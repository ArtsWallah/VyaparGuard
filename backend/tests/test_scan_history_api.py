import os
from datetime import datetime, timezone

os.environ.setdefault("DATABASE_URL", "sqlite://")

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import main
from app.db.database import Base
from app.db.models import Scan, ScanCheck, SeenClaim


@pytest.fixture
def api_session(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'history.db'}")
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    monkeypatch.setattr(main, "SessionLocal", session_factory)
    with session_factory() as session:
        yield session
    Base.metadata.drop_all(bind=engine)


def add_scan(session, request_id, verdict, created_at):
    scan = Scan(
        request_id=request_id,
        verdict=verdict,
        demo_mode=True,
        amount=500.0,
        reference_fingerprint="a" * 64,
        summary=f"Summary for {request_id}",
        processing_ms=10,
        created_at=created_at,
    )
    session.add(scan)
    session.flush()
    session.add(
        ScanCheck(
            scan_id=scan.id,
            check_id="AMOUNT_CONTRADICTION",
            status="HIGH",
            message="Amount differs.",
            evidence={"source": "matcher"},
        )
    )
    session.commit()


def test_list_scans_is_paginated_and_ordered(api_session):
    add_scan(
        api_session,
        "scan-old",
        "UNVERIFIED",
        datetime(2026, 10, 14, tzinfo=timezone.utc),
    )
    add_scan(
        api_session,
        "scan-new",
        "SUSPICIOUS",
        datetime(2026, 10, 15, tzinfo=timezone.utc),
    )

    result = main.list_scans(page=1, page_size=1)

    assert result["total"] == 2
    assert result["has_next"] is True
    assert result["items"][0]["scan_id"] == "scan-new"


def test_get_scan_returns_details_and_checks(api_session):
    add_scan(
        api_session,
        "scan-detail",
        "UNVERIFIED",
        datetime(2026, 10, 15, tzinfo=timezone.utc),
    )

    result = main.get_scan("scan-detail")

    assert result["status"] == "UNVERIFIED"
    assert result["reference_available"] is True
    assert result["checks"][0]["check_id"] == "AMOUNT_CONTRADICTION"
    assert result["checks"][0]["evidence"] == {"source": "matcher"}


def test_missing_scan_returns_404(api_session):
    with pytest.raises(HTTPException) as error:
        main.get_scan("does-not-exist")

    assert error.value.status_code == 404


def test_delete_scan_removes_scan_and_checks_but_keeps_claim_history(api_session):
    add_scan(
        api_session,
        "scan-delete",
        "UNVERIFIED",
        datetime(2026, 10, 15, tzinfo=timezone.utc),
    )
    api_session.add(
        SeenClaim(
            reference_fingerprint="a" * 64,
            image_sha256="b" * 64,
            occurrence_count=1,
        )
    )
    api_session.commit()

    result = main.delete_scan("scan-delete")

    assert result == {"scan_id": "scan-delete", "deleted": True}
    assert api_session.query(Scan).filter_by(request_id="scan-delete").one_or_none() is None
    assert api_session.query(ScanCheck).count() == 0
    assert api_session.query(SeenClaim).count() == 1


def test_blank_scan_id_is_rejected(api_session):
    with pytest.raises(HTTPException) as error:
        main.get_scan("   ")

    assert error.value.status_code == 400
