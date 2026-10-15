"""Inspect QR payment destinations and optional untrusted payment messages."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any, Mapping
from urllib.parse import parse_qs, urlsplit

import cv2
import numpy as np

MAX_QR_INPUT_BYTES = 10 * 1024 * 1024
MAX_QR_PAYLOAD_LENGTH = 2048
MAX_PAYEE_IDENTIFIER_LENGTH = 256
MAX_PAYEE_NAME_LENGTH = 200
MAX_REFERENCE_LENGTH = 100
MAX_AMOUNT = Decimal("1000000000")


class QRStatus(str, Enum):
    MATCH = "MATCH"
    RECIPIENT_MISMATCH = "RECIPIENT_MISMATCH"
    UNREADABLE = "UNREADABLE"
    UNSUPPORTED_FORMAT = "UNSUPPORTED_FORMAT"
    EXPECTED_RECIPIENT_NOT_CONFIGURED = "EXPECTED_RECIPIENT_NOT_CONFIGURED"


class PaymentMessageStatus(str, Enum):
    MATCH = "MATCH"
    AMOUNT_MISMATCH = "AMOUNT_MISMATCH"
    REFERENCE_MISMATCH = "REFERENCE_MISMATCH"
    UNREADABLE = "UNREADABLE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


@dataclass(frozen=True)
class QRDestination:
    scheme: str
    payee_identifier: str
    payee_name: str | None
    amount: Decimal | None
    reference: str | None


@dataclass(frozen=True)
class QRInspectionResult:
    status: QRStatus
    destination: QRDestination | None
    expected_recipient: str | None
    explanation: str


@dataclass(frozen=True)
class PaymentMessageResult:
    status: PaymentMessageStatus
    amount: Decimal | None
    reference: str | None
    compared_fields: tuple[str, ...]
    explanation: str


@dataclass(frozen=True)
class RecipientVerificationResult:
    qr: QRInspectionResult
    message: PaymentMessageResult | None


def _normalize_identifier(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().casefold()
    return normalized or None


def _parse_decimal(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        amount = Decimal(str(value).strip())
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not amount.is_finite() or amount < 0 or amount > MAX_AMOUNT:
        return None
    return amount


def _parse_upi_payload(payload: str) -> QRDestination | None:
    if len(payload) > MAX_QR_PAYLOAD_LENGTH:
        return None

    parts = urlsplit(payload)
    if parts.scheme.casefold() != "upi" or parts.netloc.casefold() != "pay":
        return None

    query = parse_qs(parts.query, keep_blank_values=True)
    payee_values = query.get("pa", [])
    if len(payee_values) != 1:
        return None

    payee_identifier = _normalize_identifier(payee_values[0])
    if (
        payee_identifier is None
        or len(payee_identifier) > MAX_PAYEE_IDENTIFIER_LENGTH
        or not re.fullmatch(
            r"[a-z0-9][a-z0-9._-]{1,255}@[a-z0-9][a-z0-9.-]{0,63}",
            payee_identifier,
        )
    ):
        return None

    payee_name = _normalize_identifier(query.get("pn", [None])[0])
    if payee_name is not None and len(payee_name) > MAX_PAYEE_NAME_LENGTH:
        return None

    amount = None
    if "am" in query:
        amount_values = query["am"]
        if len(amount_values) != 1:
            return None
        amount = _parse_decimal(amount_values[0])
        if amount is None or amount == 0:
            return None

    reference = _normalize_identifier(query.get("tr", [None])[0])
    if reference is not None and len(reference) > MAX_REFERENCE_LENGTH:
        return None

    return QRDestination(
        scheme="upi://pay",
        payee_identifier=payee_identifier,
        payee_name=payee_name,
        amount=amount,
        reference=reference,
    )


def inspect_qr_destination(image_bytes: bytes) -> QRInspectionResult:
    """Decode one supported UPI QR payload without following its destination."""
    if not isinstance(image_bytes, bytes) or not image_bytes:
        return QRInspectionResult(
            QRStatus.UNREADABLE,
            None,
            None,
            "No QR image data was provided.",
        )
    if len(image_bytes) > MAX_QR_INPUT_BYTES:
        return QRInspectionResult(
            QRStatus.UNSUPPORTED_FORMAT,
            None,
            None,
            "QR image exceeds the supported input size.",
        )

    try:
        image = cv2.imdecode(
            np.frombuffer(image_bytes, dtype=np.uint8),
            cv2.IMREAD_COLOR,
        )
        if image is None:
            return QRInspectionResult(
                QRStatus.UNREADABLE,
                None,
                None,
                "The QR image could not be decoded.",
            )
        payload, _, _ = cv2.QRCodeDetector().detectAndDecode(image)
    except (cv2.error, ValueError):
        return QRInspectionResult(
            QRStatus.UNREADABLE,
            None,
            None,
            "The QR image could not be inspected.",
        )

    if not payload:
        return QRInspectionResult(
            QRStatus.UNREADABLE,
            None,
            None,
            "No readable QR payload was found.",
        )
    if len(payload) > MAX_QR_PAYLOAD_LENGTH:
        return QRInspectionResult(
            QRStatus.UNSUPPORTED_FORMAT,
            None,
            None,
            "The QR payload exceeds the supported length.",
        )

    destination = _parse_upi_payload(payload)
    if destination is None:
        return QRInspectionResult(
            QRStatus.UNSUPPORTED_FORMAT,
            None,
            None,
            "Only supported upi://pay QR payloads are recognized.",
        )

    return QRInspectionResult(
        QRStatus.EXPECTED_RECIPIENT_NOT_CONFIGURED,
        destination,
        None,
        "QR destination decoded; no expected recipient was configured.",
    )


def compare_qr_recipient(
    inspection: QRInspectionResult,
    expected_recipient: str | None,
) -> QRInspectionResult:
    """Compare a decoded UPI payee with an explicitly supplied expectation."""
    normalized_expected = _normalize_identifier(expected_recipient)
    if inspection.destination is None:
        return inspection
    if normalized_expected is None:
        return QRInspectionResult(
            QRStatus.EXPECTED_RECIPIENT_NOT_CONFIGURED,
            inspection.destination,
            None,
            "QR destination decoded; no expected recipient was configured.",
        )
    if len(normalized_expected) > MAX_PAYEE_IDENTIFIER_LENGTH:
        return QRInspectionResult(
            QRStatus.RECIPIENT_MISMATCH,
            inspection.destination,
            normalized_expected,
            "The expected recipient identifier is too long.",
        )
    if normalized_expected == inspection.destination.payee_identifier:
        return QRInspectionResult(
            QRStatus.MATCH,
            inspection.destination,
            normalized_expected,
            "QR destination matches the expected recipient identifier.",
        )
    return QRInspectionResult(
        QRStatus.RECIPIENT_MISMATCH,
        inspection.destination,
        normalized_expected,
        "QR destination does not match the expected recipient identifier.",
    )


def _parse_message_amount(message: str) -> Decimal | None:
    match = re.search(
        r"(?:₹|inr|rs\.?|amount|total|paid)\s*[:=\-]?\s*"
        r"([0-9][0-9,]*(?:\.[0-9]{1,2})?)",
        message,
        re.IGNORECASE,
    )
    if not match:
        return None
    return _parse_decimal(match.group(1).replace(",", ""))


def _parse_message_reference(message: str) -> str | None:
    match = re.search(
        r"(?:upi\s*(?:reference|ref)|reference|txn(?:\s*id)?|"
        r"transaction\s*(?:id|number))\s*[:#=\-]?\s*"
        r"([A-Za-z0-9][A-Za-z0-9_-]{5,99})",
        message,
        re.IGNORECASE,
    )
    return _normalize_identifier(match.group(1)) if match else None


def _ocr_field(ocr: Mapping[str, Any] | None, field: str) -> object:
    if not isinstance(ocr, Mapping):
        return None
    nested = ocr.get("ocr")
    source = nested if isinstance(nested, Mapping) else ocr
    return source.get(field)


def compare_payment_message(
    message: str | None,
    ocr: Mapping[str, Any] | None,
) -> PaymentMessageResult | None:
    """Compare optional untrusted message fields with OCR observations."""
    if message is None:
        return None
    normalized_message = message.strip()
    if not normalized_message or len(normalized_message) > MAX_QR_PAYLOAD_LENGTH:
        return PaymentMessageResult(
            PaymentMessageStatus.UNREADABLE,
            None,
            None,
            (),
            "Payment message is empty or exceeds the supported length.",
        )

    message_amount = _parse_message_amount(normalized_message)
    message_reference = _parse_message_reference(normalized_message)
    ocr_amount = _parse_decimal(_ocr_field(ocr, "amount"))
    ocr_reference = _normalize_identifier(_ocr_field(ocr, "reference"))
    compared_fields: list[str] = []

    if message_amount is not None and ocr_amount is not None:
        compared_fields.append("amount")
        if message_amount != ocr_amount:
            return PaymentMessageResult(
                PaymentMessageStatus.AMOUNT_MISMATCH,
                message_amount,
                message_reference,
                tuple(compared_fields),
                "Untrusted payment message amount differs from OCR amount.",
            )
    if message_reference is not None and ocr_reference is not None:
        compared_fields.append("reference")
        if message_reference != ocr_reference:
            return PaymentMessageResult(
                PaymentMessageStatus.REFERENCE_MISMATCH,
                message_amount,
                message_reference,
                tuple(compared_fields),
                "Untrusted payment message reference differs from OCR reference.",
            )

    if not compared_fields:
        return PaymentMessageResult(
            PaymentMessageStatus.INSUFFICIENT_DATA,
            message_amount,
            message_reference,
            (),
            "Message and OCR did not provide a comparable amount or reference.",
        )
    return PaymentMessageResult(
        PaymentMessageStatus.MATCH,
        message_amount,
        message_reference,
        tuple(compared_fields),
        "Comparable payment message fields agree with OCR; the message remains untrusted.",
    )


def verify_recipient_evidence(
    image_bytes: bytes,
    expected_recipient: str | None = None,
    payment_message: str | None = None,
    ocr: Mapping[str, Any] | None = None,
) -> RecipientVerificationResult:
    inspection = inspect_qr_destination(image_bytes)
    qr = compare_qr_recipient(inspection, expected_recipient)
    message = compare_payment_message(payment_message, ocr)
    return RecipientVerificationResult(qr=qr, message=message)
