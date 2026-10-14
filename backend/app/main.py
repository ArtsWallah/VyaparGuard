
import time
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile
from sqlalchemy.exc import SQLAlchemyError

from app.db.database import SessionLocal
from app.db.models import Scan
from app.services.payment_analyzer import (
    PaymentImageError,
    analyze_payment_image,
)

app = FastAPI(
    title="VyaparGuard API",
    description="Payment screenshot analysis API",
    version="0.2.0",
)

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_FILE_SIZE = 10 * 1024 * 1024

ERROR_STATUS_CODES = {
    "EMPTY_IMAGE": 400,
    "INVALID_IMAGE": 400,
    "INVALID_DIMENSIONS": 400,
    "UNSUPPORTED_FORMAT": 415,
    "FILE_TOO_LARGE": 413,
    "IMAGE_TOO_LARGE": 413,
    "OCR_FAILED": 500,
    "FORENSICS_FAILED": 500,
}


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "VyaparGuard API"}


@app.post("/api/v1/scan")
@app.post("/api/v1/analyze")
async def scan_payment(image: UploadFile = File(...)):
    started = time.perf_counter()

    try:
        if image.content_type not in ALLOWED_TYPES:
            raise HTTPException(
                status_code=415,
                detail="Upload a JPEG, PNG, or WebP image.",
            )

        content = await image.read(MAX_FILE_SIZE + 1)

        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail="Image exceeds the 10 MB limit.",
            )

        if not content:
            raise HTTPException(
                status_code=400,
                detail="Uploaded image is empty.",
            )

        result = analyze_payment_image(
            content,
            filename=image.filename,
            content_type=image.content_type,
        )

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        request_id = str(uuid4())

        # Save scan history. This does not verify the payment.
        with SessionLocal() as session:
            scan = Scan(
                request_id=request_id,
                verdict=result["verification"]["status"],
                demo_mode=True,
                amount=result["ocr"]["amount"],
                reference_fingerprint=None,
                summary=result["verification"]["reason"],
                processing_ms=elapsed_ms,
            )
            session.add(scan)
            session.commit()

        return {
            **result,
            "request_id": request_id,
            "processing_ms": elapsed_ms,
            "demo_mode": True,
        }

    except HTTPException:
        raise

    except PaymentImageError as exc:
        raise HTTPException(
            status_code=ERROR_STATUS_CODES.get(exc.code, 400),
            detail=exc.message,
        ) from exc

    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail="Scan history database is temporarily unavailable.",
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Payment image analysis failed.",
        ) from exc

    finally:
        await image.close()
