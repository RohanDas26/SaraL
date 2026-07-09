"""
routes/document_routes.py — Document upload, listing, deletion, and status endpoints.

Upload flow:
  1. Validate file (extension + MIME + magic bytes)
  2. Read bytes, compute SHA-256 hash
  3. Reject duplicate (hash already in SQLite)
  4. Enforce size limit
  5. Generate UUID filename, save bytes to uploads/
  6. Insert SQLite record (status='pending')
  7. Start background ingestion thread
  8. Return doc_id immediately (frontend polls /status)
"""

import os
from flask import Blueprint, request, jsonify

from backend.config import Config
from backend.database import get_db
from backend.utils.logger import get_logger
from backend.utils.file_utils import (
    FileValidationError,
    validate_upload,
    make_uuid_filename,
    compute_sha256,
    check_duplicate,
    human_readable_size,
)
from backend.services.document_service import (
    start_processing,
    delete_document,
    get_all_documents,
    get_document,
)

log = get_logger(__name__)

documents_bp = Blueprint("documents", __name__, url_prefix="/api/documents")

_LIMIT_MB = Config.MAX_CONTENT_LENGTH // (1024 * 1024)


# ── POST /api/documents/upload ─────────────────────────────────────────

@documents_bp.route("/upload", methods=["POST"])
def upload():
    """
    Accepts multipart/form-data with a single 'file' field.
    Responds with the document record and status='pending' immediately.
    The frontend should poll GET /api/documents/<id>/status.
    """
    if "file" not in request.files:
        return jsonify({"error": "No file provided. Include a 'file' field in the form data."}), 400

    file = request.files["file"]

    if not file.filename:
        return jsonify({"error": "No file selected."}), 400

    # ── Layer 1-3: extension + MIME + magic bytes ──────────────────────
    try:
        ext, raw_bytes = validate_upload(file)
    except FileValidationError as exc:
        log.warning("Upload rejected (validation): %s", exc)
        return jsonify({"error": str(exc)}), 400

    # ── Size check ─────────────────────────────────────────────────────
    file_size = len(raw_bytes)
    if file_size > Config.MAX_CONTENT_LENGTH:
        return jsonify({
            "error": f"File size {human_readable_size(file_size)} exceeds the "
                     f"{_LIMIT_MB} MB upload limit."
        }), 413

    if file_size == 0:
        return jsonify({"error": "The uploaded file is empty."}), 400

    # ── SHA-256 deduplication ──────────────────────────────────────────
    file_hash    = compute_sha256(raw_bytes)
    existing_doc = check_duplicate(file_hash)
    if existing_doc:
        log.info(
            "Duplicate upload rejected: hash=%s existing_doc_id=%d",
            file_hash[:12] + "...", existing_doc["id"],
        )
        return jsonify({
            "error": (
                f"This file has already been uploaded as "
                f"'{existing_doc['display_name']}' (status: {existing_doc['status']}). "
                "Delete the existing document first if you want to re-upload."
            ),
            "duplicate_doc_id": existing_doc["id"],
        }), 409

    # ── Save file to disk ──────────────────────────────────────────────
    display_name  = file.filename                 # original name — for display only
    uuid_filename = make_uuid_filename(ext)       # safe internal name on disk
    file_path     = os.path.join(Config.UPLOAD_FOLDER, uuid_filename)
    file_size_kb  = max(1, file_size // 1024)

    os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
    with open(file_path, "wb") as fh:
        fh.write(raw_bytes)

    log.info(
        "File saved: display_name='%s' uuid='%s' size=%s",
        display_name, uuid_filename, human_readable_size(file_size),
    )

    # ── Create SQLite record ───────────────────────────────────────────
    conn = get_db()
    try:
        cursor = conn.execute(
            """INSERT INTO documents
               (filename, display_name, file_path, file_type, file_size_kb, file_hash, status)
               VALUES (?, ?, ?, ?, ?, ?, 'pending')""",
            (uuid_filename, display_name, file_path, ext, file_size_kb, file_hash),
        )
        doc_id = cursor.lastrowid
        conn.commit()
    finally:
        conn.close()

    log.info("Document record created: doc_id=%d", doc_id)

    # ── Start async ingestion ──────────────────────────────────────────
    start_processing(doc_id)

    doc = get_document(doc_id)
    return jsonify({
        "message": "File uploaded. Processing started.",
        "document": doc,
    }), 202    # 202 Accepted — processing is async


# ── GET /api/documents/ ────────────────────────────────────────────────

@documents_bp.route("/", methods=["GET"])
def list_documents():
    """List all documents with metadata."""
    docs = get_all_documents()
    return jsonify({"documents": docs}), 200


# ── GET /api/documents/<id> ────────────────────────────────────────────

@documents_bp.route("/<int:doc_id>", methods=["GET"])
def get_doc(doc_id: int):
    """Get a single document's full metadata."""
    doc = get_document(doc_id)
    if not doc:
        return jsonify({"error": f"Document {doc_id} not found."}), 404
    return jsonify({"document": doc}), 200


# ── DELETE /api/documents/<id> ─────────────────────────────────────────

@documents_bp.route("/<int:doc_id>", methods=["DELETE"])
def delete_doc(doc_id: int):
    """Delete a document, its vectors, its file, and cache entries."""
    doc = get_document(doc_id)
    if not doc:
        return jsonify({"error": f"Document {doc_id} not found."}), 404

    if doc["status"] == "processing":
        return jsonify({
            "error": "Cannot delete a document that is currently being processed. "
                     "Wait for indexing to complete or fail."
        }), 409

    try:
        delete_document(doc_id)
        return jsonify({"message": f"Document '{doc['display_name']}' deleted."}), 200
    except Exception as exc:
        log.error("Failed to delete doc_id=%d: %s", doc_id, exc)
        return jsonify({"error": str(exc)}), 500


# ── GET /api/documents/<id>/status ────────────────────────────────────

@documents_bp.route("/<int:doc_id>/status", methods=["GET"])
def doc_status(doc_id: int):
    """
    Poll endpoint for processing progress.
    Returns status, progress_pct (0-100), chunk_count, page_count.
    """
    doc = get_document(doc_id)
    if not doc:
        return jsonify({"error": f"Document {doc_id} not found."}), 404

    return jsonify({
        "doc_id":      doc_id,
        "status":      doc["status"],
        "progress_pct": doc.get("progress_pct", 0),
        "chunk_count": doc["chunk_count"],
        "page_count":  doc["page_count"],
        "error":       doc["error_message"],
    }), 200
