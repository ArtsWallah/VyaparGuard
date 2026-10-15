import base64
import os
import threading
import time
from uuid import uuid4

from fastapi import (
    FastAPI,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
)
from sqlalchemy.exc import SQLAlchemyError

from app.db.database import SessionLocal
from app.db.models import Scan, ScanCheck
from app.services.apk_analyzer import (
    APKAnalysisError,
    MAX_APK_SIZE,
    analyze_apk,
)
from app.services.fraud_engine_integration import (
    integrate_fraud_engine,
    reference_fingerprint,
)
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
_APK_UPLOAD_SLOTS = threading.BoundedSemaphore(2)


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


def _serialize_datetime(value):
    return value.isoformat() if value is not None else None


def _serialize_scan(scan: Scan) -> dict:
    return {
        "scan_id": scan.request_id,
        "created_at": _serialize_datetime(scan.created_at),
        "status": scan.verdict,
        "amount": scan.amount,
        "reference_available": scan.reference_fingerprint is not None,
        "reference_fingerprint": scan.reference_fingerprint,
        "summary": scan.summary,
        "processing_ms": scan.processing_ms,
        "demo_mode": scan.demo_mode,
    }


def _serialize_check(check: ScanCheck) -> dict:
    return {
        "check_id": check.check_id,
        "status": check.status,
        "message": check.message,
        "evidence": _json_safe(check.evidence),
    }


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "VyaparGuard API"}


@app.get("/api/v1/scans")
def list_scans(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    try:
        with SessionLocal() as session:
            total = session.query(Scan).count()
            scans = (
                session.query(Scan)
                .order_by(Scan.created_at.desc(), Scan.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
                .all()
            )
            return {
                "items": [_serialize_scan(scan) for scan in scans],
                "page": page,
                "page_size": page_size,
                "total": total,
                "has_next": page * page_size < total,
            }
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail="Scan history is temporarily unavailable.",
        ) from exc


@app.get("/api/v1/scans/{scan_id}")
def get_scan(scan_id: str):
    if not scan_id.strip():
        raise HTTPException(status_code=400, detail="Scan ID is required.")

    try:
        with SessionLocal() as session:
            scan = (
                session.query(Scan)
                .filter(Scan.request_id == scan_id)
                .one_or_none()
            )
            if scan is None:
                raise HTTPException(status_code=404, detail="Scan not found.")

            checks = (
                session.query(ScanCheck)
                .filter(ScanCheck.scan_id == scan.id)
                .order_by(ScanCheck.id.asc())
                .all()
            )
            return {
                **_serialize_scan(scan),
                "checks": [_serialize_check(check) for check in checks],
            }
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail="Scan history is temporarily unavailable.",
        ) from exc


@app.delete("/api/v1/scans/{scan_id}")
def delete_scan(scan_id: str):
    if not scan_id.strip():
        raise HTTPException(status_code=400, detail="Scan ID is required.")

    try:
        with SessionLocal() as session:
            scan = (
                session.query(Scan)
                .filter(Scan.request_id == scan_id)
                .one_or_none()
            )
            if scan is None:
                raise HTTPException(status_code=404, detail="Scan not found.")

            session.query(ScanCheck).filter(
                ScanCheck.scan_id == scan.id
            ).delete(synchronize_session=False)
            session.delete(scan)
            session.commit()
            return {"scan_id": scan_id, "deleted": True}
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail="Scan history is temporarily unavailable.",
        ) from exc


@app.post("/api/v1/apk/analyze")
async def analyze_apk_file(apk: UploadFile = File(...)):
    """Screen an APK statically without extracting or executing it."""
    if not _APK_UPLOAD_SLOTS.acquire(blocking=False):
        await apk.close()
        raise HTTPException(
            status_code=429,
            detail="APK analysis is busy. Please retry shortly.",
        )
    try:
        content = await apk.read(MAX_APK_SIZE + 1)
        result = analyze_apk(content, apk.filename or "uploaded.apk")
        return result.to_dict()
    except APKAnalysisError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    finally:
        _APK_UPLOAD_SLOTS.release()
        await apk.close()


@app.post("/api/v1/scan")
@app.post("/api/v1/analyze")
async def scan_payment(
    request: Request = None,
    image: UploadFile | None = File(None),
    file: UploadFile | None = File(None),
    expected_recipient: str | None = Form(None),
    payment_message: str | None = Form(None),
):
    upload_file = image or file
    started = time.perf_counter()

    try:
        content: bytes | None = None
        filename: str | None = None
        raw_content_type: str | None = None

        if upload_file is not None:
            filename = upload_file.filename
            raw_content_type = (upload_file.content_type or "").split(";")[0].strip().lower()
            if raw_content_type and raw_content_type not in ALLOWED_TYPES:
                raise HTTPException(
                    status_code=415,
                    detail="Only JPEG, PNG, and WebP images are supported.",
                )
            content = await upload_file.read(MAX_FILE_SIZE + 1)
        else:
            if request is None:
                raise HTTPException(
                    status_code=400,
                    detail="An image file is required.",
                )
            req_ct = (request.headers.get("content-type") or "").split(";")[0].strip().lower()

            if req_ct == "application/json":
                try:
                    payload = await request.json()
                except Exception:
                    payload = {}

                b64_data = payload.get("image_base64") or payload.get("image") or payload.get("file")
                if b64_data and isinstance(b64_data, str):
                    if "," in b64_data and "base64" in b64_data.split(",", 1)[0]:
                        b64_data = b64_data.split(",", 1)[1]
                    try:
                        content = base64.b64decode(b64_data)
                    except Exception as b64_err:
                        raise HTTPException(
                            status_code=400,
                            detail="Invalid base64 image data.",
                        ) from b64_err

                    filename = payload.get("filename") or "payment-screenshot.jpg"
                    raw_content_type = payload.get("content_type") or "image/jpeg"
            else:
                # Direct raw binary body or octet-stream
                raw_body = await request.body()
                if raw_body:
                    content = raw_body[: MAX_FILE_SIZE + 1]
                    raw_content_type = req_ct if req_ct in ALLOWED_TYPES else "image/jpeg"
                    filename = request.headers.get("x-filename") or "payment-screenshot.jpg"

        if not content:
            raise HTTPException(
                status_code=400,
                detail="An image file is required. Provide it as 'image' or 'file' in multipart form data, or as 'image_base64' in JSON.",
            )

        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail="Image exceeds 10 MB.",
            )

        result = analyze_payment_image(
            image_bytes=content,
            filename=filename,
            content_type=raw_content_type or "image/jpeg",
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
                image_bytes=content,
                expected_recipient=expected_recipient,
                payment_message=payment_message,
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
                reference_fingerprint=reference_fingerprint(
                    (result.get("ocr") or {}).get("reference")
                ),
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
        print("DATABASE ERROR:", repr(exc))
        raise HTTPException(
            status_code=503,
            detail="Scan history database is temporarily unavailable.",
        ) from exc


    finally:
        if upload_file:
            await upload_file.close()
