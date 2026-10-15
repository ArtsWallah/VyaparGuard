"""Match payment claims against trusted incoming transactions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Iterable, Protocol


class MatchStatus(str, Enum):
    """Outcome of comparing a claim with trusted transaction records."""

    UNIQUE_MATCH = "UNIQUE_MATCH"
    NO_MATCH = "NO_MATCH"
    AMOUNT_CONFLICT = "AMOUNT_CONFLICT"
    REFERENCE_CONFLICT = "REFERENCE_CONFLICT"
    AMBIGUOUS_MATCH = "AMBIGUOUS_MATCH"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


@dataclass(frozen=True)
class PaymentClaim:
    """Untrusted claim fields extracted from a payment request or image."""

    amount: Decimal | None = None
    currency: str | None = None
    reference: str | None = None
    recipient: str | None = None
    timestamp: datetime | None = None


@dataclass(frozen=True)
class TrustedTransaction:
    """A transaction record returned by a trusted source."""

    transaction_id: str
    amount: Decimal | None
    currency: str | None
    reference: str | None
    recipient: str | None
    timestamp: datetime | None
    direction: str
    status: str


class TrustedTransactionSource(Protocol):
    """Interface implemented by in-memory and persistent record sources."""

    def iter_incoming_credits(self) -> Iterable[TrustedTransaction]:
        """Yield trusted records that may be considered by the matcher."""


@dataclass(frozen=True)
class InMemoryTrustedTransactionSource:
    """Simple source for deterministic tests and local use."""

    transactions: tuple[TrustedTransaction, ...]

    def __init__(self, transactions: Iterable[TrustedTransaction]):
        object.__setattr__(self, "transactions", tuple(transactions))

    def iter_incoming_credits(self) -> Iterable[TrustedTransaction]:
        return iter(self.transactions)


@dataclass(frozen=True)
class TransactionMatchResult:
    """Explainable matching outcome; this is not a payment verdict."""

    status: MatchStatus
    matched_transaction_id: str | None
    candidate_count: int
    conflict_fields: tuple[str, ...]
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class _NormalizedClaim:
    amount: Decimal
    currency: str
    reference: str | None
    recipient: str | None
    timestamp: datetime | None
    identifying_fields: tuple[str, ...]


@dataclass(frozen=True)
class _NormalizedTransaction:
    transaction: TrustedTransaction
    amount: Decimal | None
    currency: str | None
    reference: str | None
    recipient: str | None
    timestamp: datetime | None


def _normalize_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().casefold()
    return normalized or None


def _to_decimal(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        decimal_value = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return decimal_value if decimal_value.is_finite() else None


def _normalize_timestamp(value: object) -> datetime | None:
    if value is None or not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    try:
        return value.astimezone(timezone.utc)
    except (OverflowError, ValueError):
        return None


def _invalid_supplied_fields(claim: PaymentClaim) -> list[str]:
    invalid_fields = []
    if claim.amount is not None and _to_decimal(claim.amount) is None:
        invalid_fields.append("amount")
    if claim.currency is not None and _normalize_text(claim.currency) is None:
        invalid_fields.append("currency")
    for field_name in ("reference", "recipient"):
        value = getattr(claim, field_name)
        if value is not None and _normalize_text(value) is None:
            invalid_fields.append(field_name)
    if claim.timestamp is not None and _normalize_timestamp(claim.timestamp) is None:
        invalid_fields.append("timestamp")
    return invalid_fields


def _normalize_claim(claim: PaymentClaim) -> _NormalizedClaim | None:
    amount = _to_decimal(claim.amount)
    currency = _normalize_text(claim.currency)
    reference = _normalize_text(claim.reference)
    recipient = _normalize_text(claim.recipient)
    timestamp = _normalize_timestamp(claim.timestamp)
    identifying_fields = tuple(
        field_name
        for field_name, value in (
            ("reference", reference),
            ("recipient", recipient),
            ("timestamp", timestamp),
        )
        if value is not None
    )
    if amount is None or currency is None or not identifying_fields:
        return None
    return _NormalizedClaim(
        amount=amount,
        currency=currency,
        reference=reference,
        recipient=recipient,
        timestamp=timestamp,
        identifying_fields=identifying_fields,
    )


def _normalize_transaction(
    transaction: TrustedTransaction,
) -> _NormalizedTransaction:
    return _NormalizedTransaction(
        transaction=transaction,
        amount=_to_decimal(transaction.amount),
        currency=_normalize_text(transaction.currency),
        reference=_normalize_text(transaction.reference),
        recipient=_normalize_text(transaction.recipient),
        timestamp=_normalize_timestamp(transaction.timestamp),
    )


def _is_eligible(transaction: TrustedTransaction) -> bool:
    return (
        isinstance(transaction.direction, str)
        and isinstance(transaction.status, str)
        and transaction.direction.casefold() == "incoming"
        and transaction.status.casefold() == "settled"
    )


def _timestamp_matches(
    claim_timestamp: datetime,
    transaction_timestamp: datetime | None,
    tolerance: timedelta,
) -> bool:
    if transaction_timestamp is None:
        return False
    return abs(claim_timestamp - transaction_timestamp) <= tolerance


def _matching_fields(
    claim: _NormalizedClaim,
    transaction: _NormalizedTransaction,
    timestamp_tolerance: timedelta,
) -> tuple[set[str], set[str]]:
    matches: set[str] = set()
    conflicts: set[str] = set()

    if transaction.amount is not None and transaction.amount == claim.amount:
        matches.add("amount")
    elif transaction.amount is not None:
        conflicts.add("amount")

    if transaction.currency == claim.currency:
        matches.add("currency")
    elif transaction.currency is not None:
        conflicts.add("currency")

    if claim.reference is not None:
        if transaction.reference == claim.reference:
            matches.add("reference")
        elif transaction.reference is not None:
            conflicts.add("reference")

    if claim.recipient is not None:
        if transaction.recipient == claim.recipient:
            matches.add("recipient")
        elif transaction.recipient is not None:
            conflicts.add("recipient")

    if claim.timestamp is not None:
        if _timestamp_matches(
            claim.timestamp,
            transaction.timestamp,
            timestamp_tolerance,
        ):
            matches.add("timestamp")
        elif transaction.timestamp is not None:
            conflicts.add("timestamp")

    return matches, conflicts


def _has_reliable_reference_conflict(
    claim: _NormalizedClaim,
    transaction: _NormalizedTransaction,
    matches: set[str],
    conflicts: set[str],
) -> bool:
    return (
        claim.reference is not None
        and "reference" in conflicts
        and "amount" in matches
        and bool(
            {"recipient", "timestamp"}.intersection(matches)
        )
    )


def _has_reliable_amount_conflict(
    claim: _NormalizedClaim,
    matches: set[str],
    conflicts: set[str],
) -> bool:
    return (
        "amount" in conflicts
        and (
            "reference" in matches
            or {"recipient", "timestamp"}.issubset(matches)
        )
    )


def match_transaction(
    claim: PaymentClaim,
    source: TrustedTransactionSource,
    timestamp_tolerance: timedelta = timedelta(minutes=5),
) -> TransactionMatchResult:
    """Match one claim against eligible trusted incoming-credit records."""
    if timestamp_tolerance < timedelta(0):
        raise ValueError("timestamp_tolerance must not be negative.")

    invalid_fields = _invalid_supplied_fields(claim)
    if invalid_fields:
        return TransactionMatchResult(
            status=MatchStatus.INSUFFICIENT_DATA,
            matched_transaction_id=None,
            candidate_count=0,
            conflict_fields=tuple(invalid_fields),
            reasons=(
                "Supplied fields are invalid or unreadable: "
                + ", ".join(invalid_fields)
                + ".",
            ),
        )

    normalized_claim = _normalize_claim(claim)
    if normalized_claim is None:
        return TransactionMatchResult(
            status=MatchStatus.INSUFFICIENT_DATA,
            matched_transaction_id=None,
            candidate_count=0,
            conflict_fields=(),
            reasons=(
                "Amount, currency, and at least one usable identifying "
                "field are required.",
            ),
        )

    eligible_records = [
        _normalize_transaction(transaction)
        for transaction in source.iter_incoming_credits()
        if _is_eligible(transaction)
    ]

    matching_records: list[_NormalizedTransaction] = []
    amount_conflict = False
    reference_conflict = False
    conflict_fields: set[str] = set()

    for transaction in eligible_records:
        matches, conflicts = _matching_fields(
            normalized_claim,
            transaction,
            timestamp_tolerance,
        )
        required_matches = {
            "amount",
            "currency",
            *normalized_claim.identifying_fields,
        }
        if required_matches.issubset(matches) and not conflicts:
            matching_records.append(transaction)
            continue

        if _has_reliable_amount_conflict(
            normalized_claim,
            matches,
            conflicts,
        ):
            amount_conflict = True
            conflict_fields.add("amount")
        if _has_reliable_reference_conflict(
            normalized_claim,
            transaction,
            matches,
            conflicts,
        ):
            reference_conflict = True
            conflict_fields.add("reference")

    if len(matching_records) == 1:
        return TransactionMatchResult(
            status=MatchStatus.UNIQUE_MATCH,
            matched_transaction_id=matching_records[0].transaction.transaction_id,
            candidate_count=1,
            conflict_fields=(),
            reasons=("Exactly one eligible trusted record matched all supplied fields.",),
        )

    if len(matching_records) > 1:
        return TransactionMatchResult(
            status=MatchStatus.AMBIGUOUS_MATCH,
            matched_transaction_id=None,
            candidate_count=len(matching_records),
            conflict_fields=(),
            reasons=(
                "More than one eligible trusted record matched all supplied fields.",
            ),
        )

    if amount_conflict:
        status = MatchStatus.AMOUNT_CONFLICT
    elif reference_conflict:
        status = MatchStatus.REFERENCE_CONFLICT
    else:
        status = MatchStatus.NO_MATCH

    return TransactionMatchResult(
        status=status,
        matched_transaction_id=None,
        candidate_count=0,
        conflict_fields=tuple(sorted(conflict_fields)),
        reasons=(
            "No eligible trusted record satisfied all supplied claim fields.",
        ),
    )
