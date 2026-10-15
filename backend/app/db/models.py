
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.sql import func

from app.db.database import Base


class DemoTransaction(Base):
    __tablename__ = "demo_transactions"

    id = Column(Integer, primary_key=True, index=True)
    reference_norm = Column(String(100), unique=True, nullable=False, index=True)
    amount = Column(Float, nullable=False)
    currency = Column(String(3), nullable=False, default="INR")
    payee_alias = Column(String(150), nullable=True)
    transaction_time = Column(DateTime(timezone=True), nullable=True)
    seeded_status = Column(String(30), nullable=False, default="SUCCESS")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Scan(Base):
    __tablename__ = "scans"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(String(36), unique=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    verdict = Column(String(20), nullable=False, default="UNVERIFIED")
    demo_mode = Column(Boolean, nullable=False, default=True)
    amount = Column(Float, nullable=True)
    reference_fingerprint = Column(String(64), nullable=True)
    summary = Column(Text, nullable=True)
    processing_ms = Column(Integer, nullable=True)


class ScanCheck(Base):
    __tablename__ = "scan_checks"

    id = Column(Integer, primary_key=True, index=True)
    scan_id = Column(Integer, ForeignKey("scans.id", ondelete="CASCADE"), nullable=False)
    check_id = Column(String(100), nullable=False)
    status = Column(String(20), nullable=False)
    message = Column(Text, nullable=False)
    evidence = Column(JSON, nullable=True)


class SeenClaim(Base):
    __tablename__ = "seen_claims"

    id = Column(Integer, primary_key=True, index=True)
    reference_fingerprint = Column(String(64), nullable=True, index=True)
    image_sha256 = Column(String(64), nullable=True, index=True)
    first_seen_at = Column(DateTime(timezone=True), server_default=func.now())
    last_seen_at = Column(DateTime(timezone=True), server_default=func.now())
    occurrence_count = Column(Integer, nullable=False, default=1)

    __table_args__ = (
        UniqueConstraint(
            "reference_fingerprint",
            "image_sha256",
            name="uq_seen_claim_reference_image",
        ),
    )
