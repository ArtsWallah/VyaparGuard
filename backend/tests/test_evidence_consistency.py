from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.services.fraud_engine.duplicate_detector import (
    DuplicateDetectionResult,
    DuplicateStatus,
)
from app.services.fraud_engine.evidence_consistency import (
    DEFAULT_OCR_CONFIDENCE_THRESHOLD,
    EvidenceConsistencyInput,
    FindingCategory,
    FindingSeverity,
    evaluate_consistency,
)
from app.services.fraud_engine.transaction_matcher import (
    MatchStatus,
    PaymentClaim,
    TransactionMatchResult,
)


TIMESTAMP = datetime(2026, 10, 15, 12, 0, tzinfo=timezone.utc)


def match_result(status=MatchStatus.UNIQUE_MATCH, **overrides):
    values = {
        "status": status,
        "matched_transaction_id": "txn-1" if status is MatchStatus.UNIQUE_MATCH else None,
        "candidate_count": 1 if status is MatchStatus.UNIQUE_MATCH else 0,
        "conflict_fields": (),
        "reasons": (),
    }
    values.update(overrides)
    return TransactionMatchResult(**values)


def duplicate_result(status=DuplicateStatus.NO_DUPLICATE, **overrides):
    values = {
        "status": status,
        "signals": (),
        "matched_claim_ids": (),
        "exact_image_claim_ids": (),
        "similar_image_claim_ids": (),
        "reference_claim_ids": (),
        "unavailable_checks": (),
        "reasons": (),
    }
    values.update(overrides)
    return DuplicateDetectionResult(**values)


def evaluate(
    *,
    claim=None,
    ocr=None,
    transaction_match=None,
    duplicate_detection=None,
    **overrides,
):
    claim = claim or PaymentClaim(
        amount=Decimal("500.00"),
        currency="INR",
        reference="UPI-123456",
        timestamp=TIMESTAMP,
    )
    return evaluate_consistency(
        EvidenceConsistencyInput(
            claim=claim,
            ocr=ocr,
            transaction_match=transaction_match or match_result(),
            duplicate_detection=duplicate_detection or duplicate_result(),
            **overrides,
        )
    )


def findings(result, category):
    return [finding for finding in result.findings if finding.category is category]


def test_agreeing_claim_and_ocr_amount_has_no_amount_finding():
    result = evaluate(ocr={"amount": 500.0, "currency": "INR", "reference": "UPI-123456", "timestamp": TIMESTAMP.isoformat(), "confidence": 0.95})

    assert findings(result, FindingCategory.AMOUNT_CONTRADICTION) == []
    assert "amount" in result.compared_fields


def test_conflicting_amount_is_high_severity():
    result = evaluate(ocr={"amount": "501.00", "currency": "INR", "reference": "UPI-123456", "timestamp": TIMESTAMP.isoformat()})

    amount_findings = findings(result, FindingCategory.AMOUNT_CONTRADICTION)
    assert len(amount_findings) == 1
    assert amount_findings[0].severity is FindingSeverity.HIGH


def test_currency_conflict_is_reported():
    result = evaluate(ocr={"amount": "500.00", "currency": "USD", "reference": "UPI-123456", "timestamp": TIMESTAMP.isoformat()})

    assert len(findings(result, FindingCategory.CURRENCY_CONTRADICTION)) == 1


def test_reference_conflict_is_reported():
    result = evaluate(ocr={"amount": "500.00", "currency": "INR", "reference": "UPI-999999", "timestamp": TIMESTAMP.isoformat()})

    assert len(findings(result, FindingCategory.REFERENCE_CONTRADICTION)) == 1


def test_timestamp_within_tolerance_agrees():
    result = evaluate(
        ocr={
            "amount": "500.00",
            "currency": "INR",
            "reference": "UPI-123456",
            "timestamp": (TIMESTAMP + timedelta(minutes=5)).isoformat(),
        }
    )

    assert findings(result, FindingCategory.TIMESTAMP_CONTRADICTION) == []


