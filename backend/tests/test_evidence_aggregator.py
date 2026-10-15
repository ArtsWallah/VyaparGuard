from decimal import Decimal

from app.services.fraud_engine.duplicate_detector import (
    DuplicateDetectionResult,
    DuplicateStatus,
)
from app.services.fraud_engine.evidence_aggregator import (
    AggregationStatus,
    EvidenceAggregationInput,
    aggregate_evidence,
)
from app.services.fraud_engine.evidence_consistency import (
    ConsistencyFinding,
    EvidenceConsistencyResult,
    FindingCategory,
    FindingSeverity,
)
from app.services.fraud_engine.transaction_matcher import (
    MatchStatus,
    TransactionMatchResult,
)


def transaction_match(status=MatchStatus.UNIQUE_MATCH, **overrides):
    values = {
        "status": status,
        "matched_transaction_id": "txn-1" if status is MatchStatus.UNIQUE_MATCH else None,
        "candidate_count": 1 if status is MatchStatus.UNIQUE_MATCH else 0,
        "conflict_fields": (),
        "reasons": (),
    }
    values.update(overrides)
    return TransactionMatchResult(**values)


def duplicate_detection(status=DuplicateStatus.NO_DUPLICATE, **overrides):
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


def consistency(*findings, unavailable=(), compared=("amount", "currency", "reference")):
    return EvidenceConsistencyResult(
        findings=tuple(findings),
        compared_fields=tuple(compared),
        unavailable_evidence=tuple(unavailable),
    )


def finding(category, severity, field=None, evidence=()):
    return ConsistencyFinding(
        category=category,
        severity=severity,
        field=field,
        explanation=f"Explanation for {category.value}.",
        evidence=evidence,
    )


def aggregate(
    *,
    transaction=None,
    duplicate=None,
    consistency_result=None,
):
    return aggregate_evidence(
        EvidenceAggregationInput(
            transaction_match=transaction or transaction_match(),
            duplicate_detection=duplicate or duplicate_detection(),
            consistency=consistency_result or consistency(),
        )
    )


def test_complete_unique_consistent_evidence_is_verified():
    result = aggregate()

    assert result.status is AggregationStatus.VERIFIED
    assert result.blocking_conditions == ()


def test_screenshot_or_ocr_without_trusted_match_is_unverified():
    result = aggregate(transaction=transaction_match(MatchStatus.NO_MATCH))

    assert result.status is AggregationStatus.UNVERIFIED
    assert "NO_MATCH" in result.reasons[0]


def test_explicit_amount_contradiction_is_suspicious():
    result = aggregate(
        consistency_result=consistency(
            finding(
                FindingCategory.AMOUNT_CONTRADICTION,
                FindingSeverity.HIGH,
                "amount",
            )
        )
    )

    assert result.status is AggregationStatus.SUSPICIOUS


def test_explicit_reference_contradiction_is_suspicious():
    result = aggregate(
        consistency_result=consistency(
            finding(
                FindingCategory.REFERENCE_CONTRADICTION,
                FindingSeverity.HIGH,
                "reference",
            )
        )
    )

    assert result.status is AggregationStatus.SUSPICIOUS


def test_replay_is_suspicious_even_without_trusted_match():
    replay = finding(FindingCategory.REPLAY_SIGNAL, FindingSeverity.HIGH)
    result = aggregate(
        transaction=transaction_match(MatchStatus.NO_MATCH),
        consistency_result=consistency(replay),
    )

    assert result.status is AggregationStatus.SUSPICIOUS


def test_normal_duplicate_signal_blocks_verification_but_is_not_suspicious():
    result = aggregate(
        duplicate=duplicate_detection(DuplicateStatus.EXACT_IMAGE_REUSE),
        consistency_result=consistency(
            finding(FindingCategory.DUPLICATE_SIGNAL, FindingSeverity.MEDIUM)
        ),
    )

    assert result.status is AggregationStatus.UNVERIFIED


def test_missing_mandatory_ocr_field_is_unverified():
    result = aggregate(
        consistency_result=consistency(
            finding(
                FindingCategory.OCR_FIELD_MISSING,
                FindingSeverity.INFO,
                "amount",
            ),
            unavailable=("ocr.amount", "claim.recipient", "claim.timestamp"),
        )
    )

    assert result.status is AggregationStatus.UNVERIFIED
    assert any("amount" in reason for reason in result.reasons)


def test_optional_claim_fields_do_not_block_verification_when_absent():
    result = aggregate(
        consistency_result=consistency(
            unavailable=(
                "claim.recipient",
                "claim.timestamp",
                "ocr.confidence",
            )
        )
    )

    assert result.status is AggregationStatus.VERIFIED


