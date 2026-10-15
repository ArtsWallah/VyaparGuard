from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.services.fraud_engine.transaction_matcher import (
    InMemoryTrustedTransactionSource,
    MatchStatus,
    PaymentClaim,
    TrustedTransaction,
    match_transaction,
)


TIMESTAMP = datetime(2026, 10, 15, 12, 0, tzinfo=timezone.utc)


def transaction(**overrides) -> TrustedTransaction:
    values = {
        "transaction_id": "txn-1",
        "amount": Decimal("500.00"),
        "currency": "INR",
        "reference": "UPI-123456",
        "recipient": "Demo Merchant",
        "timestamp": TIMESTAMP,
        "direction": "INCOMING",
        "status": "SETTLED",
    }
    values.update(overrides)
    return TrustedTransaction(**values)


def claim(**overrides) -> PaymentClaim:
    values = {
        "amount": Decimal("500.00"),
        "currency": "inr",
        "reference": " upi-123456 ",
        "recipient": " Demo Merchant ",
        "timestamp": TIMESTAMP,
    }
    values.update(overrides)
    return PaymentClaim(**values)


def match(claim_value: PaymentClaim, *records: TrustedTransaction):
    source = InMemoryTrustedTransactionSource(records)
    return match_transaction(claim_value, source)


def test_returns_unique_match_for_all_supplied_fields():
    result = match(claim(), transaction())

    assert result.status is MatchStatus.UNIQUE_MATCH
    assert result.matched_transaction_id == "txn-1"
    assert result.candidate_count == 1


def test_returns_no_match_when_no_record_satisfies_claim():
    result = match(
        claim(reference=None, recipient="Other Merchant"),
        transaction(),
    )

    assert result.status is MatchStatus.NO_MATCH
    assert result.matched_transaction_id is None


def test_returns_amount_conflict_only_for_reliably_identified_record():
    result = match(
        claim(),
        transaction(amount=Decimal("700.00")),
    )

    assert result.status is MatchStatus.AMOUNT_CONFLICT
    assert result.conflict_fields == ("amount",)


def test_returns_reference_conflict_only_with_another_matching_identity():
    result = match(
        claim(reference="UPI-999999"),
        transaction(reference="UPI-123456"),
    )

    assert result.status is MatchStatus.REFERENCE_CONFLICT
    assert result.conflict_fields == ("reference",)


def test_unrelated_amount_differences_do_not_become_amount_conflicts():
    result = match(
        claim(reference="UPI-MISSING", recipient=None, timestamp=None),
        transaction(amount=Decimal("700.00")),
    )

    assert result.status is MatchStatus.NO_MATCH
    assert result.conflict_fields == ()


def test_returns_ambiguous_match_for_duplicate_eligible_records():
    result = match(
        claim(),
        transaction(transaction_id="txn-1"),
        transaction(transaction_id="txn-2"),
    )

    assert result.status is MatchStatus.AMBIGUOUS_MATCH
    assert result.matched_transaction_id is None
    assert result.candidate_count == 2


def test_excludes_outgoing_pending_failed_and_reversed_records():
    result = match(
        claim(),
        transaction(direction="OUTGOING"),
        transaction(status="PENDING"),
        transaction(status="FAILED"),
        transaction(status="REVERSED"),
    )

    assert result.status is MatchStatus.NO_MATCH


def test_requires_amount_currency_and_an_identifying_field():
    result = match(
        PaymentClaim(amount=Decimal("500.00"), currency="INR"),
        transaction(),
    )

    assert result.status is MatchStatus.INSUFFICIENT_DATA
    assert result.matched_transaction_id is None


def test_does_not_fabricate_missing_trusted_fields():
    result = match(
        claim(reference="UPI-123456"),
        transaction(reference=None),
    )

    assert result.status is MatchStatus.NO_MATCH


def test_does_not_ignore_conflicting_recipient():
    result = match(claim(), transaction(recipient="Other Merchant"))

    assert result.status is MatchStatus.NO_MATCH


def test_timestamp_must_be_within_configured_tolerance():
    result = match(
        claim(reference=None, recipient=None),
        transaction(
            reference=None,
            recipient=None,
            timestamp=TIMESTAMP + timedelta(minutes=6),
        ),
    )

    assert result.status is MatchStatus.NO_MATCH


def test_timestamp_at_tolerance_boundary_matches():
    result = match(
        claim(reference=None, recipient=None),
        transaction(
            reference=None,
            recipient=None,
            timestamp=TIMESTAMP + timedelta(minutes=5),
        ),
    )

    assert result.status is MatchStatus.UNIQUE_MATCH


def test_naive_and_aware_timestamps_are_compared_as_utc():
    result = match(
        claim(reference=None, recipient=None, timestamp=TIMESTAMP.replace(tzinfo=None)),
        transaction(
            reference=None,
            recipient=None,
            timestamp=TIMESTAMP,
        ),
    )

    assert result.status is MatchStatus.UNIQUE_MATCH


def test_invalid_claim_timestamp_is_insufficient_data():
    result = match(claim(timestamp="not-a-timestamp"))

    assert result.status is MatchStatus.INSUFFICIENT_DATA
    assert "timestamp" in result.conflict_fields


def test_invalid_claim_amount_is_insufficient_data():
    result = match(claim(amount="not-an-amount"))

    assert result.status is MatchStatus.INSUFFICIENT_DATA
    assert "amount" in result.conflict_fields


def test_negative_timestamp_tolerance_is_rejected():
    with pytest.raises(ValueError, match="must not be negative"):
        match_transaction(
            claim(),
            InMemoryTrustedTransactionSource([transaction()]),
            timestamp_tolerance=timedelta(seconds=-1),
        )


def test_matcher_never_returns_verified():
    result = match(claim(), transaction())

    assert "VERIFIED" not in {result.status.value}
