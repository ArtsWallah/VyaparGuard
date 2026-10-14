
from io import BytesIO

import cv2
import numpy as np
from PIL import Image, ImageChops, ImageEnhance


def inspect_image(image_bytes: bytes) -> dict:
    """
    Measure image characteristics and exploratory
    forensic indicators.

    These measurements do not prove that an image
    is genuine or manipulated.
    """
    if not image_bytes:
        raise ValueError("Image is empty.")

    try:
        original = Image.open(BytesIO(image_bytes))
        original_format = original.format
        original.verify()

        # Reopen after verify(), which invalidates the image object.
        original = Image.open(BytesIO(image_bytes)).convert("RGB")
    except Exception as exc:
        raise ValueError(
            "Invalid or unsupported image."
        ) from exc

    width, height = original.size

    if width < 1 or height < 1:
        raise ValueError("Image dimensions are invalid.")

    image_array = np.asarray(original)
    gray = cv2.cvtColor(image_array, cv2.COLOR_RGB2GRAY)

    # Laplacian variance: a basic sharpness indicator.
    sharpness = float(
        cv2.Laplacian(gray, cv2.CV_64F).var()
    )

    # Recompress at JPEG quality 90 for exploratory ELA.
    buffer = BytesIO()
    original.save(buffer, format="JPEG", quality=90)
    buffer.seek(0)

    recompressed = Image.open(buffer).convert("RGB")
    difference = ImageChops.difference(
        original, recompressed
    )
    enhanced = ImageEnhance.Contrast(
        difference
    ).enhance(5)

    ela_mean = float(
        np.asarray(enhanced, dtype=np.float32).mean()
    )

    indicators = []

    # These are quality flags, not fraud findings.
    if min(width, height) < 250:
        indicators.append("LOW_RESOLUTION")

    if sharpness < 30:
        indicators.append("POSSIBLY_BLURRY")

    return {
        "width": width,
        "height": height,
        "format": original_format,
        "sharpness_score": round(sharpness, 3),
        "ela_mean": round(ela_mean, 3),
        "indicators": indicators,
        "assessment": "INCONCLUSIVE",
        "limitations": [
            "ELA differences are not proof of manipulation.",
            "Compression, resizing, and screenshots can "
            "change image characteristics.",
            "Sharpness thresholds depend on image content."
        ]
    }
