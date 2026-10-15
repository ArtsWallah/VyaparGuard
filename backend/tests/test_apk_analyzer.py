from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from app.services import apk_analyzer
from app.services.apk_analyzer import (
    APKAnalysisError,
    analyze_apk,
)


def apk_bytes(*, extra_entries=None, manifest=b"manifest", dex=b"dex"):
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        archive.writestr("AndroidManifest.xml", manifest)
        archive.writestr("classes.dex", dex)
        for name, data in extra_entries or []:
            archive.writestr(name, data)
    return buffer.getvalue()


def fake_parser(_path):
    return (
        {
            "package_name": "com.example.benign",
            "version_code": 1,
            "version_name": "1.0",
            "permissions": ["android.permission.INTERNET"],
            "components": {
                "activities": [".MainActivity"],
                "services": [],
                "receivers": [],
                "providers": [],
            },
            "signing": {
                "status": "PRESENT",
                "schemes": ["v2"],
                "trust_validation": "NOT_PERFORMED",
            },
        },
        [],
    )


def test_valid_benign_fixture_completes_without_false_positive():
    result = analyze_apk(
        apk_bytes(),
        "benign.apk",
        parser=fake_parser,
    )

    assert result.status == "COMPLETE"
    assert result.metadata["package_name"] == "com.example.benign"
    assert result.findings == ()
    assert len(result.sha256) == 64


def test_non_apk_extension_is_rejected():
    with pytest.raises(APKAnalysisError, match=r"\.apk"):
        analyze_apk(apk_bytes(), "benign.zip", parser=fake_parser)


def test_non_zip_file_renamed_apk_is_rejected():
    with pytest.raises(APKAnalysisError, match="valid APK archive"):
        analyze_apk(b"not an apk", "renamed.apk", parser=fake_parser)


def test_oversized_input_is_rejected():
    with pytest.raises(APKAnalysisError, match="100 MB"):
        analyze_apk(b"x" * (100 * 1024 * 1024 + 1), "large.apk")


def test_path_traversal_entry_is_rejected():
    with pytest.raises(APKAnalysisError, match="unsafe archive path"):
        analyze_apk(
            apk_bytes(extra_entries=[("../payload", b"x")]),
            "unsafe.apk",
            parser=fake_parser,
        )


def test_absolute_entry_is_rejected():
    with pytest.raises(APKAnalysisError, match="unsafe archive path"):
        analyze_apk(
            apk_bytes(extra_entries=[("/payload", b"x")]),
            "unsafe.apk",
            parser=fake_parser,
        )


def test_missing_manifest_is_rejected():
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        archive.writestr("classes.dex", b"dex")

    with pytest.raises(APKAnalysisError, match="AndroidManifest"):
        analyze_apk(buffer.getvalue(), "missing-manifest.apk", parser=fake_parser)


def test_missing_dex_is_rejected():
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        archive.writestr("AndroidManifest.xml", b"manifest")

    with pytest.raises(APKAnalysisError, match="Dalvik"):
        analyze_apk(buffer.getvalue(), "missing-dex.apk", parser=fake_parser)


def test_parser_failure_returns_failed_status():
    def failing_parser(_path):
        raise TimeoutError("parser timeout")

    result = analyze_apk(apk_bytes(), "parser-failure.apk", parser=failing_parser)

    assert result.status == "FAILED"
    assert "TimeoutError" in result.parsing_errors[0]
    assert result.findings == ()


def test_missing_metadata_returns_partial_status():
    def partial_parser(_path):
        return {"package_name": None, "permissions": []}, ["manifest: ValueError"]

    result = analyze_apk(apk_bytes(), "partial.apk", parser=partial_parser)

    assert result.status == "PARTIAL"
    assert result.parsing_errors == ("manifest: ValueError",)


def test_sensitive_permission_rules_are_conservative():
    def permission_parser(_path):
        metadata, errors = fake_parser(_path)
        metadata["permissions"] = [
            "android.permission.CAMERA",
            "android.permission.INTERNET",
        ]
        return metadata, errors

    result = analyze_apk(apk_bytes(), "permissions.apk", parser=permission_parser)

    assert result.status == "COMPLETE"
    assert result.findings == ()


def test_sensitive_permission_combination_is_explained():
    def permission_parser(_path):
        metadata, errors = fake_parser(_path)
        metadata["permissions"] = [
            "android.permission.BIND_ACCESSIBILITY_SERVICE",
            "android.permission.SYSTEM_ALERT_WINDOW",
        ]
        return metadata, errors

    result = analyze_apk(apk_bytes(), "permissions.apk", parser=permission_parser)

    assert any(
        finding.rule_id == "APK_ACCESSIBILITY_OVERLAY_COMBINATION"
        and finding.severity == "HIGH"
        for finding in result.findings
    )


def test_same_file_has_same_fingerprint_and_no_network_lookup():
    first = analyze_apk(apk_bytes(), "one.apk", parser=fake_parser)
    second = analyze_apk(apk_bytes(), "two.apk", parser=fake_parser)

    assert first.sha256 == second.sha256
    assert any("no live threat" in limitation.lower() for limitation in first.limitations)


def test_temp_directory_is_cleaned_after_analysis(monkeypatch, tmp_path):
    created: list[Path] = []
    real_temporary_directory = apk_analyzer.tempfile.TemporaryDirectory

    def tracked_directory(*args, **kwargs):
        directory = real_temporary_directory(*args, dir=tmp_path, **kwargs)
        created.append(Path(directory.name))
        return directory

    monkeypatch.setattr(
        apk_analyzer.tempfile,
        "TemporaryDirectory",
        tracked_directory,
    )
    analyze_apk(apk_bytes(), "cleanup.apk", parser=fake_parser)

    assert created
    assert all(not directory.exists() for directory in created)
