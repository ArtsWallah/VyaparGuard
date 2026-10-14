
import re
from datetime import datetime
from io import BytesIO
from typing import Any

import cv2
import numpy as np
import pytesseract
from PIL import Image
from pytesseract import Output


# Windows Tesseract installation path
pytesseract.pytesseract.tesseract_cmd = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _parse_amount(text: str) -> float | None:
    """Extract an amount from common payment screenshot formats."""
    patterns = [
        r"(?:₹|rs\.?|inr)\s*[:\-]?\s*"
        r"([0-9][0-9,]*(?:\.[0-9]{1,2})?)",

        r"\b([0-9][0-9,]*(?:\.[0-9]{1,2})?)\s*"
        r"(?:inr|rupees|rs\.?)\b",

        r"\b([0-9][0-9,]*(?:\.[0-9]{1,2})?)"
        r"\s+has\s+been\s+paid\b",

        r"\b(?:amount|total|paid|payment\s+amount)"
        r"\s*[:\-]?\s*(?:₹|rs\.?|inr)?\s*"
        r"([0-9][0-9,]*(?:\.[0-9]{1,2})?)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            continue

        try:
            amount = float(match.group(1).replace(",", ""))
            if np.isfinite(amount) and amount >= 0:
                return amount
        except (ValueError, TypeError):
            continue

    return None


def _parse_date(text: str) -> str | None:
    """Normalize recognizable dates to YYYY-MM-DD."""
    patterns = [
        (
            r"\b(\d{1,2})\s+"
            r"(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|"
            r"May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|"
            r"Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
            r"\s*,?\s*(\d{4})\b"
        ),
        r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b",
        r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b",
        r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b",
    ]

    for index, pattern in enumerate(patterns):
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            continue

        try:
            if index == 0:
                date_text = (
                    f"{match.group(1)} "
                    f"{match.group(2)} {match.group(3)}"
                )
                for fmt in ("%d %b %Y", "%d %B %Y"):
                    try:
                        return datetime.strptime(
                            date_text, fmt
                        ).date().isoformat()
                    except ValueError:
                        pass

            elif index in (1, 2):
                # Assumes Indian DD/MM/YYYY date convention.
                day, month, year = map(int, match.groups())
                return datetime(year, month, day).date().isoformat()

            else:
                year, month, day = map(int, match.groups())
                return datetime(year, month, day).date().isoformat()

        except ValueError:
            continue

    return None


def _extract_payment_details(text: str) -> dict[str, Any]:
    normalized = _normalize_text(text)

    transaction_id = None
    upi_reference = None

    transaction_patterns = [
        r"\btransaction\s*(?:id|no\.?|number)"
        r"\s*[:#\-]?\s*([A-Z0-9][A-Z0-9\-]{5,})",
        r"\btxn\s*(?:id|no\.?|number)"
        r"\s*[:#\-]?\s*([A-Z0-9][A-Z0-9\-]{5,})",
    ]

    upi_patterns = [
        r"\bUPI\s*(?:reference|ref)"
        r"\s*(?:no\.?|number|id)?\s*[:#\-]?\s*"
        r"([A-Z0-9][A-Z0-9\-]{5,})",
        r"\bRRN\s*[:#\-]?\s*([A-Z0-9][A-Z0-9\-]{5,})",
    ]

    for pattern in transaction_patterns:
        match = re.search(pattern, normalized, re.IGNORECASE)
        if match:
            transaction_id = match.group(1).strip(".,;:")
            break

    for pattern in upi_patterns:
        match = re.search(pattern, normalized, re.IGNORECASE)
        if match:
            upi_reference = match.group(1).strip(".,;:")
            break

    labeled_date = re.search(
        r"(?:date\s*(?:&|and)?\s*time|payment\s*date|"
        r"transaction\s*date)\s*[:\-]?\s*(.{0,80})",
        normalized,
        re.IGNORECASE,
    )

    payment_date = (
        _parse_date(labeled_date.group(1))
        if labeled_date
        else None
    )
    payment_date = payment_date or _parse_date(normalized)

    generic_reference = upi_reference or transaction_id

    return {
        "amount": _parse_amount(normalized),
        "currency": "INR" if re.search(
            r"₹|\bINR\b|\bRs\.?",
            normalized,
            re.IGNORECASE,
        ) else None,
        "date": payment_date,
        "time": None,
        "timestamp": None,
        "transaction_id": transaction_id,
        "upi_reference": upi_reference,
        "reference": generic_reference,
        "payee": None,
        "displayed_status": None,
    }


def extract_payment_details(image_bytes: bytes) -> dict[str, Any]:
    """
    Extract payment-related text and fields from image bytes.

    OCR results are untrusted observations, not proof of payment.
    """
    if not image_bytes:
        raise ValueError("Image data is empty.")

    try:
        with Image.open(BytesIO(image_bytes)) as image:
            image_array = np.array(image.convert("RGB"))
    except Exception as exc:
        raise ValueError("Unable to decode image for OCR.") from exc

    try:
        gray = cv2.cvtColor(image_array, cv2.COLOR_RGB2GRAY)

        height, width = gray.shape[:2]
        if max(height, width) < 1600:
            scale = min(2.0, 1600 / max(height, width))
            gray = cv2.resize(
                gray,
                None,
                fx=scale,
                fy=scale,
                interpolation=cv2.INTER_CUBIC,
            )

        blurred = cv2.GaussianBlur(gray, (3, 3), 0)
        _, thresholded = cv2.threshold(
            blurred,
            0,
            255,
            cv2.THRESH_BINARY + cv2.THRESH_OTSU,
        )

        config = "--oem 3 --psm 6"

        raw_text = pytesseract.image_to_string(
            thresholded,
            config=config,
        ).strip()

        ocr_data = pytesseract.image_to_data(
            thresholded,
            config=config,
            output_type=Output.DICT,
        )

        confidences = []
        for value in ocr_data.get("conf", []):
            try:
                confidence = float(value)
                if confidence >= 0:
                    confidences.append(confidence)
            except (TypeError, ValueError):
                continue

        confidence = (
            sum(confidences) / len(confidences) / 100
            if confidences
            else 0.0
        )
        confidence = max(0.0, min(1.0, confidence))

        fields = _extract_payment_details(raw_text)

        # Provide nested fields and top-level compatibility.
        return {
            "raw_text": raw_text,
            "confidence": round(confidence, 4),
            "ocr_confidence": round(confidence, 4),
            "fields": fields,
            **fields,
            "fields_missing": [
                name
                for name in ("amount", "date")
                if fields[name] is None
            ],
        }

    except pytesseract.TesseractNotFoundError as exc:
        raise RuntimeError(
            "Tesseract OCR was not found. Check its executable path."
        ) from exc
    except Exception as exc:
        raise RuntimeError(f"OCR processing failed: {exc}") from exc
