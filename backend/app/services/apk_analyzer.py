"""Defensive, non-executing static screening for Android APK archives."""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
import threading
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from pathlib import PurePosixPath
from typing import Any, Callable
from uuid import uuid4

from androguard.core.apk import APK


MAX_APK_SIZE = 100 * 1024 * 1024
MAX_UNCOMPRESSED_SIZE = 300 * 1024 * 1024
MAX_ENTRY_SIZE = 50 * 1024 * 1024
MAX_ENTRIES = 5000
MAX_COMPRESSION_RATIO = 100
MAX_CONCURRENT_ANALYSES = 2

_APK_SLOTS = threading.BoundedSemaphore(MAX_CONCURRENT_ANALYSES)
_KNOWN_SAMPLE_SHA256: frozenset[str] = frozenset()
_UPI_LIKE_PACKAGE_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]*(?:\.[a-zA-Z][a-zA-Z0-9_]*)+$")

SENSITIVE_PERMISSIONS = frozenset(
    {
        "android.permission.BIND_ACCESSIBILITY_SERVICE",
        "android.permission.CAMERA",
        "android.permission.INSTALL_PACKAGES",
        "android.permission.QUERY_ALL_PACKAGES",
        "android.permission.READ_CALL_LOG",
        "android.permission.READ_CONTACTS",
        "android.permission.READ_PHONE_STATE",
        "android.permission.READ_SMS",
        "android.permission.RECEIVE_SMS",
        "android.permission.RECORD_AUDIO",
        "android.permission.REQUEST_INSTALL_PACKAGES",
        "android.permission.SEND_SMS",
        "android.permission.SYSTEM_ALERT_WINDOW",
        "android.permission.WRITE_EXTERNAL_STORAGE",
    }
)


class APKAnalysisError(ValueError):
    """Safe, user-facing APK upload or archive validation failure."""

    def __init__(self, code: str, message: str, status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class APKAnalysisBusy(APKAnalysisError):
    """All bounded APK analysis slots are currently occupied."""

    def __init__(self):
        super().__init__(
            "APK_ANALYSIS_BUSY",
            "APK analysis is busy. Please retry shortly.",
            429,
        )


@dataclass(frozen=True)
class APKFinding:
    rule_id: str
    severity: str
    evidence: tuple[tuple[str, object], ...]
    explanation: str


@dataclass(frozen=True)
class APKAnalysisResult:
    analysis_id: str
    analyzed_at: datetime
    status: str
    filename: str
    sha256: str
    metadata: dict[str, object]
    findings: tuple[APKFinding, ...]
    parsing_errors: tuple[str, ...]
    limitations: tuple[str, ...]
    recommended_next_steps: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "analysis_id": self.analysis_id,
            "analyzed_at": self.analyzed_at.isoformat(),
            "status": self.status,
            "filename": self.filename,
            "sha256": self.sha256,
            "metadata": self.metadata,
            "findings": [
                {
                    "rule_id": finding.rule_id,
                    "severity": finding.severity,
                    "evidence": dict(finding.evidence),
                    "explanation": finding.explanation,
                }
                for finding in self.findings
            ],
            "parsing_errors": list(self.parsing_errors),
            "limitations": list(self.limitations),
            "recommended_next_steps": list(self.recommended_next_steps),
        }


def _finding(
    rule_id: str,
    severity: str,
    explanation: str,
    **evidence: object,
) -> APKFinding:
    return APKFinding(rule_id, severity, tuple(evidence.items()), explanation)


def _validate_entry_name(name: str) -> None:
    normalized = name.replace("\\", "/")
    path = PurePosixPath(normalized)
    if (
        not normalized
        or normalized.startswith("/")
        or ":" in path.parts[0]
        or ".." in path.parts
        or "\x00" in normalized
    ):
        raise APKAnalysisError(
            "APK_PATH_TRAVERSAL",
            "APK contains an unsafe archive path.",
        )


