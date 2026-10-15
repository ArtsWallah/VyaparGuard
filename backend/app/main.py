
import base64
import json

from fastapi import FastAPI, File, HTTPException, Request, UploadFile

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
    request: Request,
    image: UploadFile | None = File(None),
    file: UploadFile | None = File(None),
):
    upload_file = image or file
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
        content: bytes | None = None
        filename: str | None = None
        raw_content_type: str | None = None

        if upload_file is not None:
            filename = upload_file.filename
            raw_content_type = (upload_file.content_type or "").split(";")[0].strip().lower()
            if raw_content_type and raw_content_type not in allowed_types:
                raise HTTPException(
                    status_code=415,
                    detail="Only JPEG, PNG, and WebP images are supported.",
                )
            content = await upload_file.read(MAX_FILE_SIZE + 1)
        else:
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
                    raw_content_type = req_ct if req_ct in allowed_types else "image/jpeg"
                    filename = request.headers.get("x-filename") or "payment-screenshot.jpg"

        if not content:
            raise HTTPException(
                status_code=400,
                detail="An image file is required. Provide it as 'image' or 'file' in multipart form data, or as 'image_base64' in JSON.",
            )

        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(status_code=413, detail="Image exceeds 10 MB.")

        try:
            return analyze_payment_image(
                image_bytes=content,
                filename=filename,
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
