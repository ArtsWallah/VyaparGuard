"""Backend adapters that connect persistence and API analysis to the Fraud Engine."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Iterable, Mapping

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.db.models import DemoTransaction, SeenClaim
from app.services.fraud_engine.duplicate_detector import (
    DuplicateClaim,
    DuplicateDetectionResult,
    DuplicateStatus,
    PriorClaim,
    PriorClaimHistory,
    detect_duplicates,
)
from app.services.fraud_engine.evidence_aggregator import (
    EvidenceAggregationInput,
    EvidenceAggregationResult,
    aggregate_evidence,
)
from app.services.fraud_engine.evidence_consistency import (
    ConsistencyFinding,
    EvidenceConsistencyInput,
    EvidenceConsistencyResult,
    evaluate_consistency,
)
from app.services.fraud_engine.transaction_matcher import (
    MatchStatus,
    PaymentClaim,
    TrustedTransaction,
    TrustedTransactionSource,
    match_transaction,
)
from app.services.recipient_verification import (
    RecipientVerificationResult,
    verify_recipient_evidence,
)


class EmptyTrustedTransactionSource:
    """Explicit no-source adapter used when live trusted data is unavailable."""

    def iter_incoming_credits(self) -> Iterable[TrustedTransaction]:
        return iter(())


class DemoTransactionSource:
    """Adapter for the repository's explicitly seeded demo transactions."""

    def __init__(self, session: Session):
        self._session = session

    def iter_incoming_credits(self) -> Iterable[TrustedTransaction]:
        records = self._session.query(DemoTransaction).all()
        for record in records:
            status = (
                "SETTLED"
                if str(record.seeded_status).casefold() in {"success", "settled"}
                else str(record.seeded_status)
            )
            yield TrustedTransaction(
                transaction_id=f"demo-{record.id}",
                amount=Decimal(str(record.amount)),
                currency=record.currency,
                reference=record.reference_norm,
                recipient=record.payee_alias,
                timestamp=record.transaction_time,
                direction="INCOMING",
                status=status,
            )


class SeenClaimHistory:
    """Persistent exact-image/reference history backed by ``seen_claims``."""

    def __init__(
        self,
        session: Session,
        image_sha256: str | None,
        reference_fingerprint: str | None,
    ):
        self._session = session
        self._image_sha256 = image_sha256
        self._reference_fingerprint = reference_fingerprint

    def iter_prior_claims(self) -> Iterable[PriorClaim]:
        predicates = []
        if self._image_sha256 is not None:
            predicates.append(SeenClaim.image_sha256 == self._image_sha256)
        if self._reference_fingerprint is not None:
            predicates.append(
                SeenClaim.reference_fingerprint == self._reference_fingerprint
            )
        if not predicates:
            return iter(())

        rows = self._session.query(SeenClaim).filter(or_(*predicates)).all()
        return iter(
            PriorClaim(
                claim_id=f"seen-{row.id}",
                image_sha256=row.image_sha256,
                image_phash=None,
                reference=row.reference_fingerprint,
                created_at=row.first_seen_at,
            )
            for row in rows
        )


def reference_fingerprint(reference: object) -> str | None:
    if not isinstance(reference, str):
        return None
    normalized = reference.strip().casefold()
    if not normalized:
        return None
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _parse_timestamp(value: object) -> datetime | None:
    if isinstance(value, datetime):
        timestamp = value
    elif isinstance(value, str):
        try:
            timestamp = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
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


def _build_claim(ocr: Mapping[str, Any]) -> PaymentClaim:
    return PaymentClaim(
        amount=ocr.get("amount"),
        currency=ocr.get("currency"),
        reference=ocr.get("reference"),
        recipient=ocr.get("payee"),
        timestamp=_parse_timestamp(ocr.get("timestamp")),
    )


def _serialize_value(value: object) -> object:
    if isinstance(value, tuple):
        return [_serialize_value(item) for item in value]
    if isinstance(value, list):
        return [_serialize_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _serialize_value(item) for key, item in value.items()}
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _serialize_finding(finding: ConsistencyFinding) -> dict[str, object]:
    return {
        "category": finding.category.value,
        "severity": finding.severity.value,
        "field": finding.field,
        "explanation": finding.explanation,
        "evidence": _serialize_value(dict(finding.evidence)),
    }


def _serialize_recipient_verification(
    result: RecipientVerificationResult,
) -> dict[str, object]:
    destination = result.qr.destination
    message = result.message
    return {
        "qr": {
            "status": result.qr.status.value,
            "explanation": result.qr.explanation,
            "expected_recipient": result.qr.expected_recipient,
            "destination": (
                {
                    "scheme": destination.scheme,
                    "payee_identifier": destination.payee_identifier,
                    "payee_name": destination.payee_name,
                    "amount": _serialize_value(destination.amount),
                    "reference": destination.reference,
                }
                if destination is not None
                else None
            ),
        },
        "payment_message": (
            {
                "status": message.status.value,
                "amount": _serialize_value(message.amount),
                "reference": message.reference,
                "compared_fields": list(message.compared_fields),
                "explanation": message.explanation,
                "untrusted": True,
            }
            if message is not None
            else None
        ),
    }


