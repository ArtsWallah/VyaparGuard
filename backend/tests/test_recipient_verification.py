from io import BytesIO
from decimal import Decimal

import cv2
import pytest
from PIL import Image

from app.services.recipient_verification import (
    PaymentMessageStatus,
    QRStatus,
    compare_payment_message,
    compare_qr_recipient,
    inspect_qr_destination,
    verify_recipient_evidence,
)


def image_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (120, 120), "white").save(buffer, format="PNG")
    return buffer.getvalue()


class FakeDetector:
    def __init__(self, payload: str):
        self.payload = payload

    def detectAndDecode(self, _image):
        return self.payload, None, None


def inspect_with_payload(monkeypatch, payload: str):
    monkeypatch.setattr(cv2, "QRCodeDetector", lambda: FakeDetector(payload))
    return inspect_qr_destination(image_bytes())


def test_valid_upi_payload_is_decoded(monkeypatch):
    result = inspect_with_payload(
        monkeypatch,
        "upi://pay?pa=Merchant.Store%40upi&pn=Demo%20Merchant&am=500.00&tr=ABC123456",
    )

    assert result.status is QRStatus.EXPECTED_RECIPIENT_NOT_CONFIGURED
    assert result.destination is not None
    assert result.destination.payee_identifier == "merchant.store@upi"
    assert result.destination.payee_name == "demo merchant"
    assert result.destination.amount == Decimal("500.00")
    assert result.destination.reference == "abc123456"


def test_matching_expected_recipient_is_reported(monkeypatch):
    inspection = inspect_with_payload(monkeypatch, "upi://pay?pa=merchant@upi")

    result = compare_qr_recipient(inspection, " Merchant@UPI ")

    assert result.status is QRStatus.MATCH


def test_mismatching_expected_recipient_is_reported(monkeypatch):
    inspection = inspect_with_payload(monkeypatch, "upi://pay?pa=merchant@upi")

    result = compare_qr_recipient(inspection, "other@upi")

    assert result.status is QRStatus.RECIPIENT_MISMATCH


def test_missing_expected_recipient_is_not_fraud(monkeypatch):
    inspection = inspect_with_payload(monkeypatch, "upi://pay?pa=merchant@upi")

    result = compare_qr_recipient(inspection, None)

    assert result.status is QRStatus.EXPECTED_RECIPIENT_NOT_CONFIGURED


def test_unreadable_qr_is_reported(monkeypatch):
    result = inspect_with_payload(monkeypatch, "")

    assert result.status is QRStatus.UNREADABLE
    assert result.destination is None


def test_unsupported_scheme_is_rejected(monkeypatch):
    result = inspect_with_payload(monkeypatch, "https://example.com/payment")

    assert result.status is QRStatus.UNSUPPORTED_FORMAT
    assert result.destination is None


def test_malformed_upi_payload_is_rejected(monkeypatch):
    result = inspect_with_payload(monkeypatch, "upi://pay?pa=not-an-upi-id")

    assert result.status is QRStatus.UNSUPPORTED_FORMAT


def test_oversized_qr_input_is_rejected():
    result = inspect_qr_destination(b"x" * (10 * 1024 * 1024 + 1))

    assert result.status is QRStatus.UNSUPPORTED_FORMAT


def test_qr_parser_does_not_follow_payload(monkeypatch):
    inspection = inspect_with_payload(
        monkeypatch,
        "upi://pay?pa=merchant@upi&url=https%3A%2F%2Fevil.example%2Fpay",
    )

    assert inspection.destination is not None
    assert inspection.destination.payee_identifier == "merchant@upi"


def test_message_amount_mismatch_is_explicit():
    result = compare_payment_message(
        "INR 700 reference ABC123456",
        {"amount": 500, "reference": "ABC123456"},
    )

    assert result is not None
    assert result.status is PaymentMessageStatus.AMOUNT_MISMATCH


def test_message_reference_mismatch_is_explicit():
    result = compare_payment_message(
        "INR 500 reference OTHER123456",
        {"amount": 500, "reference": "ABC123456"},
    )

    assert result is not None
    assert result.status is PaymentMessageStatus.REFERENCE_MISMATCH


def test_message_agreement_remains_untrusted():
    result = compare_payment_message(
        "INR 500 reference ABC123456",
        {"amount": 500, "reference": "ABC123456"},
    )

    assert result is not None
    assert result.status is PaymentMessageStatus.MATCH


def test_message_missing_comparable_fields_is_insufficient():
    result = compare_payment_message("Payment successful", {"amount": None})

    assert result is not None
    assert result.status is PaymentMessageStatus.INSUFFICIENT_DATA


def test_message_oversized_input_is_unreadable():
    result = compare_payment_message("x" * 2049, {"amount": 500})

    assert result is not None
    assert result.status is PaymentMessageStatus.UNREADABLE


def test_optional_message_can_be_absent():
    result = compare_payment_message(None, {"amount": 500})

    assert result is None


def test_combined_result_contains_qr_and_message():
    result = verify_recipient_evidence(
        image_bytes(),
        expected_recipient=None,
        payment_message="INR 500 reference ABC123456",
        ocr={"amount": 500, "reference": "ABC123456"},
    )

    assert result.qr.status is QRStatus.UNREADABLE
    assert result.message is not None
    assert result.message.status is PaymentMessageStatus.MATCH
