from pathlib import Path
import json

from app.services.payment_analyzer import (
    analyze_payment_image,
    PaymentImageError,
)

image_path = input("Enter test image path: ").strip().strip('"')
path = Path(image_path)

if not path.is_file():
    raise SystemExit(f"Image not found: {path}")

try:
    result = analyze_payment_image(
        image_bytes=path.read_bytes(),
        filename=path.name,
    )

    print(json.dumps(result, indent=2, ensure_ascii=False))

except PaymentImageError as exc:
    print(json.dumps({
        "error_code": exc.code,
        "message": exc.message,
    }, indent=2))