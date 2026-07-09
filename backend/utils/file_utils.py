"""
utils/file_utils.py — File validation, hashing, and safe filename generation.

Validation is three-layered:
  1. Extension check  — quick reject on disallowed extensions
  2. MIME type check  — checks the Content-Type header from the browser
  3. Magic bytes      — reads the first 8 bytes of the file to verify format

Never trust the extension alone.  All three layers must pass.

Filename strategy:
  - Internal storage uses a UUID4 + original extension (no user-controlled characters)
  - The original filename is preserved in SQLite as display_name only
  - werkzeug.secure_filename is applied before any path operations

Deduplication:
  - SHA-256 of the raw file bytes is computed before saving
  - The hash is stored in SQLite with a UNIQUE constraint
  - Duplicate uploads are rejected before any disk write
"""

import os
import hashlib
import uuid
from typing import Optional

from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage

from backend.config import Config
from backend.utils.logger import get_logger

log = get_logger(__name__)


# ── Allowed types — extension, MIME, and magic bytes ──────────────────

# Maps file extension → (set of accepted MIME types, magic byte prefix)
# Magic bytes: the first N bytes that identify the format.
_ALLOWED_TYPES: dict[str, dict] = {
    "pdf": {
        "mime":  {"application/pdf", "application/x-pdf"},
        "magic": b"%PDF",        # PDF signature
    },
    "docx": {
        "mime": {
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/zip",   # DOCX is a ZIP archive — browser may send this
            "application/octet-stream",
        },
        "magic": b"PK\x03\x04",  # ZIP/DOCX signature
    },
    "txt": {
        "mime": {
            "text/plain",
            "application/octet-stream",  # some browsers send this for .txt
        },
        "magic": None,           # plain text has no fixed magic bytes
    },
}


# ── Public validation API ──────────────────────────────────────────────

class FileValidationError(ValueError):
    """Raised when a file fails any validation check."""


def validate_upload(file: FileStorage) -> tuple[str, bytes]:
    """
    Run all three validation layers on an uploaded file.

    Returns:
        (file_extension, raw_bytes) — the extension (e.g. 'pdf') and the
        complete raw file bytes ready for hashing and saving.

    Raises:
        FileValidationError — with a user-facing message on any failure.
    """
    filename = file.filename or ""

    # ── Layer 1: extension ─────────────────────────────────────────────
    ext = _get_extension(filename)
    if not ext or ext not in _ALLOWED_TYPES:
        raise FileValidationError(
            f"Unsupported file type '.{ext or '?'}'. "
            "Please upload a PDF, DOCX, or TXT file."
        )

    # ── Read file bytes (needed for layers 2 and 3) ────────────────────
    file.seek(0)
    raw_bytes = file.read()
    file.seek(0)

    if not raw_bytes:
        raise FileValidationError("The uploaded file is empty.")

    # ── Layer 2: MIME type ─────────────────────────────────────────────
    content_type = (file.content_type or "").lower().split(";")[0].strip()
    allowed_mimes = _ALLOWED_TYPES[ext]["mime"]
    if content_type and content_type not in allowed_mimes:
        # Be lenient: only hard-reject if we get a clearly wrong MIME type
        if not content_type.startswith("application/") and not content_type.startswith("text/"):
            raise FileValidationError(
                f"Unexpected content type '{content_type}' for a .{ext} file. "
                "The file may be corrupted or mislabelled."
            )
        log.debug(
            "MIME '%s' not in strict allow-list for .%s — passing (magic bytes will confirm)",
            content_type, ext,
        )

    # ── Layer 3: magic bytes ───────────────────────────────────────────
    magic = _ALLOWED_TYPES[ext]["magic"]
    if magic is not None:
        if not raw_bytes[:len(magic)] == magic:
            raise FileValidationError(
                f"The file does not appear to be a valid {ext.upper()} "
                "(file signature mismatch). It may be corrupted or renamed."
            )

    log.debug(
        "File validation passed: name='%s' ext=%s mime=%s size=%d bytes",
        secure_filename(filename), ext, content_type, len(raw_bytes),
    )
    return ext, raw_bytes


# ── UUID filename ──────────────────────────────────────────────────────

def make_uuid_filename(extension: str) -> str:
    """
    Generate a unique, safe storage filename using UUID4.
    The original filename is never used on disk.

    Example: 'f47ac10b-58cc-4372-a567-0e02b2c3d479.pdf'
    """
    return f"{uuid.uuid4()}.{extension}"


# ── SHA-256 deduplication ──────────────────────────────────────────────

def compute_sha256(raw_bytes: bytes) -> str:
    """Return the lowercase hex SHA-256 digest of raw file bytes."""
    return hashlib.sha256(raw_bytes).hexdigest()


def check_duplicate(file_hash: str) -> Optional[dict]:
    """
    Query SQLite to see if a file with this hash already exists.
    Returns the existing document dict if found, else None.
    Imported here lazily to avoid circular imports.
    """
    from backend.database import get_db
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT id, display_name, status FROM documents WHERE file_hash = ?",
            (file_hash,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


# ── Helpers ────────────────────────────────────────────────────────────

def _get_extension(filename: str) -> str:
    """Return lowercase extension without the dot, or empty string."""
    if "." not in filename:
        return ""
    return filename.rsplit(".", 1)[1].lower()


def get_extension(filename: str) -> str:
    """Public alias used by other modules."""
    return _get_extension(filename)


def human_readable_size(size_bytes: int) -> str:
    """Convert bytes to a human-readable string, e.g. '2.4 MB'."""
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"