def test_timestamp_beyond_tolerance_conflicts():
    result = evaluate(
        ocr={
            "amount": "500.00",
            "currency": "INR",
            "reference": "UPI-123456",
            "timestamp": (TIMESTAMP + timedelta(minutes=6)).isoformat(),
        }
    )

    assert len(findings(result, FindingCategory.TIMESTAMP_CONTRADICTION)) == 1


def test_configured_timestamp_tolerance_is_used():
    result = evaluate(
        ocr={"timestamp": (TIMESTAMP + timedelta(minutes=6)).isoformat()},
        timestamp_tolerance=timedelta(minutes=10),
    )

    assert findings(result, FindingCategory.TIMESTAMP_CONTRADICTION) == []


def test_naive_ocr_timestamp_is_interpreted_as_utc():
    result = evaluate(ocr={"timestamp": "2026-10-15T12:00:00"})

    assert findings(result, FindingCategory.TIMESTAMP_CONTRADICTION) == []


def test_date_only_ocr_timestamp_is_unreadable():
    result = evaluate(ocr={"timestamp": "2026-10-15"})

    unreadable = findings(result, FindingCategory.OCR_FIELD_UNREADABLE)
    assert len(unreadable) == 1
    assert unreadable[0].field == "timestamp"


def test_missing_ocr_fields_are_not_contradictions():
    result = evaluate(ocr={})

    assert len(findings(result, FindingCategory.OCR_FIELD_MISSING)) == 4
    assert findings(result, FindingCategory.AMOUNT_CONTRADICTION) == []


def test_unreadable_ocr_amount_is_distinguished_from_conflict():
    result = evaluate(ocr={"amount": "unknown"})

    assert len(findings(result, FindingCategory.OCR_FIELD_UNREADABLE)) == 1
    assert findings(result, FindingCategory.AMOUNT_CONTRADICTION) == []


def test_low_confidence_ocr_is_reported_using_configured_threshold():
    result = evaluate(ocr={"confidence": 0.69})

    low_confidence = findings(result, FindingCategory.OCR_LOW_CONFIDENCE)
    assert len(low_confidence) == 1
    assert low_confidence[0].severity is FindingSeverity.LOW
    assert DEFAULT_OCR_CONFIDENCE_THRESHOLD == 0.70


def test_missing_confidence_is_unavailable_not_invented():
    result = evaluate(ocr={"amount": "500.00"})

    assert findings(result, FindingCategory.OCR_LOW_CONFIDENCE) == []
    assert "ocr.confidence" in result.unavailable_evidence


def test_unique_trusted_match_has_no_trusted_issue():
    result = evaluate(ocr=None, transaction_match=match_result())

    assert findings(result, FindingCategory.TRUSTED_RECORD_NOT_MATCHED) == []
    assert findings(result, FindingCategory.TRUSTED_MATCH_INSUFFICIENT) == []


def test_no_trusted_match_is_informational_only():
    result = evaluate(
        ocr=None,
        transaction_match=match_result(
            MatchStatus.NO_MATCH,
            reasons=("No eligible record.",),
        ),
    )

    trusted = findings(result, FindingCategory.TRUSTED_RECORD_NOT_MATCHED)
    assert len(trusted) == 1
    assert trusted[0].severity is FindingSeverity.INFO
    assert ("status", MatchStatus.NO_MATCH.value) in trusted[0].evidence


def test_matcher_amount_conflict_preserves_upstream_evidence():
    result = evaluate(
        ocr=None,
        transaction_match=match_result(
            MatchStatus.AMOUNT_CONFLICT,
            conflict_fields=("amount",),
            reasons=("trusted reason",),
        ),
    )

    amount_findings = findings(result, FindingCategory.AMOUNT_CONTRADICTION)
    assert len(amount_findings) == 1
    assert amount_findings[0].severity is FindingSeverity.HIGH
    assert ("status", MatchStatus.AMOUNT_CONFLICT.value) in amount_findings[0].evidence
    assert ("reasons", ("trusted reason",)) in amount_findings[0].evidence