def test_ambiguous_trusted_match_is_unverified():
    result = aggregate(
        transaction=transaction_match(
            MatchStatus.AMBIGUOUS_MATCH,
            candidate_count=2,
        )
    )

    assert result.status is AggregationStatus.UNVERIFIED


def test_insufficient_upstream_evidence_is_unverified():
    result = aggregate(
        transaction=transaction_match(MatchStatus.INSUFFICIENT_DATA),
        duplicate=duplicate_detection(
            DuplicateStatus.INSUFFICIENT_DATA,
            unavailable_checks=("image_sha256", "reference"),
        ),
        consistency_result=consistency(
            finding(
                FindingCategory.TRUSTED_MATCH_INSUFFICIENT,
                FindingSeverity.INFO,
            ),
            finding(
                FindingCategory.DUPLICATE_CHECK_UNAVAILABLE,
                FindingSeverity.INFO,
            ),
            unavailable=(
                "ocr.confidence",
                "claim.recipient",
                "claim.timestamp",
                "duplicate.image_sha256",
                "duplicate.reference",
            ),
        ),
    )

    assert result.status is AggregationStatus.UNVERIFIED


def test_multiple_findings_are_preserved_and_block_verification():
    amount = finding(FindingCategory.AMOUNT_CONTRADICTION, FindingSeverity.HIGH, "amount")
    low_confidence = finding(FindingCategory.OCR_LOW_CONFIDENCE, FindingSeverity.LOW, "amount")
    result = aggregate(consistency_result=consistency(amount, low_confidence))

    assert result.status is AggregationStatus.SUSPICIOUS
    assert result.findings == (amount, low_confidence)


def test_contradiction_takes_precedence_over_missing_evidence():
    contradiction = finding(
        FindingCategory.CURRENCY_CONTRADICTION,
        FindingSeverity.HIGH,
        "currency",
    )
    result = aggregate(
        consistency_result=consistency(
            contradiction,
            finding(FindingCategory.OCR_FIELD_MISSING, FindingSeverity.INFO, "amount"),
            unavailable=("ocr.amount", "claim.recipient", "claim.timestamp"),
        )
    )

    assert result.status is AggregationStatus.SUSPICIOUS
    assert len(result.findings) == 2


def test_replay_takes_precedence_over_normal_duplicate_signal_without_duplicates():
    replay = finding(FindingCategory.REPLAY_SIGNAL, FindingSeverity.HIGH)
    duplicate = finding(FindingCategory.DUPLICATE_SIGNAL, FindingSeverity.MEDIUM)
    result = aggregate(
        duplicate=duplicate_detection(DuplicateStatus.REPLAY_SUSPECTED),
        consistency_result=consistency(replay, duplicate),
    )

    assert result.status is AggregationStatus.SUSPICIOUS
    assert result.findings == (replay, duplicate)
    assert sum(f.category is FindingCategory.REPLAY_SIGNAL for f in result.findings) == 1


def test_upstream_objects_and_explanations_are_preserved():
    match = transaction_match(
        MatchStatus.AMOUNT_CONFLICT,
        conflict_fields=("amount",),
        reasons=("trusted source conflict",),
    )
    duplicate = duplicate_detection(
        DuplicateStatus.REFERENCE_REUSE,
        matched_claim_ids=("claim-previous",),
    )
    original_finding = finding(
        FindingCategory.AMOUNT_CONTRADICTION,
        FindingSeverity.HIGH,
        "amount",
        evidence=(("source", "matcher"),),
    )
    result = aggregate(
        transaction=match,
        duplicate=duplicate,
        consistency_result=consistency(original_finding),
    )

    assert result.status is AggregationStatus.SUSPICIOUS
    assert result.transaction_match is match
    assert result.duplicate_detection is duplicate
    assert result.findings == (original_finding,)
    assert result.findings[0].evidence == (("source", "matcher"),)


def test_identical_inputs_produce_deterministic_results():
    input_result = consistency(
        unavailable=("claim.recipient", "claim.timestamp", "ocr.confidence")
    )
    first = aggregate(consistency_result=input_result)
    second = aggregate(consistency_result=input_result)

    assert first == second


def test_screenshot_alone_can_never_be_verified():
    result = aggregate(
        transaction=transaction_match(MatchStatus.NO_MATCH),
        consistency_result=consistency(
            unavailable=("ocr.amount", "ocr.currency", "ocr.reference")
        ),
    )

    assert result.status is AggregationStatus.UNVERIFIED


def test_low_confidence_optional_field_does_not_make_suspicious():
    result = aggregate(
        consistency_result=consistency(
            finding(FindingCategory.OCR_LOW_CONFIDENCE, FindingSeverity.LOW, "recipient"),
            unavailable=("claim.recipient", "claim.timestamp", "ocr.confidence"),
        )
    )

    assert result.status is AggregationStatus.VERIFIED
