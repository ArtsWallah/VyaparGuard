import os
import re
import shutil
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pytesseract
from PIL import Image
from pytesseract import Output

def _resolve_tesseract_cmd() -> str:
    configured_path = os.environ.get("TESSERACT_CMD")
    if configured_path:
        return configured_path

    path_command = shutil.which("tesseract")
    if path_command:
        return path_command

    if os.name == "nt":
        install_dirs = [
            Path.home() / "AppData" / "Local" / "Programs" / "Tesseract-OCR",
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Tesseract-OCR",
            Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))
            / "Tesseract-OCR",
        ]
        for install_dir in install_dirs:
            executable = install_dir / "tesseract.exe"
            if executable.is_file():
                return str(executable)

    return "tesseract"


pytesseract.pytesseract.tesseract_cmd = _resolve_tesseract_cmd()



def _normalize_text(text: str) -> str:
    return re.sub(r"[ \t]+", " ", text).strip()


def _parse_amount(text: str) -> float | None:
    patterns = [
        r"(?:₹|rs\.?|inr)\s*[:\-]?\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)",
        r"\b([0-9][0-9,]*(?:\.[0-9]{1,2})?)\s*(?:inr|rupees|rs\.?)\b",
        r"\b([0-9][0-9,]*(?:\.[0-9]{1,2})?)\s+has\s+been\s+paid\b",
        r"\b(?:amount|total|paid|payment\s+amount)\s*[:\-]?\s*(?:₹|rs\.?|inr)?\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                amount = float(match.group(1).replace(",", ""))
                if np.isfinite(amount) and amount >= 0:
                    return amount
            except (ValueError, TypeError):
                pass

    return None


def _parse_date(text: str) -> str | None:
    patterns = [
        r"\b(\d{1,2})\s+(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s*,?\s*(\d{4})\b",
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
                date_text = f"{match.group(1)} {match.group(2)} {match.group(3)}"
                for fmt in ("%d %b %Y", "%d %B %Y"):
                    try:
                        return datetime.strptime(date_text, fmt).date().isoformat()
                    except ValueError:
                        continue
            elif index in (1, 2):
                day, month, year = map(int, match.groups())
                return datetime(year, month, day).date().isoformat()
            else:
                year, month, day = map(int, match.groups())
                return datetime(year, month, day).date().isoformat()
        except ValueError:
            continue

    return None


def _parse_time(text: str) -> str | None:
    match = re.search(
        r"\b(0?[1-9]|1[0-2]):([0-5]\d)\s*(AM|PM)\b",
        text,
        re.IGNORECASE,
    )
    if match:
        try:
            parsed = datetime.strptime(
                f"{match.group(1)}:{match.group(2)} {match.group(3).upper()}",
                "%I:%M %p",
            )
            return parsed.strftime("%H:%M:%S")
        except ValueError:
            pass

    match = re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)(?::([0-5]\d))?\b", text)
    if match:
        hour, minute, second = match.groups()
        return f"{int(hour):02d}:{minute}:{second or '00'}"

    return None


def _extract_payment_details(text: str) -> dict[str, Any]:
    # Keep line breaks for more reliable label/value extraction.
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    normalized = " ".join(lines)

    transaction_id = None
    upi_reference = None

    # Match transaction ID labels even when OCR reads "ID" as "tD".
    transaction_patterns = [
        r"\btransaction\s*(?:id|[tli]d|no\.?|number)\s*[:#\-]?\s*([A-Z0-9][A-Z0-9\-]{5,})",
        r"\btxn\s*(?:id|no\.?|number)\s*[:#\-]?\s*([A-Z0-9][A-Z0-9\-]{5,})",
    ]

    for pattern in transaction_patterns:
        match = re.search(pattern, normalized, re.IGNORECASE)
        if match:
            transaction_id = match.group(1).strip(".,;:")
            break

    # Fallback: look at the line following a transaction label.
    if transaction_id is None:
        for i, line in enumerate(lines):
            if re.search(r"\btransaction\s*(?:id|[tli]d|no\.?|number)\b", line, re.IGNORECASE):
                candidates = [line]
                if i + 1 < len(lines):
                    candidates.append(lines[i + 1])

                for candidate in candidates:
                    match = re.search(r"\b[A-Z0-9][A-Z0-9\-]{7,}\b", candidate, re.IGNORECASE)
                    if match:
                        value = match.group(0).strip(".,;:")
                        if re.search(r"\d", value):
                            transaction_id = value
                            break
                if transaction_id:
                    break

    upi_patterns = [
        r"\bUPI\s*(?:reference|ref)\s*(?:no\.?|number|id)?\s*[:#\-]?\s*([A-Z0-9][A-Z0-9\-]{5,})",
        r"\bRRN\s*[:#\-]?\s*([A-Z0-9][A-Z0-9\-]{5,})",
    ]

    for pattern in upi_patterns:
        match = re.search(pattern, normalized, re.IGNORECASE)
        if match:
            upi_reference = match.group(1).strip(".,;:")
            break

    if upi_reference is None:
        for i, line in enumerate(lines):
            if re.search(r"\bUPI\s*(?:reference|ref)\b", line, re.IGNORECASE):
                candidates = [line]
                if i + 1 < len(lines):
                    candidates.append(lines[i + 1])

                for candidate in candidates:
                    match = re.search(r"\b[A-Z0-9][A-Z0-9\-]{7,}\b", candidate, re.IGNORECASE)
                    if match and re.search(r"\d", match.group(0)):
                        upi_reference = match.group(0).strip(".,;:")
                        break
                if upi_reference:
                    break

    # Extract the date and time independently.
    payment_date = _parse_date(normalized)
    payment_time = _parse_time(normalized)

    timestamp = None
    if payment_date and payment_time:
        timestamp = f"{payment_date}T{payment_time}"

    # Look for a payee following a recognizable payment phrase.
    payee = None
    for i, line in enumerate(lines):
        if re.search(
            r"\b(?:paid\s+to|sent\s+to|payment\s+to|transferred\s+to)\b",
            line,
            re.IGNORECASE,
        ):
            match = re.search(
                r"\b(?:paid\s+to|sent\s+to|payment\s+to|transferred\s+to)\s+(.+)",
                line,
                re.IGNORECASE,
            )
            if match and match.group(1).strip():
                candidate = match.group(1).strip(" :-")
            elif i + 1 < len(lines):
                candidate = lines[i + 1]
            else:
                candidate = ""

            # Don't accidentally treat labels or account information as a name.
            candidate = re.split(
                r"\s{2,}|\b(?:transaction|date|debited from|upi reference)\b",
                candidate,
                maxsplit=1,
                flags=re.IGNORECASE,
            )[0].strip(" :-")

            if candidate and not re.search(r"\d{5,}", candidate):
                payee = candidate
                break

    displayed_status = None
    status_patterns = [
        (r"\bpayment\s+successful\b", "Payment Successful"),
        (r"\bpayment\s+completed\b", "Payment Completed"),
        (r"\btransaction\s+successful\b", "Transaction Successful"),
        (r"\bpayment\s+failed\b", "Payment Failed"),
        (r"\btransaction\s+failed\b", "Transaction Failed"),
        (r"\bpending\b", "Pending"),
    ]
    for pattern, label in status_patterns:
        if re.search(pattern, normalized, re.IGNORECASE):
            displayed_status = label
            break

    currency = None
    if re.search(r"₹|\bINR\b|\bRs\.?", normalized, re.IGNORECASE):
        currency = "INR"
    elif re.search(r"\bRupees\b", normalized, re.IGNORECASE):
        currency = "INR"

    return {
        "amount": _parse_amount(normalized),
        "currency": currency,
        "date": payment_date,
        "time": payment_time,
        "timestamp": timestamp,
        "transaction_id": transaction_id,
        "upi_reference": upi_reference,
        "reference": upi_reference or transaction_id,
        "payee": payee,
        "displayed_status": displayed_status,
    }


def extract_payment_details(image_bytes: bytes) -> dict[str, Any]:
    """
    Extract payment-related text and fields from image bytes.

    OCR output represents visible screenshot content only.
    It is not proof that a payment was received.
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
            thresholded, config=config
        ).strip()

        ocr_data = pytesseract.image_to_data(
            thresholded,
            config=config,
            output_type=Output.DICT,
        )

        confidences = []
        for value in ocr_data.get("conf", []):
            try:
                confidence_value = float(value)
                if confidence_value >= 0:
                    confidences.append(confidence_value)
            except (TypeError, ValueError):
                continue

        confidence = (
            sum(confidences) / len(confidences) / 100
            if confidences else 0.0
        )
        confidence = max(0.0, min(1.0, confidence))

        fields = _extract_payment_details(raw_text)

        return {
            "raw_text": raw_text,
            "confidence": round(confidence, 4),
            "ocr_confidence": round(confidence, 4),
            "fields": fields,
            **fields,
            "fields_missing": [
                name
                for name in (
                    "amount",
                    "date",
                    "time",
                    "transaction_id",
                    "upi_reference",
                    "payee",
                    "displayed_status",
                )
                if fields[name] is None
            ],
        }

    except pytesseract.TesseractNotFoundError as exc:
        raise RuntimeError(
            "Tesseract OCR was not found. Check its executable path."
        ) from exc
    except Exception as exc:
        raise RuntimeError(f"OCR processing failed: {exc}") from exc
