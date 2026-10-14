
from pathlib import Path

from app.services.ocr_service import extract_payment_details

image_path = input("Enter payment screenshot path: ").strip().strip('"')
image_bytes = Path(image_path).read_bytes()

result = extract_payment_details(image_bytes)

for key, value in result.items():
    print(f"{key}: {value}")