def _serialize_aggregation(
    aggregation: EvidenceAggregationResult,
) -> dict[str, object]:
    match = aggregation.transaction_match
    duplicate = aggregation.duplicate_detection
    consistency = aggregation.consistency
    return {
        "status": aggregation.status.value,
        "reasons": list(aggregation.reasons),
        "blocking_conditions": list(aggregation.blocking_conditions),
        "transaction_match": {
            "status": match.status.value,
            "matched_transaction_id": match.matched_transaction_id,
            "candidate_count": match.candidate_count,
            "conflict_fields": list(match.conflict_fields),
            "reasons": list(match.reasons),
        },
        "duplicate_detection": {
            "status": duplicate.status.value,
            "signals": list(duplicate.signals),
            "matched_claim_ids": list(duplicate.matched_claim_ids),
            "exact_image_claim_ids": list(duplicate.exact_image_claim_ids),
            "similar_image_claim_ids": list(duplicate.similar_image_claim_ids),
            "reference_claim_ids": list(duplicate.reference_claim_ids),
            "unavailable_checks": list(duplicate.unavailable_checks),
            "reasons": list(duplicate.reasons),
        },
        "consistency": {
            "findings": [_serialize_finding(item) for item in consistency.findings],
            "compared_fields": list(consistency.compared_fields),
            "unavailable_evidence": list(consistency.unavailable_evidence),
            "recipient_verification": (
                _serialize_recipient_verification(
                    consistency.recipient_verification
                )
                if consistency.recipient_verification is not None
                else None
            ),
        },
    }


def _remember_claim(
    session: Session,
    image_sha256: str | None,
    reference_hash: str | None,
) -> None:
    if image_sha256 is None and reference_hash is None:
        return

    predicates = []
    if image_sha256 is None:
        predicates.append(SeenClaim.image_sha256.is_(None))
    else:
        predicates.append(SeenClaim.image_sha256 == image_sha256)
    if reference_hash is None:
        predicates.append(SeenClaim.reference_fingerprint.is_(None))
    else:
        predicates.append(SeenClaim.reference_fingerprint == reference_hash)

    existing = session.query(SeenClaim).filter(and_(*predicates)).one_or_none()
    now = datetime.now(timezone.utc)
    if existing is None:
        session.add(
            SeenClaim(
                image_sha256=image_sha256,
                reference_fingerprint=reference_hash,
                first_seen_at=now,
                last_seen_at=now,
                occurrence_count=1,
            )
        )
    else:
        existing.last_seen_at = now
        existing.occurrence_count = (existing.occurrence_count or 0) + 1


def integrate_fraud_engine(
    analysis_result: dict[str, Any],
    session: Session,
    request_id: str,
    *,
    demo_mode: bool,
    image_phash: str | None = None,
    image_bytes: bytes | None = None,
    expected_recipient: str | None = None,
    payment_message: str | None = None,
) -> dict[str, Any]:
    """Run all Fraud Engine flows and enrich an analyzer response.

    ``image_phash`` is optional because the current repository has no pHash
    generator. Production callers should leave it unset until one is supplied.
    """
    ocr = analysis_result.get("ocr") or {}
    if not isinstance(ocr, Mapping):
        ocr = {}
    claim = _build_claim(ocr)

    source: TrustedTransactionSource = (
        DemoTransactionSource(session)
        if demo_mode
        else EmptyTrustedTransactionSource()
    )
    transaction_match = match_transaction(claim, source)

    image_sha256 = (analysis_result.get("file") or {}).get("sha256")
    reference_hash = reference_fingerprint(ocr.get("reference"))
    duplicate_claim = DuplicateClaim(
        claim_id=request_id,
        image_sha256=image_sha256,
        image_phash=image_phash,
        reference=reference_hash,
    )
    duplicate_detection = detect_duplicates(
        duplicate_claim,
        SeenClaimHistory(session, image_sha256, reference_hash),
    )

    recipient_verification = verify_recipient_evidence(
        image_bytes or b"",
        expected_recipient=expected_recipient,
        payment_message=payment_message,
        ocr=ocr,
    )

    consistency = evaluate_consistency(
        EvidenceConsistencyInput(
            claim=claim,
            ocr=ocr,
            transaction_match=transaction_match,
            duplicate_detection=duplicate_detection,
            recipient_verification=recipient_verification,
        )
    )
    aggregation = aggregate_evidence(
        EvidenceAggregationInput(
            transaction_match=transaction_match,
            duplicate_detection=duplicate_detection,
            consistency=consistency,
        )
    )

    _remember_claim(session, image_sha256, reference_hash)

    finding_reasons = [finding.explanation for finding in consistency.findings]
    reasons = list(dict.fromkeys([*aggregation.reasons, *finding_reasons]))
    verification_source = (
        "demo_transaction_ledger"
        if transaction_match.status is MatchStatus.UNIQUE_MATCH
        else "none"
    )

    analysis_result["status"] = aggregation.status.value
    analysis_result["reasons"] = reasons
    analysis_result["verification_source"] = verification_source
    analysis_result["checks"] = {
        **(analysis_result.get("checks") or {}),
        "duplicate": duplicate_detection.status is not DuplicateStatus.NO_DUPLICATE,
        "trusted_record_match": transaction_match.status is MatchStatus.UNIQUE_MATCH,
        "trusted_match_status": transaction_match.status.value,
        "duplicate_status": duplicate_detection.status.value,
    }
    analysis_result["verification"] = {
        **(analysis_result.get("verification") or {}),
        "status": aggregation.status.value,
        "source": verification_source,
        "reason": "; ".join(reasons),
    }
    analysis_result["recipient_verification"] = _serialize_recipient_verification(
        recipient_verification
    )
    analysis_result["fraud_engine"] = _serialize_aggregation(aggregation)
    return analysis_result
