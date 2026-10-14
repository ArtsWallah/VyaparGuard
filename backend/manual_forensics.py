
from pathlib import Path

from app.services.image_forensics import inspect_image

image_path = input("Enter image path: ").strip().strip('"')
image_bytes = Path(image_path).read_bytes()

result = inspect_image(image_bytes)

for key, value in result.items():
    print(f"{key}: {value}")
