import os
from datetime import datetime, timezone
from decimal import Decimal

os.environ.setdefault("DATABASE_URL", "sqlite://")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.db.models import DemoTransaction, SeenClaim
from app.services.fraud_engine_integration import integrate_fraud_engine


TIMESTAMP = datetime(2026, 10, 15, 10, 30, tzinfo=timezone.utc)
PHASH = "0000000000000000"
IMAGE_SHA256 = "a" * 64


@pytest.fixture
def db_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'integration.db'}")
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    with session_factory() as session:
        yield session
    Base.metadata.drop_all(bind=engine)


def analysis(
    *,
    amount=500.0,
    reference="DEMO123456",
    image_sha256=IMAGE_SHA256,
    timestamp="2026-10-15T10:30:00+00:00",
):
    ocr = {
        "amount": amount,
        "currency": "INR",
        "reference": reference,
        "payee": "Demo Merchant",
        "timestamp": timestamp,
        "confidence": 0.95,
    }
    return {
        "status": "UNVERIFIED",
        "file": {"sha256": image_sha256},
        "ocr": ocr,
        "extracted": dict(ocr),
        "verification": {
            "status": "UNVERIFIED",
            "source": "none",
            "reason": "Screenshot analysis only.",
        },
        "checks": {"duplicate": False, "trusted_record_match": False},
        "reasons": ["Screenshot analysis only."],
    }


def seed_demo_transaction(session, *, amount=500.0):
    session.add(
        DemoTransaction(
            reference_norm="DEMO123456",
            amount=amount,
            currency="INR",
            payee_alias="Demo Merchant",
            transaction_time=TIMESTAMP,
            seeded_status="SUCCESS",
        )
    )
    session.commit()


def test_demo_trusted_match_can_produce_verified_with_available_phash(db_session):
    seed_demo_transaction(db_session)

    result = integrate_fraud_engine(
        analysis(),
        db_session,
        "request-verified",
        demo_mode=True,
        image_phash=PHASH,
    )

    assert result["status"] == "VERIFIED"
    assert result["verification"]["status"] == "VERIFIED"
    assert result["verification"]["source"] == "demo_transaction_ledger"
    assert result["checks"]["trusted_record_match"] is True
    assert db_session.query(SeenClaim).count() == 1


def test_trusted_amount_conflict_produces_suspicious(db_session):
    seed_demo_transaction(db_session)

    result = integrate_fraud_engine(
        analysis(amount=501.0),
        db_session,
        "request-suspicious",
        demo_mode=True,
        image_phash=PHASH,
    )

    assert result["status"] == "SUSPICIOUS"
    assert result["verification"]["status"] == "SUSPICIOUS"
    assert any(
        finding["category"] == "AMOUNT_CONTRADICTION"
        for finding in result["fraud_engine"]["consistency"]["findings"]
    )


def test_without_trusted_source_result_is_unverified(db_session):
    result = integrate_fraud_engine(
        analysis(),
        db_session,
        "request-unverified",
        demo_mode=False,
        image_phash=PHASH,
    )

    assert result["status"] == "UNVERIFIED"
    assert result["verification"]["status"] == "UNVERIFIED"
    assert result["checks"]["trusted_match_status"] == "NO_MATCH"
    assert result["verification"]["source"] == "none"


def test_persistent_seen_claim_replay_is_suspicious(db_session):
    seed_demo_transaction(db_session)

    integrate_fraud_engine(
        analysis(),
        db_session,
        "request-first",
        demo_mode=True,
        image_phash=PHASH,
    )
    result = integrate_fraud_engine(
        analysis(),
        db_session,
        "request-replay",
        demo_mode=True,
        image_phash=PHASH,
    )

    assert result["status"] == "SUSPICIOUS"
    assert result["verification"]["status"] == "SUSPICIOUS"
    assert result["checks"]["duplicate_status"] == "REPLAY_SUSPECTED"
    assert any(
        finding["category"] == "REPLAY_SIGNAL"
        for finding in result["fraud_engine"]["consistency"]["findings"]
    )


def test_missing_phash_keeps_production_result_unverified(db_session):
    seed_demo_transaction(db_session)

    result = integrate_fraud_engine(
        analysis(),
        db_session,
        "request-no-phash",
        demo_mode=True,
    )

    assert result["status"] == "UNVERIFIED"
    assert result["checks"]["duplicate_status"] == "NO_DUPLICATE"
    assert "one or more duplicate checks were unavailable" in result["verification"]["reason"]
