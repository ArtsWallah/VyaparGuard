
from __future__ import annotations

import hashlib
from io import BytesIO
from typing import Any

from PIL import Image, UnidentifiedImageError

# pyrefly: ignore [missing-import]
from app.services.ocr_service import extract_payment_details
from app.services.image_forensics import inspect_image


MAX_FILE_SIZE = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 25_000_000
SUPPORTED_FORMATS = {"JPEG", "PNG", "WEBP"}


class PaymentImageError(ValueError):
    """Expected image validation or processing error."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _validate_image(image_bytes: bytes) -> dict[str, Any]:
    if not isinstance(image_bytes, bytes) or not image_bytes:
        raise PaymentImageError(
            "EMPTY_IMAGE",
            "No image data was provided.",
        )

    if len(image_bytes) > MAX_FILE_SIZE:
        raise PaymentImageError(
            "FILE_TOO_LARGE",
            "Image exceeds the 10 MB limit.",
        )

    try:
        with Image.open(BytesIO(image_bytes)) as image:
            image_format = image.format
            width, height = image.size
            image.verify()

    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        Image.DecompressionBombError,
    ) as exc:
        raise PaymentImageError(
            "INVALID_IMAGE",
            "The uploaded file is not a valid image.",
        ) from exc

    if image_format not in SUPPORTED_FORMATS:
        raise PaymentImageError(
            "UNSUPPORTED_FORMAT",
            "Only JPEG, PNG, and WebP images are supported.",
        )

    if width <= 0 or height <= 0:
        raise PaymentImageError(
            "INVALID_DIMENSIONS",
            "Image dimensions are invalid.",
        )

    if width * height > MAX_IMAGE_PIXELS:
        raise PaymentImageError(
            "IMAGE_TOO_LARGE",
            "Image pixel dimensions exceed the processing limit.",
        )

    return {
        "format": image_format.lower(),
        "width": width,
        "height": height,
        "size_bytes": len(image_bytes),
        "sha256": hashlib.sha256(image_bytes).hexdigest(),
    }


def analyze_payment_image(
    image_bytes: bytes,
    filename: str | None = None,
    content_type: str | None = None,
) -> dict[str, Any]:
    """
    Analyze a payment screenshot using OCR and image forensics.

    Screenshot content and forensic indicators are not proof
    that a payment was received. Verification remains UNVERIFIED
    until a trusted transaction source confirms the payment.
    """
    metadata = _validate_image(image_bytes)

    try:
        ocr_result = extract_payment_details(image_bytes)
    except Exception as exc:
        raise PaymentImageError(
            "OCR_FAILED",
            "Text extraction failed.",
        ) from exc

    # Support either {"fields": {...}} or top-level OCR fields.
    fields = ocr_result.get("fields")
    if not isinstance(fields, dict):
        fields = ocr_result

    transaction_id = fields.get("transaction_id")
    upi_reference = fields.get("upi_reference")
    reference = fields.get("reference") or (
        upi_reference or transaction_id
    )

    missing_fields = [
        field
        for field in ("amount", "date")
        if fields.get(field) is None
    ]

    ocr = {
        "raw_text": ocr_result.get("raw_text", ""),
        "confidence": ocr_result.get(
            "confidence",
            ocr_result.get("ocr_confidence", 0.0),
        ),
        "amount": fields.get("amount"),
        "currency": fields.get("currency"),
        "date": fields.get("date"),
        "time": fields.get("time"),
        "timestamp": fields.get("timestamp"),
        "transaction_id": transaction_id,
        "upi_reference": upi_reference,
        "reference": reference,
        "payee": fields.get("payee"),
        "displayed_status": fields.get("displayed_status"),
        "fields_missing": fields.get("fields_missing", missing_fields),
    }

    try:
        forensic_result = inspect_image(image_bytes)
    except Exception as exc:
        raise PaymentImageError(
            "FORENSICS_FAILED",
            "Image analysis failed.",
        ) from exc

    reasons = [
        "Screenshot analysis cannot establish that a payment was received. "
        "No trusted transaction source has been checked."
    ]
    if forensic_result.get("limitations"):
        reasons.extend(forensic_result["limitations"])

    return {
        "scan_id": metadata["sha256"][:12],
        "status": "UNVERIFIED",
        "extracted": {
            "amount": ocr.get("amount"),
            "transaction_id": ocr.get("transaction_id"),
            "upi_reference": ocr.get("upi_reference"),
            "reference": ocr.get("reference"),
            "date": ocr.get("date"),
            "time": ocr.get("time"),
            "timestamp": ocr.get("timestamp"),
            "payee": ocr.get("payee"),
            "currency": ocr.get("currency"),
            "displayed_status": ocr.get("displayed_status"),
        },
        "checks": {
            "duplicate": False,
            "trusted_record_match": False,
        },
        "reasons": reasons,
        "verification_source": "none",
        "schema_version": "1.0",
        "file": {
            **metadata,
            "filename": filename,
            "declared_content_type": content_type,
        },
        "ocr": ocr,
        "image_quality": {
            "width": metadata["width"],
            "height": metadata["height"],
            "sharpness_score": forensic_result.get(
                "sharpness_score"
            ),
        },
        "forensics": {
            "ela_mean": forensic_result.get("ela_mean"),
            "indicators": forensic_result.get("indicators", []),
            "assessment": forensic_result.get(
                "assessment",
                "INCONCLUSIVE",
            ),
            "limitations": forensic_result.get("limitations", []),
        },
        "errors": [],
        "verification": {
            "status": "UNVERIFIED",
            "source": "none",
            "reason": (
                "Screenshot analysis cannot establish that "
                "a payment was received. No trusted transaction "
                "source has been checked."
            ),
        },
    }