def test_matcher_reference_conflict_is_high_severity():
    result = evaluate(
        ocr=None,
        transaction_match=match_result(MatchStatus.REFERENCE_CONFLICT),
    )

    reference_findings = findings(result, FindingCategory.REFERENCE_CONTRADICTION)
    assert len(reference_findings) == 1
    assert reference_findings[0].severity is FindingSeverity.HIGH


def test_duplicate_signal_with_consistent_evidence_is_not_a_contradiction():
    result = evaluate(
        ocr=None,
        duplicate_detection=duplicate_result(
            DuplicateStatus.EXACT_IMAGE_REUSE,
            signals=("EXACT_IMAGE_REUSE",),
            matched_claim_ids=("claim-1",),
            exact_image_claim_ids=("claim-1",),
        ),
    )

    duplicate_findings = findings(result, FindingCategory.DUPLICATE_SIGNAL)
    assert len(duplicate_findings) == 1
    assert duplicate_findings[0].severity is FindingSeverity.MEDIUM
    assert findings(result, FindingCategory.REPLAY_SIGNAL) == []


def test_replay_emits_one_signal_with_underlying_evidence():
    result = evaluate(
        ocr=None,
        duplicate_detection=duplicate_result(
            DuplicateStatus.REPLAY_SUSPECTED,
            signals=("EXACT_IMAGE_REUSE", "REFERENCE_REUSE", "REPLAY_SUSPECTED"),
            matched_claim_ids=("claim-1",),
            exact_image_claim_ids=("claim-1",),
            reference_claim_ids=("claim-1",),
        ),
    )

    assert len(findings(result, FindingCategory.REPLAY_SIGNAL)) == 1
    assert findings(result, FindingCategory.DUPLICATE_SIGNAL) == []
    assert findings(result, FindingCategory.REPLAY_SIGNAL)[0].severity is FindingSeverity.HIGH


def test_duplicate_insufficient_data_is_reported_as_unavailable():
    result = evaluate(
        ocr=None,
        duplicate_detection=duplicate_result(
            DuplicateStatus.INSUFFICIENT_DATA,
            unavailable_checks=("image_sha256", "reference"),
        ),
    )

    unavailable = findings(result, FindingCategory.DUPLICATE_CHECK_UNAVAILABLE)
    assert len(unavailable) == 1
    assert "duplicate.image_sha256" in result.unavailable_evidence


def test_multiple_contradictions_are_returned_together():
    result = evaluate(
        ocr={
            "amount": "501.00",
            "currency": "USD",
            "reference": "UPI-999999",
            "timestamp": (TIMESTAMP + timedelta(minutes=6)).isoformat(),
        }
    )

    categories = {finding.category for finding in result.findings}
    assert FindingCategory.AMOUNT_CONTRADICTION in categories
    assert FindingCategory.CURRENCY_CONTRADICTION in categories
    assert FindingCategory.REFERENCE_CONTRADICTION in categories
    assert FindingCategory.TIMESTAMP_CONTRADICTION in categories


def test_insufficient_evidence_has_no_final_fraud_verdict():
    result = evaluate(
        ocr=None,
        transaction_match=match_result(MatchStatus.INSUFFICIENT_DATA),
        duplicate_detection=duplicate_result(
            DuplicateStatus.INSUFFICIENT_DATA,
            unavailable_checks=("image_sha256", "image_phash", "reference"),
        ),
    )

    assert not any(
        verdict in {"VERIFIED", "SUSPICIOUS", "UNVERIFIED"}
        for finding in result.findings
        for verdict in (finding.category.value, finding.explanation)
    )


def test_nested_payment_analyzer_ocr_shape_is_supported():
    result = evaluate(
        ocr={
            "ocr": {
                "amount": 500,
                "currency": "INR",
                "reference": "UPI-123456",
                "timestamp": TIMESTAMP.isoformat(),
            }
        }
    )

    assert findings(result, FindingCategory.AMOUNT_CONTRADICTION) == []
