"""Deterministic fraud-engine components."""

from .duplicate_detector import (
    DEFAULT_PHASH_DISTANCE_THRESHOLD,
    DuplicateClaim,
    DuplicateDetectionResult,
    DuplicateStatus,
    InMemoryPriorClaimHistory,
    PriorClaim,
    PriorClaimHistory,
    detect_duplicates,
)
from .evidence_aggregator import (
    AggregationStatus,
    EvidenceAggregationInput,
    EvidenceAggregationResult,
    aggregate_evidence,
)
from .evidence_consistency import (
    DEFAULT_OCR_CONFIDENCE_THRESHOLD,
    DEFAULT_TIMESTAMP_TOLERANCE,
    ConsistencyFinding,
    EvidenceConsistencyInput,
    EvidenceConsistencyResult,
    FindingCategory,
    FindingSeverity,
    evaluate_consistency,
)
from .transaction_matcher import (
    InMemoryTrustedTransactionSource,
    MatchStatus,
    PaymentClaim,
    TransactionMatchResult,
    TrustedTransaction,
    TrustedTransactionSource,
    match_transaction,
)

__all__ = [
    "DEFAULT_PHASH_DISTANCE_THRESHOLD",
    "DEFAULT_OCR_CONFIDENCE_THRESHOLD",
    "DEFAULT_TIMESTAMP_TOLERANCE",
    "AggregationStatus",
    "ConsistencyFinding",
    "DuplicateClaim",
    "DuplicateDetectionResult",
    "DuplicateStatus",
    "EvidenceConsistencyInput",
    "EvidenceConsistencyResult",
    "EvidenceAggregationInput",
    "EvidenceAggregationResult",
    "FindingCategory",
    "FindingSeverity",
    "InMemoryTrustedTransactionSource",
    "InMemoryPriorClaimHistory",
    "MatchStatus",
    "PaymentClaim",
    "PriorClaim",
    "PriorClaimHistory",
    "TransactionMatchResult",
    "TrustedTransaction",
    "TrustedTransactionSource",
    "detect_duplicates",
    "evaluate_consistency",
    "aggregate_evidence",
    "match_transaction",
]
