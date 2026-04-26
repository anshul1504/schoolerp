from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess
import tempfile

from PIL import Image


@dataclass(frozen=True)
class UploadPolicy:
    max_bytes: int
    allowed_extensions: set[str]
    allowed_image_formats: set[str] | None = None


DEFAULT_IMAGE_POLICY = UploadPolicy(
    max_bytes=2 * 1024 * 1024,  # 2MB
    allowed_extensions={".png", ".jpg", ".jpeg", ".webp", ".gif", ".ico"},
    allowed_image_formats={"PNG", "JPEG", "WEBP", "GIF", "ICO"},
)

DEFAULT_DOCUMENT_POLICY = UploadPolicy(
    max_bytes=5 * 1024 * 1024,  # 5MB
    allowed_extensions={".pdf", ".png", ".jpg", ".jpeg"},
    allowed_image_formats={"PNG", "JPEG"},
)


def _ext(name: str) -> str:
    try:
        return Path(name or "").suffix.lower()
    except Exception:
        return ""


def validate_upload(upload, *, policy: UploadPolicy, kind: str) -> list[str]:
    """
    Validates a Django UploadedFile against a centralized policy.

    Returns a list of human-readable validation errors (empty list means OK).
    """
    errors: list[str] = []
    if not upload:
        return errors

    name = getattr(upload, "name", "") or ""
    size = int(getattr(upload, "size", 0) or 0)
    ext = _ext(name)

    if ext not in policy.allowed_extensions:
        errors.append(f"{kind}: unsupported file type ({ext or 'no extension'})")

    if policy.max_bytes and size and size > policy.max_bytes:
        max_mb = round(policy.max_bytes / (1024 * 1024), 1)
        errors.append(f"{kind}: file too large (max {max_mb}MB)")

    # Lightweight file signature checks (magic bytes) for common risky types.
    if ext == ".pdf":
        pos = None
        try:
            pos = upload.tell()
        except Exception:
            pos = None
        try:
            head = upload.read(5) or b""
            if head != b"%PDF-":
                errors.append(f"{kind}: invalid PDF file")
        except Exception:
            errors.append(f"{kind}: could not read file")
        finally:
            try:
                if pos is not None:
                    upload.seek(pos)
                else:
                    upload.seek(0)
            except Exception:
                pass

    image_exts = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".ico"}

    if policy.allowed_image_formats is not None and ext in image_exts:
        pos = None
        try:
            pos = upload.tell()
        except Exception:
            pos = None
        try:
            img = Image.open(upload)
            img.verify()
            fmt = (img.format or "").upper()
            if fmt not in policy.allowed_image_formats:
                errors.append(f"{kind}: unsupported image format ({fmt or 'unknown'})")
        except Exception:
            errors.append(f"{kind}: invalid/corrupted image")
        finally:
            try:
                if pos is not None:
                    upload.seek(pos)
                else:
                    upload.seek(0)
            except Exception:
                pass

    errors.extend(antivirus_scan(upload, kind=kind))
    return errors


def antivirus_scan(upload, *, kind: str) -> list[str]:
    """
    Optional antivirus scan hook.

    Default behavior is controlled via settings:
    - `ANTIVIRUS_SCAN_MODE="off"` (default): no-op
    - `ANTIVIRUS_SCAN_MODE="best_effort"`: scan if available; skip silently if not
    - `ANTIVIRUS_SCAN_MODE="required"`: fail upload if scanner isn't available or scan errors

    Current implementation supports ClamAV CLI (`clamscan`) when installed on the host.
    """
    from django.conf import settings

    mode = str(getattr(settings, "ANTIVIRUS_SCAN_MODE", "off") or "off").strip().lower()
    if mode not in {"off", "best_effort", "required"}:
        mode = "off"

    if mode == "off":
        return []

    scanner = shutil.which("clamscan")
    if not scanner:
        if mode == "required":
            return [f"{kind}: antivirus scanner not available"]
        return []

    pos = None
    try:
        pos = upload.tell()
    except Exception:
        pos = None

    try:
        suffix = _ext(getattr(upload, "name", "") or "") or ".bin"
        with tempfile.NamedTemporaryFile(prefix="upload_scan_", suffix=suffix, delete=True) as tmp:
            try:
                upload.seek(0)
            except Exception:
                pass
            try:
                for chunk in upload.chunks():
                    tmp.write(chunk)
            except Exception:
                # Fallback for non-chunked file-like objects.
                tmp.write(upload.read() or b"")
            tmp.flush()

            proc = subprocess.run(
                [scanner, "--no-summary", tmp.name],
                capture_output=True,
                text=True,
                timeout=int(getattr(settings, "ANTIVIRUS_SCAN_TIMEOUT_SECONDS", 20)),
            )

            # clamscan exit codes: 0=no virus, 1=virus found, 2=error.
            if proc.returncode == 0:
                return []
            if proc.returncode == 1:
                details = (proc.stdout or proc.stderr or "").strip()
                if details:
                    details = details[:400]
                    return [f"{kind}: malware detected ({details})"]
                return [f"{kind}: malware detected"]

            if mode == "required":
                details = (proc.stderr or proc.stdout or "").strip()
                details = (details[:400] if details else "scanner error")
                return [f"{kind}: antivirus scan failed ({details})"]
            return []

    except Exception:
        if mode == "required":
            return [f"{kind}: antivirus scan failed"]
        return []
    finally:
        try:
            if pos is not None:
                upload.seek(pos)
            else:
                upload.seek(0)
        except Exception:
            pass