def _validate_archive(file_bytes: bytes) -> None:
    if len(file_bytes) > MAX_APK_SIZE:
        raise APKAnalysisError(
            "APK_TOO_LARGE",
            "APK exceeds the 100 MB upload limit.",
            413,
        )
    if not zipfile.is_zipfile(BytesIO(file_bytes)):
        raise APKAnalysisError(
            "APK_NOT_ZIP",
            "The uploaded file is not a valid APK archive.",
        )

    try:
        with zipfile.ZipFile(BytesIO(file_bytes)) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_ENTRIES:
                raise APKAnalysisError(
                    "APK_TOO_MANY_ENTRIES",
                    "APK contains too many archive entries.",
                )

            total_uncompressed = 0
            names = set()
            for entry in entries:
                _validate_entry_name(entry.filename)
                if entry.filename in names:
                    raise APKAnalysisError(
                        "APK_DUPLICATE_ENTRY",
                        "APK contains duplicate archive entries.",
                    )
                names.add(entry.filename)

                mode = (entry.external_attr >> 16) & 0o170000
                if mode == 0o120000:
                    raise APKAnalysisError(
                        "APK_SYMLINK_ENTRY",
                        "APK contains an unsafe symbolic-link entry.",
                    )
                if entry.flag_bits & 0x1:
                    raise APKAnalysisError(
                        "APK_ENCRYPTED_ENTRY",
                        "Encrypted APK entries are not supported.",
                    )
                if entry.file_size > MAX_ENTRY_SIZE:
                    raise APKAnalysisError(
                        "APK_ENTRY_TOO_LARGE",
                        "APK contains an oversized archive entry.",
                    )
                total_uncompressed += entry.file_size
                if total_uncompressed > MAX_UNCOMPRESSED_SIZE:
                    raise APKAnalysisError(
                        "APK_UNCOMPRESSED_TOO_LARGE",
                        "APK exceeds the decompression resource limit.",
                    )
                if entry.file_size and (
                    entry.compress_size == 0
                    or entry.file_size / entry.compress_size > MAX_COMPRESSION_RATIO
                ):
                    raise APKAnalysisError(
                        "APK_COMPRESSION_RATIO",
                        "APK contains a suspicious compression ratio.",
                    )

            required = {"AndroidManifest.xml"}
            if not required.issubset(names):
                raise APKAnalysisError(
                    "APK_MANIFEST_MISSING",
                    "APK does not contain AndroidManifest.xml.",
                )
            if not any(name.startswith("classes") and name.endswith(".dex") for name in names):
                raise APKAnalysisError(
                    "APK_DEX_MISSING",
                    "APK does not contain a Dalvik executable file.",
                )
            bad_entry = archive.testzip()
            if bad_entry is not None:
                raise APKAnalysisError(
                    "APK_CORRUPT_ENTRY",
                    "APK contains a corrupt archive entry.",
                )
    except APKAnalysisError:
        raise
    except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
        raise APKAnalysisError(
            "APK_ARCHIVE_INVALID",
            "The APK archive could not be safely inspected.",
        ) from exc


def _safe_call(
    parser: APK,
    method_name: str,
    parsing_errors: list[str],
    default: Any,
):
    try:
        return getattr(parser, method_name)()
    except Exception as exc:
        parsing_errors.append(f"{method_name}: {type(exc).__name__}")
        return default


def _extract_metadata(path: str) -> tuple[dict[str, object], list[str]]:
    parsing_errors: list[str] = []
    parser = APK(path, skip_analysis=True, testzip=False)

    package_name = _safe_call(parser, "get_package", parsing_errors, None)
    permissions = _safe_call(parser, "get_permissions", parsing_errors, []) or []
    activities = _safe_call(parser, "get_activities", parsing_errors, []) or []
    services = _safe_call(parser, "get_services", parsing_errors, []) or []
    receivers = _safe_call(parser, "get_receivers", parsing_errors, []) or []
    providers = _safe_call(parser, "get_providers", parsing_errors, []) or []

    signature_schemes: list[str] = []
    for scheme, method_name in (
        ("v1", "get_certificates_v1"),
        ("v2", "get_certificates_v2"),
        ("v3", "get_certificates_v3"),
    ):
        certificates = _safe_call(parser, method_name, parsing_errors, []) or []
        if certificates:
            signature_schemes.append(scheme)

    metadata = {
        "package_name": package_name,
        "version_code": _safe_call(parser, "get_androidversion_code", parsing_errors, None),
        "version_name": _safe_call(parser, "get_androidversion_name", parsing_errors, None),
        "permissions": sorted(str(item) for item in permissions),
        "components": {
            "activities": sorted(str(item) for item in activities),
            "services": sorted(str(item) for item in services),
            "receivers": sorted(str(item) for item in receivers),
            "providers": sorted(str(item) for item in providers),
        },
        "signing": {
            "status": "PRESENT" if signature_schemes else "NOT_FOUND",
            "schemes": signature_schemes,
            "trust_validation": "NOT_PERFORMED",
        },
    }
    return metadata, parsing_errors


