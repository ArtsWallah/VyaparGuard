import asyncio
from io import BytesIO

import pytest
from fastapi import HTTPException, UploadFile

from app import main


class FakeAnalysis:
    def to_dict(self):
        return {
            "analysis_id": "analysis-1",
            "status": "COMPLETE",
            "sha256": "a" * 64,
            "metadata": {"package_name": "com.example.safe"},
            "findings": [],
            "limitations": ["Static screening is not comprehensive."],
        }


def test_apk_endpoint_returns_structured_result(monkeypatch):
    captured = {}

    def fake_analyzer(content, filename):
        captured["content"] = content
        captured["filename"] = filename
        return FakeAnalysis()

    monkeypatch.setattr(main, "analyze_apk", fake_analyzer)
    upload = UploadFile(
        file=BytesIO(b"apk-bytes"),
        filename="sample.apk",
    )

    result = asyncio.run(main.analyze_apk_file(upload))

    assert result["status"] == "COMPLETE"
    assert result["sha256"] == "a" * 64
    assert captured == {"content": b"apk-bytes", "filename": "sample.apk"}


def test_apk_endpoint_rejects_invalid_extension():
    upload = UploadFile(file=BytesIO(b"not-an-apk"), filename="sample.zip")

    with pytest.raises(HTTPException) as error:
        asyncio.run(main.analyze_apk_file(upload))

    assert error.value.status_code == 400
    assert error.value.detail["code"] == "APK_EXTENSION_REQUIRED"
