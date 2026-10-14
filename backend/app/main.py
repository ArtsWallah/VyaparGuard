
from fastapi import FastAPI, File, HTTPException, UploadFile

from app.services.payment_analyzer import (
    MAX_FILE_SIZE,
    PaymentImageError,
    analyze_payment_image,
)

app = FastAPI(
    title="VyaparGuard API",
    description="Payment screenshot analysis API",
    version="0.2.0",
)


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "VyaparGuard API"}


@app.post("/api/v1/scan")
async def scan_payment(
    image: UploadFile | None = File(None),
    file: UploadFile | None = File(None),
):
    upload_file = image or file
    if upload_file is None:
        raise HTTPException(
            status_code=400,
            detail="An image file is required. Provide it as 'image' or 'file' in multipart form data.",
        )

    allowed_types = {
        "image/jpeg",
        "image/jpg",
        "image/png",
        "image/webp",
        "image/pjpeg",
        "application/octet-stream",
        "binary/octet-stream",
    }

    try:
        raw_content_type = (upload_file.content_type or "").split(";")[0].strip().lower()
        if raw_content_type and raw_content_type not in allowed_types:
            raise HTTPException(
                status_code=415,
                detail="Only JPEG, PNG, and WebP images are supported.",
            )

        content = await upload_file.read(MAX_FILE_SIZE + 1)

        if not content:
            raise HTTPException(status_code=400, detail="Empty image.")

        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(status_code=413, detail="Image exceeds 10 MB.")

        try:
            return analyze_payment_image(
                image_bytes=content,
                filename=upload_file.filename,
                content_type=raw_content_type or "image/jpeg",
            )
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

    finally:
        if upload_file:
            await upload_file.close()
