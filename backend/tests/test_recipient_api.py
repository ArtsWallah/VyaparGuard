import asyncio
import os
from io import BytesIO

os.environ.setdefault("DATABASE_URL", "sqlite://")

from fastapi import UploadFile
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import main
from app.db.database import Base
from app.db.models import Scan


class CapturedIntegration:
    expected_recipient = None
    payment_message = None


def test_scan_route_forwards_recipient_inputs_and_preserves_response(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'recipient-api.db'}")
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    monkeypatch.setattr(main, "SessionLocal", session_factory)
    monkeypatch.setenv("VYAPARGUARD_DEMO_MODE", "false")

    def fake_analyzer(**_kwargs):
        return {
            "status": "UNVERIFIED",
            "file": {"sha256": "a" * 64},
            "ocr": {
                "amount": 500,
                "currency": "INR",
                "reference": "ABC123456",
                "payee": "Demo Merchant",
                "timestamp": "2026-10-15T10:30:00Z",
            },
            "extracted": {"amount": 500},
            "verification": {"status": "UNVERIFIED", "reason": "pending"},
            "checks": {},
            "reasons": [],
        }

    def fake_integration(
        result,
        _session,
        _request_id,
        *,
        demo_mode,
        image_bytes,
        expected_recipient,
        payment_message,
    ):
        CapturedIntegration.expected_recipient = expected_recipient
        CapturedIntegration.payment_message = payment_message
        assert demo_mode is False
        assert image_bytes == b"image-bytes"
        result["status"] = "UNVERIFIED"
        result["verification"] = {
            "status": "UNVERIFIED",
            "source": "none",
            "reason": "Recipient check is not settlement proof.",
        }
        result["fraud_engine"] = {"consistency": {"findings": []}}
        return result

    monkeypatch.setattr(main, "analyze_payment_image", fake_analyzer)
    monkeypatch.setattr(main, "integrate_fraud_engine", fake_integration)

    upload = UploadFile(
        file=BytesIO(b"image-bytes"),
        filename="payment.png",
        size=11,
    )
    result = asyncio.run(
        main.scan_payment(
            image=upload,
            expected_recipient="merchant@upi",
            payment_message="INR 500 reference ABC123456",
        )
    )

    assert result["status"] == "UNVERIFIED"
    assert CapturedIntegration.expected_recipient == "merchant@upi"
    assert CapturedIntegration.payment_message == "INR 500 reference ABC123456"
    with session_factory() as session:
        assert session.query(Scan).count() == 1
        assert session.query(Scan).one().verdict == "UNVERIFIED"

    Base.metadata.drop_all(bind=engine)
