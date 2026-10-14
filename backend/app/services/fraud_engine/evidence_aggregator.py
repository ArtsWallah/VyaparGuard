"""Aggregate Fraud Engine evidence into a final outcome."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .duplicate_detector import DuplicateDetectionResult, DuplicateStatus
from .evidence_consistency import (
    ConsistencyFinding,
    EvidenceConsistencyResult,
    FindingCategory,
    FindingSeverity,
)
from .transaction_matcher import MatchStatus, TransactionMatchResult


class AggregationStatus(str, Enum):
    """Final outcome produced by the Fraud Engine decision layer."""

    VERIFIED = "VERIFIED"
    SUSPICIOUS = "SUSPICIOUS"
    UNVERIFIED = "UNVERIFIED"


@dataclass(frozen=True)
class EvidenceAggregationInput:
    """Completed outputs from the three preceding Fraud Engine flows."""

    transaction_match: TransactionMatchResult
    duplicate_detection: DuplicateDetectionResult
    consistency: EvidenceConsistencyResult


@dataclass(frozen=True)
class EvidenceAggregationResult:
    """Final outcome plus all original upstream evidence."""

    status: AggregationStatus
    reasons: tuple[str, ...]
    findings: tuple[ConsistencyFinding, ...]
    transaction_match: TransactionMatchResult
    duplicate_detection: DuplicateDetectionResult
    consistency: EvidenceConsistencyResult
    blocking_conditions: tuple[str, ...]


_CONTRADICTION_CATEGORIES = frozenset(
    {
        FindingCategory.AMOUNT_CONTRADICTION,
        FindingCategory.CURRENCY_CONTRADICTION,
        FindingCategory.REFERENCE_CONTRADICTION,
        FindingCategory.TIMESTAMP_CONTRADICTION,
    }
)
_MANDATORY_FIELDS = frozenset({"amount", "currency"})
_IDENTITY_FIELDS = frozenset({"reference", "recipient", "timestamp"})


def _claim_supplied_fields(result: EvidenceConsistencyResult) -> set[str]:
    unavailable = set(result.unavailable_evidence)
    fields = set(_MANDATORY_FIELDS)
    fields.update(
        field
        for field in _IDENTITY_FIELDS
        if f"claim.{field}" not in unavailable
    )
    return fields


def _mandatory_evidence_blockers(
    consistency: EvidenceConsistencyResult,
) -> list[str]:
    mandatory_fields = _claim_supplied_fields(consistency)
    blockers: list[str] = []

    for field in sorted(mandatory_fields):
        if f"ocr.{field}" in consistency.unavailable_evidence:
            blockers.append(f"missing OCR evidence for mandatory field: {field}")

    for finding in consistency.findings:
        if finding.field not in mandatory_fields:
            continue
        if finding.category in {
            FindingCategory.OCR_FIELD_MISSING,
            FindingCategory.OCR_FIELD_UNREADABLE,
        }:
            blockers.append(f"unusable OCR evidence for mandatory field: {finding.field}")
        elif finding.category is FindingCategory.OCR_LOW_CONFIDENCE:
            blockers.append(f"low OCR confidence for mandatory field: {finding.field}")

    return blockers


def _risk_findings(findings: tuple[ConsistencyFinding, ...]) -> list[str]:
    reasons: list[str] = []
    for finding in findings:
        if (
            finding.category in _CONTRADICTION_CATEGORIES
            and finding.severity is FindingSeverity.HIGH
        ):
            reasons.append(finding.explanation)
        elif finding.category is FindingCategory.REPLAY_SIGNAL:
            reasons.append(finding.explanation)
    return reasons


def _verification_blockers(
    input_data: EvidenceAggregationInput,
) -> list[str]:
    blockers = _mandatory_evidence_blockers(input_data.consistency)

    if input_data.transaction_match.status is not MatchStatus.UNIQUE_MATCH:
        blockers.append(
            f"trusted transaction match status: "
            f"{input_data.transaction_match.status.value}"
        )

    duplicate_status = input_data.duplicate_detection.status
    if duplicate_status is not DuplicateStatus.NO_DUPLICATE:
        blockers.append(f"duplicate detection status: {duplicate_status.value}")

    if input_data.duplicate_detection.unavailable_checks:
        blockers.append("one or more duplicate checks were unavailable")

    for finding in input_data.consistency.findings:
        if finding.category in _CONTRADICTION_CATEGORIES:
            blockers.append(f"consistency contradiction: {finding.field}")
        elif finding.category in {
            FindingCategory.DUPLICATE_SIGNAL,
            FindingCategory.REPLAY_SIGNAL,
            FindingCategory.TRUSTED_RECORD_NOT_MATCHED,
            FindingCategory.TRUSTED_MATCH_AMBIGUOUS,
            FindingCategory.TRUSTED_MATCH_INSUFFICIENT,
            FindingCategory.DUPLICATE_CHECK_UNAVAILABLE,
        }:
            blockers.append(f"blocking finding: {finding.category.value}")

    return blockers


def aggregate_evidence(
    input_data: EvidenceAggregationInput,
) -> EvidenceAggregationResult:
    """Apply the deterministic final-decision policy to upstream evidence."""
    findings = input_data.consistency.findings
    risk_reasons = _risk_findings(findings)
    blocking_conditions = _verification_blockers(input_data)

    if risk_reasons:
        status = AggregationStatus.SUSPICIOUS
        reasons = tuple(risk_reasons)
    elif not blocking_conditions:
        status = AggregationStatus.VERIFIED
        reasons = (
            "Exactly one eligible trusted transaction matched and all mandatory "
            "verification checks passed.",
        )
    else:
        status = AggregationStatus.UNVERIFIED
        reasons = tuple(blocking_conditions)

    return EvidenceAggregationResult(
        status=status,
        reasons=reasons,
        findings=findings,
        transaction_match=input_data.transaction_match,
        duplicate_detection=input_data.duplicate_detection,
        consistency=input_data.consistency,
        blocking_conditions=tuple(blocking_conditions),
    )