def _build_findings(metadata: dict[str, object], sha256: str) -> tuple[APKFinding, ...]:
    permissions = set(metadata.get("permissions", []))
    findings: list[APKFinding] = []
    sensitive = sorted(permissions & SENSITIVE_PERMISSIONS)

    if len(sensitive) >= 3:
        findings.append(
            _finding(
                "APK_SENSITIVE_PERMISSION_CLUSTER",
                "MEDIUM",
                "The APK requests several sensitive permissions that require contextual review.",
                permissions=sensitive,
            )
        )
    if {
        "android.permission.BIND_ACCESSIBILITY_SERVICE",
        "android.permission.SYSTEM_ALERT_WINDOW",
    }.issubset(permissions):
        findings.append(
            _finding(
                "APK_ACCESSIBILITY_OVERLAY_COMBINATION",
                "HIGH",
                "Accessibility and overlay capabilities together warrant manual review; they are not proof of malicious behavior.",
                permissions=sorted(
                    {
                        "android.permission.BIND_ACCESSIBILITY_SERVICE",
                        "android.permission.SYSTEM_ALERT_WINDOW",
                    }
                ),
            )
        )
    if (
        "android.permission.REQUEST_INSTALL_PACKAGES" in permissions
        and permissions.intersection(
            {
                "android.permission.SEND_SMS",
                "android.permission.RECEIVE_SMS",
            }
        )
    ):
        findings.append(
            _finding(
                "APK_INSTALL_SMS_COMBINATION",
                "HIGH",
                "Install-package and SMS capabilities together warrant manual review.",
                permissions=sensitive,
            )
        )

    package_name = metadata.get("package_name")
    if not isinstance(package_name, str) or not _UPI_LIKE_PACKAGE_PATTERN.fullmatch(package_name):
        findings.append(
            _finding(
                "APK_PACKAGE_METADATA_UNAVAILABLE",
                "LOW",
                "A reliable conventional package name was not available from the manifest.",
                package_name=package_name,
            )
        )

    signing = metadata.get("signing") or {}
    if signing.get("status") == "NOT_FOUND":
        findings.append(
            _finding(
                "APK_SIGNATURE_UNAVAILABLE",
                "MEDIUM",
                "No signing certificate was reported by the parser; this does not establish malicious intent.",
                sha256=sha256,
            )
        )

    if sha256 in _KNOWN_SAMPLE_SHA256:
        findings.append(
            _finding(
                "APK_KNOWN_SAMPLE_FINGERPRINT",
                "HIGH",
                "The APK fingerprint matches a locally maintained test-sample list.",
                sha256=sha256,
            )
        )
    return tuple(findings)


def analyze_apk(
    file_bytes: bytes,
    filename: str,
    *,
    parser: Callable[[str], tuple[dict[str, object], list[str]]] | None = None,
) -> APKAnalysisResult:
    """Safely screen an APK without extracting or executing its contents."""
    if not isinstance(filename, str) or not filename.casefold().endswith(".apk"):
        raise APKAnalysisError(
            "APK_EXTENSION_REQUIRED",
            "Only files with an .apk extension are accepted.",
        )
    if not _APK_SLOTS.acquire(blocking=False):
        raise APKAnalysisBusy()

    analyzed_at = datetime.now(timezone.utc)
    analysis_id = str(uuid4())
    try:
        _validate_archive(file_bytes)
        sha256 = hashlib.sha256(file_bytes).hexdigest()
        with tempfile.TemporaryDirectory(prefix="vyaparguard-apk-") as directory:
            path = os.path.join(directory, "uploaded.apk")
            with open(path, "xb") as output:
                output.write(file_bytes)
            try:
                metadata, parsing_errors = (parser or _extract_metadata)(path)
            except Exception as exc:
                return APKAnalysisResult(
                    analysis_id,
                    analyzed_at,
                    "FAILED",
                    filename,
                    sha256,
                    {},
                    (),
                    (f"parser: {type(exc).__name__}",),
                    (
                        "Metadata parsing failed; no conclusion about app safety can be made.",
                    ),
                    ("Do not install the APK until its source and signature are checked.",),
                )

        status = "COMPLETE" if not parsing_errors else "PARTIAL"
        limitations = [
            "Static screening is not comprehensive malware detection.",
            "No live threat-intelligence feed is configured.",
            "Signature trust and real-world publisher identity were not validated.",
        ]
        if parsing_errors:
            limitations.append("Some metadata fields could not be parsed reliably.")
        return APKAnalysisResult(
            analysis_id,
            analyzed_at,
            status,
            filename,
            sha256,
            metadata,
            _build_findings(metadata, sha256),
            tuple(parsing_errors),
            tuple(limitations),
            ("Avoid installation until the app source and authenticity are checked.",),
        )
    finally:
        _APK_SLOTS.release()
