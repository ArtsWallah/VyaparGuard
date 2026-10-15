from datetime import datetime, timezone

import pytest

from app.services.fraud_engine.duplicate_detector import (
    DEFAULT_PHASH_DISTANCE_THRESHOLD,
    EXACT_IMAGE_REUSE,
    REFERENCE_REUSE,
    REPLAY_SUSPECTED,
    SIMILAR_IMAGE_REUSE,
    DuplicateClaim,
    DuplicateStatus,
    InMemoryPriorClaimHistory,
    PriorClaim,
    detect_duplicates,
)


CURRENT_CLAIM_ID = "claim-current"
IMAGE_SHA256 = "a" * 64
OTHER_IMAGE_SHA256 = "b" * 64
PHASH = "0000000000000000"
REFERENCE = "UPI-123456"
CREATED_AT = datetime(2026, 10, 15, tzinfo=timezone.utc)


def prior(**overrides) -> PriorClaim:
    values = {
        "claim_id": "claim-prior-1",
        "image_sha256": IMAGE_SHA256,
        "image_phash": PHASH,
        "reference": REFERENCE,
        "created_at": CREATED_AT,
    }
    values.update(overrides)
    return PriorClaim(**values)


def claim(**overrides) -> DuplicateClaim:
    values = {
        "claim_id": CURRENT_CLAIM_ID,
        "image_sha256": OTHER_IMAGE_SHA256,
        "image_phash": "ffffffffffffffff",
        "reference": " upi-123456 ",
    }
    values.update(overrides)
    return DuplicateClaim(**values)


def detect(claim_value: DuplicateClaim, *claims: PriorClaim, **kwargs):
    return detect_duplicates(
        claim_value,
        InMemoryPriorClaimHistory(claims),
        **kwargs,
    )


def test_no_prior_history_returns_no_duplicate():
    result = detect(claim())

    assert result.status is DuplicateStatus.NO_DUPLICATE
    assert result.signals == ()


def test_exact_sha256_reuse_is_reported():
    result = detect(
        claim(image_phash=None, reference=None),
        prior(image_sha256=OTHER_IMAGE_SHA256),
    )

    assert result.status is DuplicateStatus.EXACT_IMAGE_REUSE
    assert result.signals == (EXACT_IMAGE_REUSE,)
    assert result.exact_image_claim_ids == ("claim-prior-1",)


def test_exact_image_reuse_is_distinct_from_reference_reuse():
    result = detect(
        claim(image_phash=None, reference=None),
        prior(image_sha256=OTHER_IMAGE_SHA256, reference=REFERENCE),
    )

    assert result.status is DuplicateStatus.EXACT_IMAGE_REUSE
    assert result.reference_claim_ids == ()


def test_phash_at_threshold_reports_similar_image_reuse():
    result = detect(
        claim(image_sha256=None, image_phash=PHASH, reference=None),
        prior(image_sha256=None, image_phash="0000000000000008", reference=None),
    )

    assert result.status is DuplicateStatus.SIMILAR_IMAGE_REUSE
    assert result.similar_image_claim_ids == ("claim-prior-1",)
    assert DEFAULT_PHASH_DISTANCE_THRESHOLD == 8


def test_phash_above_threshold_does_not_match():
    result = detect(
        claim(image_sha256=None, image_phash=PHASH, reference=None),
        prior(image_sha256=None, image_phash="000000000000ffff", reference=None),
    )

    assert result.status is DuplicateStatus.NO_DUPLICATE


def test_configured_phash_threshold_is_used():
    result = detect(
        claim(image_sha256=None, image_phash=PHASH, reference=None),
        prior(image_sha256=None, image_phash="000000000000ffff", reference=None),
        phash_distance_threshold=16,
    )

    assert result.status is DuplicateStatus.SIMILAR_IMAGE_REUSE


def test_reference_reuse_is_reported():
    result = detect(
        claim(image_sha256=None, image_phash=None),
        prior(image_sha256=None, image_phash=None),
    )

    assert result.status is DuplicateStatus.REFERENCE_REUSE
    assert result.signals == (REFERENCE_REUSE,)
    assert result.reference_claim_ids == ("claim-prior-1",)


def test_same_reference_and_exact_image_is_replay_suspected():
    result = detect(
        claim(image_sha256=IMAGE_SHA256, image_phash=PHASH),
        prior(),
    )

    assert result.status is DuplicateStatus.REPLAY_SUSPECTED
    assert EXACT_IMAGE_REUSE in result.signals
    assert SIMILAR_IMAGE_REUSE in result.signals
    assert REFERENCE_REUSE in result.signals
    assert REPLAY_SUSPECTED in result.signals
    assert result.matched_claim_ids == ("claim-prior-1",)


