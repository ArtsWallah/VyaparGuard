"""Detect duplicate images, reused references, and replay-like claims."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Iterable, Protocol


DEFAULT_PHASH_DISTANCE_THRESHOLD = 8

EXACT_IMAGE_REUSE = "EXACT_IMAGE_REUSE"
SIMILAR_IMAGE_REUSE = "SIMILAR_IMAGE_REUSE"
REFERENCE_REUSE = "REFERENCE_REUSE"
REPLAY_SUSPECTED = "REPLAY_SUSPECTED"


class DuplicateStatus(str, Enum):
    """Primary outcome of duplicate-history comparison."""

    NO_DUPLICATE = "NO_DUPLICATE"
    EXACT_IMAGE_REUSE = EXACT_IMAGE_REUSE
    SIMILAR_IMAGE_REUSE = SIMILAR_IMAGE_REUSE
    REFERENCE_REUSE = REFERENCE_REUSE
    REPLAY_SUSPECTED = REPLAY_SUSPECTED
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


@dataclass(frozen=True)
class DuplicateClaim:
    """Claim metadata supplied for duplicate and replay checks."""

    claim_id: str
    image_sha256: str | None = None
    image_phash: str | None = None
    reference: str | None = None


@dataclass(frozen=True)
class PriorClaim:
    """Stored claim metadata; raw screenshot bytes are never retained."""

    claim_id: str
    image_sha256: str | None = None
    image_phash: str | None = None
    reference: str | None = None
    created_at: datetime | None = None


class PriorClaimHistory(Protocol):
    """Interface for in-memory or persistent prior-claim history."""

    def iter_prior_claims(self) -> Iterable[PriorClaim]:
        """Yield prior claims available to the detector."""


@dataclass(frozen=True)
class InMemoryPriorClaimHistory:
    """Deterministic prior-claim source for unit tests."""

    claims: tuple[PriorClaim, ...]

    def __init__(self, claims: Iterable[PriorClaim]):
        object.__setattr__(self, "claims", tuple(claims))

    def iter_prior_claims(self) -> Iterable[PriorClaim]:
        return iter(self.claims)


@dataclass(frozen=True)
class DuplicateDetectionResult:
    """Explainable duplicate signals, not a final payment verdict."""

    status: DuplicateStatus
    signals: tuple[str, ...]
    matched_claim_ids: tuple[str, ...]
    exact_image_claim_ids: tuple[str, ...]
    similar_image_claim_ids: tuple[str, ...]
    reference_claim_ids: tuple[str, ...]
    unavailable_checks: tuple[str, ...]
    reasons: tuple[str, ...]


def _normalize_reference(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().casefold()
    return normalized or None


def _validate_hash(value: str | None, field_name: str, length: int) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a hexadecimal string.")
    normalized = value.strip().casefold()
    if len(normalized) != length:
        raise ValueError(
            f"{field_name} must contain exactly {length} hexadecimal characters."
        )
    if any(character not in "0123456789abcdef" for character in normalized):
        raise ValueError(f"{field_name} contains non-hexadecimal characters.")
    return normalized


def _valid_prior_hash(value: str | None, length: int) -> str | None:
    try:
        return _validate_hash(value, "prior claim hash", length)
    except ValueError:
        return None


def _hamming_distance(first: str, second: str) -> int:
    return (int(first, 16) ^ int(second, 16)).bit_count()


def _append_unique(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)


def detect_duplicates(
    claim: DuplicateClaim,
    history: PriorClaimHistory,
    phash_distance_threshold: int = DEFAULT_PHASH_DISTANCE_THRESHOLD,
) -> DuplicateDetectionResult:
    """Compare a claim with prior claims without assigning a payment verdict."""
    if (
        isinstance(phash_distance_threshold, bool)
        or not isinstance(phash_distance_threshold, int)
        or phash_distance_threshold < 0
    ):
        raise ValueError("phash_distance_threshold must be a non-negative integer.")

    image_sha256 = _validate_hash(claim.image_sha256, "image_sha256", 64)
    image_phash = _validate_hash(claim.image_phash, "image_phash", 16)
    reference = _normalize_reference(claim.reference)

    unavailable_checks = tuple(
        check_name
        for check_name, value in (
            ("image_sha256", image_sha256),
            ("image_phash", image_phash),
            ("reference", reference),
        )
        if value is None
    )
    if len(unavailable_checks) == 3:
        return DuplicateDetectionResult(
            status=DuplicateStatus.INSUFFICIENT_DATA,
            signals=(),
            matched_claim_ids=(),
            exact_image_claim_ids=(),
            similar_image_claim_ids=(),
            reference_claim_ids=(),
            unavailable_checks=unavailable_checks,
            reasons=("All duplicate checks are unavailable.",),
        )

    exact_image_claim_ids: list[str] = []
    similar_image_claim_ids: list[str] = []
    reference_claim_ids: list[str] = []
    matched_claim_ids: list[str] = []

    for prior_claim in history.iter_prior_claims():
        if prior_claim.claim_id == claim.claim_id:
            continue

        prior_sha256 = _valid_prior_hash(prior_claim.image_sha256, 64)
        prior_phash = _valid_prior_hash(prior_claim.image_phash, 16)
        prior_reference = _normalize_reference(prior_claim.reference)
        matched_this_claim = False

        if image_sha256 is not None and prior_sha256 == image_sha256:
            _append_unique(exact_image_claim_ids, prior_claim.claim_id)
            matched_this_claim = True

        if (
            image_phash is not None
            and prior_phash is not None
            and _hamming_distance(image_phash, prior_phash)
            <= phash_distance_threshold
        ):
            _append_unique(similar_image_claim_ids, prior_claim.claim_id)
            matched_this_claim = True

        if reference is not None and prior_reference == reference:
            _append_unique(reference_claim_ids, prior_claim.claim_id)
            matched_this_claim = True

        if matched_this_claim:
            _append_unique(matched_claim_ids, prior_claim.claim_id)

    signals: list[str] = []
    if exact_image_claim_ids:
        signals.append(EXACT_IMAGE_REUSE)
    if similar_image_claim_ids:
        signals.append(SIMILAR_IMAGE_REUSE)
    if reference_claim_ids:
        signals.append(REFERENCE_REUSE)

    image_claim_ids = set(exact_image_claim_ids) | set(similar_image_claim_ids)
    same_claim_has_reference_and_image = bool(
        image_claim_ids.intersection(reference_claim_ids)
    )
    replay_suspected = same_claim_has_reference_and_image or len(reference_claim_ids) > 1
    if replay_suspected:
        signals.append(REPLAY_SUSPECTED)

    if replay_suspected:
        status = DuplicateStatus.REPLAY_SUSPECTED
    elif exact_image_claim_ids:
        status = DuplicateStatus.EXACT_IMAGE_REUSE
    elif similar_image_claim_ids:
        status = DuplicateStatus.SIMILAR_IMAGE_REUSE
    elif reference_claim_ids:
        status = DuplicateStatus.REFERENCE_REUSE
    else:
        status = DuplicateStatus.NO_DUPLICATE

    if status is DuplicateStatus.NO_DUPLICATE:
        reasons = ("No duplicate evidence was found in prior claims.",)
    else:
        reasons = (
            "Prior claim history contains one or more duplicate or replay signals.",
        )

    return DuplicateDetectionResult(
        status=status,
        signals=tuple(signals),
        matched_claim_ids=tuple(matched_claim_ids),
        exact_image_claim_ids=tuple(exact_image_claim_ids),
        similar_image_claim_ids=tuple(similar_image_claim_ids),
        reference_claim_ids=tuple(reference_claim_ids),
        unavailable_checks=unavailable_checks,
        reasons=reasons,
    )
