
from io import BytesIO
from unittest.mock import patch

import pytest
from PIL import Image

# pyrefly: ignore [missing-import]
from app.services.payment_analyzer import (
    PaymentImageError,
    analyze_payment_image,
)


def make_test_image() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (400, 600), "white").save(
        buffer, format="PNG"
    )
    return buffer.getvalue()


def fake_ocr(_image_bytes):
    return {
        "raw_text": "Payment successful INR 500",
        "amount": 500.0,
        "currency": "INR",
        "reference": "DEMO123456",
        "date": "2026-10-14",
        "time": "12:30:00",
        "timestamp": "2026-10-14T12:30:00",
        "payee": "Demo Merchant",
        "displayed_status": "SUCCESS",
        "ocr_confidence": 0.91,
        "fields_missing": [],
    }


def fake_forensics(_image_bytes):
    return {
        "width": 400,
        "height": 600,
        "sharpness_score": 25.0,
        "ela_mean": 2.5,
        "indicators": [],
        "assessment": "INCONCLUSIVE",
        "limitations": [
            "ELA alone cannot prove manipulation."
        ],
    }


@patch(
    "app.services.payment_analyzer.inspect_image",
    side_effect=fake_forensics,
)
@patch(
    "app.services.payment_analyzer.extract_payment_details",
    side_effect=fake_ocr,
)
def test_analyzer_returns_expected_schema(
    mock_ocr, mock_forensics
):
    result = analyze_payment_image(make_test_image())

    assert result["schema_version"] == "1.0"
    assert result["ocr"]["amount"] == 500.0
    assert result["ocr"]["reference"] == "DEMO123456"
    assert result["ocr"]["displayed_status"] == "SUCCESS"
    assert result["verification"]["status"] == "UNVERIFIED"
    assert result["verification"]["source"] == "none"
    assert len(result["file"]["sha256"]) == 64

    mock_ocr.assert_called_once()
    mock_forensics.assert_called_once()


def test_rejects_empty_input():
    with pytest.raises(PaymentImageError) as error:
        analyze_payment_image(b"")

    assert error.value.code == "EMPTY_IMAGE"


def test_rejects_corrupt_image():
    with pytest.raises(PaymentImageError) as error:
        analyze_payment_image(b"not an image")

    assert error.value.code == "INVALID_IMAGE"


def test_rejects_unsupported_format():
    buffer = BytesIO()
    Image.new("RGB", (100, 100)).save(
        buffer, format="BMP"
    )

    with pytest.raises(PaymentImageError) as error:
        analyze_payment_image(buffer.getvalue())

    assert error.value.code == "UNSUPPORTED_FORMAT"


def test_rejects_oversized_input():
    with pytest.raises(PaymentImageError) as error:
        analyze_payment_image(b"x" * (10 * 1024 * 1024 + 1))

    assert error.value.code == "FILE_TOO_LARGE"