def test_same_reference_and_similar_image_is_replay_suspected():
    result = detect(
        claim(image_sha256=None),
        prior(image_sha256=None, image_phash="fffffffffffffffe"),
    )

    assert result.status is DuplicateStatus.REPLAY_SUSPECTED
    assert result.signals == (
        SIMILAR_IMAGE_REUSE,
        REFERENCE_REUSE,
        REPLAY_SUSPECTED,
    )


def test_repeated_reference_across_multiple_claims_is_replay_suspected():
    result = detect(
        claim(image_sha256=None, image_phash=None),
        prior(claim_id="claim-prior-1", image_sha256=None, image_phash=None),
        prior(claim_id="claim-prior-2", image_sha256=None, image_phash=None),
    )

    assert result.status is DuplicateStatus.REPLAY_SUSPECTED
    assert result.reference_claim_ids == ("claim-prior-1", "claim-prior-2")
    assert result.matched_claim_ids == ("claim-prior-1", "claim-prior-2")


def test_missing_sha256_only_disables_exact_check():
    result = detect(
        claim(image_sha256=None, image_phash=PHASH, reference=None),
        prior(
            image_sha256=IMAGE_SHA256,
            image_phash="000000000000ffff",
            reference=None,
        ),
    )

    assert result.status is DuplicateStatus.NO_DUPLICATE
    assert result.unavailable_checks == ("image_sha256", "reference")


def test_missing_phash_is_listed_when_other_check_is_available():
    result = detect(
        claim(image_sha256=IMAGE_SHA256, image_phash=None, reference=None),
        prior(image_phash=PHASH, reference=None),
    )

    assert result.status is DuplicateStatus.EXACT_IMAGE_REUSE
    assert result.unavailable_checks == ("image_phash", "reference")


def test_missing_reference_is_listed_when_image_checks_are_available():
    result = detect(
        claim(
            image_sha256=IMAGE_SHA256,
            image_phash=PHASH,
            reference=None,
        ),
        prior(reference=None),
    )

    assert result.status is DuplicateStatus.EXACT_IMAGE_REUSE
    assert result.unavailable_checks == ("reference",)


def test_all_checks_missing_return_insufficient_data():
    result = detect(
        DuplicateClaim(claim_id=CURRENT_CLAIM_ID),
        prior(image_sha256=None, image_phash=None, reference=None),
    )

    assert result.status is DuplicateStatus.INSUFFICIENT_DATA
    assert result.matched_claim_ids == ()


def test_malformed_sha256_is_rejected():
    with pytest.raises(ValueError, match="image_sha256.*64"):
        detect(claim(image_sha256="not-a-sha256"))


def test_malformed_phash_is_rejected():
    with pytest.raises(ValueError, match="image_phash.*16"):
        detect(claim(image_phash="xyz"))


def test_hash_case_and_reference_whitespace_are_normalized():
    result = detect(
        claim(
            image_sha256=IMAGE_SHA256.upper(),
            image_phash=PHASH.upper(),
            reference="  upi-123456  ",
        ),
        prior(
            image_sha256=IMAGE_SHA256,
            image_phash=PHASH,
            reference="UPI-123456",
        ),
    )

    assert result.status is DuplicateStatus.REPLAY_SUSPECTED


def test_current_claim_is_not_matched_against_itself():
    result = detect(
        claim(),
        prior(claim_id=CURRENT_CLAIM_ID),
    )

    assert result.status is DuplicateStatus.NO_DUPLICATE
    assert result.matched_claim_ids == ()


def test_different_phash_width_is_not_accepted_from_prior_history():
    result = detect(
        claim(image_sha256=None, reference=None),
        prior(image_sha256=None, image_phash="000000000000000", reference=None),
    )

    assert result.status is DuplicateStatus.NO_DUPLICATE


def test_negative_phash_threshold_is_rejected():
    with pytest.raises(ValueError, match="non-negative"):
        detect(claim(), phash_distance_threshold=-1)


def test_trusted_transaction_existence_is_not_a_duplicate_signal():
    result = detect(
        claim(image_sha256=None, image_phash=None),
        prior(image_sha256=None, image_phash=None),
    )

    assert result.status is DuplicateStatus.REFERENCE_REUSE
    assert "VERIFIED" not in result.status.value
    assert "SUSPICIOUS" not in result.status.value
    assert "UNVERIFIED" not in result.status.value


def test_no_match_lists_unavailable_checks():
    result = detect(
        claim(image_sha256=OTHER_IMAGE_SHA256, image_phash=None, reference=None),
        prior(image_sha256=IMAGE_SHA256, image_phash=None, reference=None),
    )

    assert result.status is DuplicateStatus.NO_DUPLICATE
    assert result.unavailable_checks == ("image_phash", "reference")
