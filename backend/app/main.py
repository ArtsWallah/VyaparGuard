
from fastapi import FastAPI, File, HTTPException, UploadFile

app = FastAPI(
    title="VyaparGuard API",
    description="Payment screenshot analysis API",
    version="0.1.0",
)

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "VyaparGuard API"}


@app.post("/api/v1/scan")
async def scan_payment(image: UploadFile = File(...)):
    if image.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=415,
            detail="Upload a JPEG, PNG, or WebP image.",
        )

    content = await image.read(MAX_FILE_SIZE + 1)

    if not content:
        raise HTTPException(status_code=400, detail="Image is empty.")

    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="Image exceeds 10 MB.")

    # MVP placeholder: real OCR, image analysis, and
    # trusted-record reconciliation will be added later.
    return {
        "scan_id": "demo_001",
        "status": "UNVERIFIED",
        "extracted": {
            "amount": None,
            "transaction_id": None,
            "date": None,
        },
        "checks": {
            "duplicate": False,
            "trusted_record_match": False,
        },
        "reasons": [
            "Analysis is not implemented yet.",
            "No trusted transaction record has been checked.",
        ],
        "verification_source": "none",
    }
