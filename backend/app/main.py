
import os
import time
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile
from sqlalchemy.exc import SQLAlchemyError

from app.db.database import SessionLocal
from app.db.models import Scan, ScanCheck
from app.services.fraud_engine_integration import integrate_fraud_engine
from app.services.payment_analyzer import (
    MAX_FILE_SIZE,
    PaymentImageError,
    analyze_payment_image,
)

app = FastAPI(
    title="VyaparGuard API",
    description="Payment screenshot analysis API",
    version="0.3.0",
)

ALLOWED_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
    "image/pjpeg",
    "application/octet-stream",
    "binary/octet-stream",
}


def _demo_mode_enabled() -> bool:
    return os.getenv("VYAPARGUARD_DEMO_MODE", "true").casefold() == "true"


def _json_safe(value):
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    return value


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "VyaparGuard API"}


@app.post("/api/v1/scan")
@app.post("/api/v1/analyze")
async def scan_payment(
    image: UploadFile | None = File(None),
    file: UploadFile | None = File(None),
):
    upload_file = image or file
    if upload_file is None:
        raise HTTPException(
            status_code=400,
            detail="An image file is required. Use 'image' or 'file'.",
        )

    started = time.perf_counter()

    try:
        content_type = (
            (upload_file.content_type or "")
            .split(";")[0]
            .strip()
            .lower()
        )

        if content_type and content_type not in ALLOWED_TYPES:
            raise HTTPException(
                status_code=415,
                detail="Only JPEG, PNG, and WebP images are supported.",
            )

        content = await upload_file.read(MAX_FILE_SIZE + 1)

        if not content:
            raise HTTPException(status_code=400, detail="Empty image.")

        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail="Image exceeds 10 MB.",
            )

        result = analyze_payment_image(
            image_bytes=content,
            filename=upload_file.filename,
            content_type=content_type or "image/jpeg",
        )

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        request_id = str(uuid4())
        demo_mode = _demo_mode_enabled()

        # The database write is part of the request. If it fails,
        # return an error instead of silently losing scan history.
        with SessionLocal() as session:
            result = integrate_fraud_engine(
                result,
                session,
                request_id,
                demo_mode=demo_mode,
            )

            verification = result.get("verification") or {}
            extracted = result.get("extracted") or result.get("ocr") or {}
            verdict = verification.get("status") or "UNVERIFIED"
            amount = extracted.get("amount")
            summary = (
                verification.get("reason")
                or "; ".join(result.get("reasons", []))
                or "Screenshot analyzed; payment remains unverified."
            )

            scan = Scan(
                request_id=request_id,
                verdict=verdict,
                demo_mode=demo_mode,
                amount=amount,
                reference_fingerprint=None,
                summary=summary,
                processing_ms=elapsed_ms,
            )
            session.add(scan)
            session.flush()

            fraud_engine = result.get("fraud_engine") or {}
            consistency = fraud_engine.get("consistency") or {}
            for finding in consistency.get("findings", []):
                session.add(
                    ScanCheck(
                        scan_id=scan.id,
                        check_id=str(finding.get("category", "evidence")),
                        status=str(finding.get("severity", "INFO")),
                        message=str(finding.get("explanation", "")),
                        evidence=_json_safe(finding.get("evidence", {})),
                    )
                )
            session.commit()

        # Preserve the analyzer's existing response fields.
        result["request_id"] = request_id
        result["processing_ms"] = elapsed_ms
        result["demo_mode"] = demo_mode

        return result

    except HTTPException:
        raise

    except PaymentImageError as exc:
        status_code = {
            "EMPTY_IMAGE": 400,
            "UNSUPPORTED_FORMAT": 415,
            "FILE_TOO_LARGE": 413,
            "IMAGE_TOO_LARGE": 413,
            "INVALID_IMAGE": 400,
            "INVALID_DIMENSIONS": 400,
            "OCR_FAILED": 500,
            "FORENSICS_FAILED": 500,
        }.get(exc.code, 400)

        raise HTTPException(
            status_code=status_code,
            detail=exc.message,
        ) from exc

    except SQLAlchemyError as exc:
        # Avoid returning database credentials or internal details.
        raise HTTPException(
            status_code=503,
            detail="Scan history database is temporarily unavailable.",
        ) from exc

    finally:
        await upload_file.close()
