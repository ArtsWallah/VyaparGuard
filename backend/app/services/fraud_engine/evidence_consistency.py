"""Compare merchant claims with OCR and fraud-engine evidence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
from math import isfinite
from typing import Mapping

from .duplicate_detector import (
    DuplicateDetectionResult,
    DuplicateStatus,
)
from app.services.recipient_verification import (
    PaymentMessageStatus,
    QRStatus,
    RecipientVerificationResult,
)
from .transaction_matcher import (
    MatchStatus,
    PaymentClaim,
    TransactionMatchResult,
)


DEFAULT_OCR_CONFIDENCE_THRESHOLD = 0.70
DEFAULT_TIMESTAMP_TOLERANCE = timedelta(minutes=5)


class FindingCategory(str, Enum):
    """Classification of one consistency observation."""

    AMOUNT_CONTRADICTION = "AMOUNT_CONTRADICTION"
    CURRENCY_CONTRADICTION = "CURRENCY_CONTRADICTION"
    REFERENCE_CONTRADICTION = "REFERENCE_CONTRADICTION"
    TIMESTAMP_CONTRADICTION = "TIMESTAMP_CONTRADICTION"
    OCR_FIELD_MISSING = "OCR_FIELD_MISSING"
    OCR_FIELD_UNREADABLE = "OCR_FIELD_UNREADABLE"
    OCR_LOW_CONFIDENCE = "OCR_LOW_CONFIDENCE"
    TRUSTED_RECORD_NOT_MATCHED = "TRUSTED_RECORD_NOT_MATCHED"
    TRUSTED_MATCH_AMBIGUOUS = "TRUSTED_MATCH_AMBIGUOUS"
    TRUSTED_MATCH_INSUFFICIENT = "TRUSTED_MATCH_INSUFFICIENT"
    DUPLICATE_CHECK_UNAVAILABLE = "DUPLICATE_CHECK_UNAVAILABLE"
    DUPLICATE_SIGNAL = "DUPLICATE_SIGNAL"
    REPLAY_SIGNAL = "REPLAY_SIGNAL"
    RECIPIENT_MISMATCH = "RECIPIENT_MISMATCH"
    QR_UNREADABLE = "QR_UNREADABLE"
    QR_UNSUPPORTED_FORMAT = "QR_UNSUPPORTED_FORMAT"
    EXPECTED_RECIPIENT_NOT_CONFIGURED = "EXPECTED_RECIPIENT_NOT_CONFIGURED"
    PAYMENT_MESSAGE_AMOUNT_CONTRADICTION = "PAYMENT_MESSAGE_AMOUNT_CONTRADICTION"
    PAYMENT_MESSAGE_REFERENCE_CONTRADICTION = "PAYMENT_MESSAGE_REFERENCE_CONTRADICTION"
    PAYMENT_MESSAGE_UNREADABLE = "PAYMENT_MESSAGE_UNREADABLE"
    PAYMENT_MESSAGE_INSUFFICIENT = "PAYMENT_MESSAGE_INSUFFICIENT"


class FindingSeverity(str, Enum):
    """Severity of a finding, not a final fraud verdict."""

    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


Evidence = tuple[tuple[str, object], ...]


@dataclass(frozen=True)
class EvidenceConsistencyInput:
    """Inputs from the merchant claim and completed upstream analyses."""

    claim: PaymentClaim
    ocr: Mapping[str, object] | None
    transaction_match: TransactionMatchResult
    duplicate_detection: DuplicateDetectionResult
    recipient_verification: RecipientVerificationResult | None = None
    ocr_confidence_threshold: float = DEFAULT_OCR_CONFIDENCE_THRESHOLD
    timestamp_tolerance: timedelta = DEFAULT_TIMESTAMP_TOLERANCE


@dataclass(frozen=True)
class ConsistencyFinding:
    """One explainable observation from evidence comparison."""

    category: FindingCategory
    severity: FindingSeverity
    field: str | None
    explanation: str
    evidence: Evidence = ()


@dataclass(frozen=True)
class EvidenceConsistencyResult:
    """Immutable consistency findings without a final payment verdict."""

    findings: tuple[ConsistencyFinding, ...]
    compared_fields: tuple[str, ...]
    unavailable_evidence: tuple[str, ...]
    recipient_verification: RecipientVerificationResult | None = None


def _evidence(**values: object) -> Evidence:
    return tuple((key, value) for key, value in values.items())


def _normalize_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().casefold()
    return normalized or None


def _to_decimal(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        decimal_value = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return decimal_value if decimal_value.is_finite() else None


def _to_timestamp(value: object) -> datetime | None:
    if isinstance(value, datetime):
        timestamp = value
    elif isinstance(value, str):
        normalized = value.strip()
        if not normalized or len(normalized) == 10:
            return None
        try:
            timestamp = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None

    if timestamp.tzinfo is None:
        return timestamp.replace(tzinfo=timezone.utc)
    try:
        return timestamp.astimezone(timezone.utc)
    except (OverflowError, ValueError):
        return None


def _read_ocr_value(
    ocr: Mapping[str, object] | None,
    field: str,
) -> tuple[bool, object]:
    if ocr is None:
        return False, None
    nested = ocr.get("ocr")
    source = nested if isinstance(nested, Mapping) else ocr
    if field not in source:
        return False, None
    return True, source[field]


def _add_finding(
    findings: list[ConsistencyFinding],
    category: FindingCategory,
    severity: FindingSeverity,
    field: str | None,
    explanation: str,
    **evidence: object,
) -> None:
    findings.append(
        ConsistencyFinding(
            category=category,
            severity=severity,
            field=field,
            explanation=explanation,
            evidence=_evidence(**evidence),
        )
    )


def _compare_field(
    findings: list[ConsistencyFinding],
    unavailable: list[str],
    claim: PaymentClaim,
    ocr: Mapping[str, object] | None,
    field: str,
    category: FindingCategory,
    normalize,
    *,
    timestamp_tolerance: timedelta,
) -> bool:
    claim_value = getattr(claim, field)
    if claim_value is None:
        unavailable.append(f"claim.{field}")
        return False

    present, raw_ocr_value = _read_ocr_value(ocr, field)
    if not present or raw_ocr_value is None:
        unavailable.append(f"ocr.{field}")
        _add_finding(
            findings,
            FindingCategory.OCR_FIELD_MISSING,
            FindingSeverity.INFO,
            field,
            f"OCR did not provide a value for {field}.",
        )
        return False

    ocr_value = normalize(raw_ocr_value)
    claim_normalized = normalize(claim_value)
    if ocr_value is None or claim_normalized is None:
        _add_finding(
            findings,
            FindingCategory.OCR_FIELD_UNREADABLE,
            FindingSeverity.LOW,
            field,
            f"OCR provided an unreadable {field} value.",
            ocr_value=raw_ocr_value,
        )
        return False

    if field == "timestamp":
        equal = abs(claim_normalized - ocr_value) <= timestamp_tolerance
    else:
        equal = claim_normalized == ocr_value
    if not equal:
        _add_finding(
            findings,
            category,
            FindingSeverity.HIGH,
            field,
            f"Merchant claim and OCR evidence disagree on {field}.",
            claim_value=claim_value,
            ocr_value=raw_ocr_value,
        )
    return True


def _validate_configuration(input_data: EvidenceConsistencyInput) -> None:
    if not 0 <= input_data.ocr_confidence_threshold <= 1:
        raise ValueError("ocr_confidence_threshold must be between 0 and 1.")
    if input_data.timestamp_tolerance < timedelta(0):
        raise ValueError("timestamp_tolerance must not be negative.")


def _add_confidence_finding(
    findings: list[ConsistencyFinding],
    unavailable: list[str],
    ocr: Mapping[str, object] | None,
    threshold: float,
) -> None:
    present, raw_confidence = _read_ocr_value(ocr, "confidence")
    if not present:
        present, raw_confidence = _read_ocr_value(ocr, "ocr_confidence")
    if not present or raw_confidence is None:
        unavailable.append("ocr.confidence")
        return

    try:
        confidence = float(raw_confidence)
    except (TypeError, ValueError):
        confidence = None
    if confidence is None or not isfinite(confidence) or not 0 <= confidence <= 1:
        _add_finding(
            findings,
            FindingCategory.OCR_FIELD_UNREADABLE,
            FindingSeverity.LOW,
            "confidence",
            "OCR confidence was present but unreadable.",
            ocr_confidence=raw_confidence,
        )
    elif confidence < threshold:
        _add_finding(
            findings,
            FindingCategory.OCR_LOW_CONFIDENCE,
            FindingSeverity.LOW,
            "confidence",
            "OCR confidence is below the configured threshold.",
            ocr_confidence=confidence,
            threshold=threshold,
        )


def _add_match_findings(
    findings: list[ConsistencyFinding],
    result: TransactionMatchResult,
) -> None:
    evidence = _evidence(
        status=result.status.value,
        matched_transaction_id=result.matched_transaction_id,
        candidate_count=result.candidate_count,
        conflict_fields=result.conflict_fields,
        reasons=result.reasons,
    )
    if result.status is MatchStatus.NO_MATCH:
        findings.append(
            ConsistencyFinding(
                FindingCategory.TRUSTED_RECORD_NOT_MATCHED,
                FindingSeverity.INFO,
                None,
                "No eligible trusted transaction matched the claim.",
                evidence,
            )
        )
    elif result.status is MatchStatus.AMBIGUOUS_MATCH:
        findings.append(
            ConsistencyFinding(
                FindingCategory.TRUSTED_MATCH_AMBIGUOUS,
                FindingSeverity.MEDIUM,
                None,
                "More than one eligible trusted transaction matched the claim.",
                evidence,
            )
        )
    elif result.status is MatchStatus.INSUFFICIENT_DATA:
        findings.append(
            ConsistencyFinding(
                FindingCategory.TRUSTED_MATCH_INSUFFICIENT,
                FindingSeverity.INFO,
                None,
                "The trusted transaction match did not have enough evidence.",
                evidence,
            )
        )
    elif result.status is MatchStatus.AMOUNT_CONFLICT:
        findings.append(
            ConsistencyFinding(
                FindingCategory.AMOUNT_CONTRADICTION,
                FindingSeverity.HIGH,
                "amount",
                "The trusted transaction result reports an amount conflict.",
                evidence,
            )
        )
    elif result.status is MatchStatus.REFERENCE_CONFLICT:
        findings.append(
            ConsistencyFinding(
                FindingCategory.REFERENCE_CONTRADICTION,
                FindingSeverity.HIGH,
                "reference",
                "The trusted transaction result reports a reference conflict.",
                evidence,
            )
        )


def _add_duplicate_findings(
    findings: list[ConsistencyFinding],
    unavailable: list[str],
    result: DuplicateDetectionResult,
) -> None:
    for check in result.unavailable_checks:
        unavailable.append(f"duplicate.{check}")

    if result.status is DuplicateStatus.INSUFFICIENT_DATA:
        if result.unavailable_checks:
            findings.append(
                ConsistencyFinding(
                    FindingCategory.DUPLICATE_CHECK_UNAVAILABLE,
                    FindingSeverity.INFO,
                    None,
                    "Duplicate checks were unavailable because required evidence was missing.",
                    _evidence(unavailable_checks=result.unavailable_checks),
                )
            )
        return

    if result.status is DuplicateStatus.REPLAY_SUSPECTED:
        findings.append(
            ConsistencyFinding(
                FindingCategory.REPLAY_SIGNAL,
                FindingSeverity.HIGH,
                None,
                "Prior-claim history contains a replay signal.",
                _evidence(
                    status=result.status.value,
                    signals=result.signals,
                    matched_claim_ids=result.matched_claim_ids,
                    exact_image_claim_ids=result.exact_image_claim_ids,
                    similar_image_claim_ids=result.similar_image_claim_ids,
                    reference_claim_ids=result.reference_claim_ids,
                ),
            )
        )
        return

    signal_severity = {
        DuplicateStatus.EXACT_IMAGE_REUSE: FindingSeverity.MEDIUM,
        DuplicateStatus.SIMILAR_IMAGE_REUSE: FindingSeverity.LOW,
        DuplicateStatus.REFERENCE_REUSE: FindingSeverity.MEDIUM,
    }
    if result.status in signal_severity:
        findings.append(
            ConsistencyFinding(
                FindingCategory.DUPLICATE_SIGNAL,
                signal_severity[result.status],
                None,
                "Prior-claim history contains a duplicate signal.",
                _evidence(
                    status=result.status.value,
                    signals=result.signals,
                    matched_claim_ids=result.matched_claim_ids,
                    exact_image_claim_ids=result.exact_image_claim_ids,
                    similar_image_claim_ids=result.similar_image_claim_ids,
                    reference_claim_ids=result.reference_claim_ids,
                ),
            )
        )


def _recipient_evidence(result: RecipientVerificationResult) -> dict[str, object]:
    destination = result.qr.destination
    evidence: dict[str, object] = {
        "qr_status": result.qr.status.value,
        "expected_recipient": result.qr.expected_recipient,
        "expected_recipient_configured": (
            result.qr.expected_recipient is not None
        ),
        "payee_identifier": (
            destination.payee_identifier if destination is not None else None
        ),
        "payee_name": destination.payee_name if destination is not None else None,
        "qr_amount": destination.amount if destination is not None else None,
        "qr_reference": destination.reference if destination is not None else None,
    }
    if result.message is not None:
        evidence.update(
            {
                "message_status": result.message.status.value,
                "message_amount": result.message.amount,
                "message_reference": result.message.reference,
                "message_compared_fields": result.message.compared_fields,
            }
        )
    return evidence


def _add_recipient_findings(
    findings: list[ConsistencyFinding],
    unavailable: list[str],
    result: RecipientVerificationResult | None,
) -> None:
    if result is None:
        unavailable.append("recipient_verification")
        return

    evidence = _recipient_evidence(result)
    if result.qr.status is QRStatus.RECIPIENT_MISMATCH:
        findings.append(
            ConsistencyFinding(
                FindingCategory.RECIPIENT_MISMATCH,
                FindingSeverity.HIGH,
                "recipient",
                result.qr.explanation,
                tuple(evidence.items()),
            )
        )
    elif result.qr.status is QRStatus.UNREADABLE:
        findings.append(
            ConsistencyFinding(
                FindingCategory.QR_UNREADABLE,
                FindingSeverity.INFO,
                "qr",
                result.qr.explanation,
                tuple(evidence.items()),
            )
        )
    elif result.qr.status is QRStatus.UNSUPPORTED_FORMAT:
        findings.append(
            ConsistencyFinding(
                FindingCategory.QR_UNSUPPORTED_FORMAT,
                FindingSeverity.INFO,
                "qr",
                result.qr.explanation,
                tuple(evidence.items()),
            )
        )
    elif result.qr.status is QRStatus.EXPECTED_RECIPIENT_NOT_CONFIGURED:
        findings.append(
            ConsistencyFinding(
                FindingCategory.EXPECTED_RECIPIENT_NOT_CONFIGURED,
                FindingSeverity.INFO,
                "recipient",
                result.qr.explanation,
                tuple(evidence.items()),
            )
        )

    if result.message is None:
        return
    unavailable.append("payment_message")
    message = result.message
    if message.status is PaymentMessageStatus.AMOUNT_MISMATCH:
        category = FindingCategory.PAYMENT_MESSAGE_AMOUNT_CONTRADICTION
        severity = FindingSeverity.HIGH
    elif message.status is PaymentMessageStatus.REFERENCE_MISMATCH:
        category = FindingCategory.PAYMENT_MESSAGE_REFERENCE_CONTRADICTION
        severity = FindingSeverity.HIGH
    elif message.status is PaymentMessageStatus.UNREADABLE:
        category = FindingCategory.PAYMENT_MESSAGE_UNREADABLE
        severity = FindingSeverity.LOW
    elif message.status is PaymentMessageStatus.INSUFFICIENT_DATA:
        category = FindingCategory.PAYMENT_MESSAGE_INSUFFICIENT
        severity = FindingSeverity.INFO
    else:
        return
    findings.append(
        ConsistencyFinding(
            category,
            severity,
            "payment_message",
            message.explanation,
            tuple(evidence.items()),
        )
    )


def evaluate_consistency(
    input_data: EvidenceConsistencyInput,
) -> EvidenceConsistencyResult:
    """Produce consistency findings without assigning a final verdict."""
    _validate_configuration(input_data)
    findings: list[ConsistencyFinding] = []
    unavailable: list[str] = []
    compared_fields: list[str] = []

    field_rules = (
        ("amount", FindingCategory.AMOUNT_CONTRADICTION, _to_decimal),
        ("currency", FindingCategory.CURRENCY_CONTRADICTION, _normalize_text),
        ("reference", FindingCategory.REFERENCE_CONTRADICTION, _normalize_text),
        ("timestamp", FindingCategory.TIMESTAMP_CONTRADICTION, _to_timestamp),
    )
    for field, category, normalize in field_rules:
        if _compare_field(
            findings,
            unavailable,
            input_data.claim,
            input_data.ocr,
            field,
            category,
            normalize,
            timestamp_tolerance=input_data.timestamp_tolerance,
        ):
            compared_fields.append(field)

    _add_confidence_finding(
        findings,
        unavailable,
        input_data.ocr,
        input_data.ocr_confidence_threshold,
    )
    _add_recipient_findings(
        findings,
        unavailable,
        input_data.recipient_verification,
    )
    _add_match_findings(findings, input_data.transaction_match)
    _add_duplicate_findings(findings, unavailable, input_data.duplicate_detection)

    return EvidenceConsistencyResult(
        findings=tuple(findings),
        compared_fields=tuple(compared_fields),
        unavailable_evidence=tuple(dict.fromkeys(unavailable)),
        recipient_verification=input_data.recipient_verification,
    )
