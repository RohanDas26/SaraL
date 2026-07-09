"""
routes/revision_routes.py
"""
import json
from flask import Blueprint, request, jsonify
from backend.extensions import limiter
from backend.config import Config
from backend.services.llm_service import get_llm
from backend.services.rag_service import retrieve_context
from backend.services.document_service import get_document
from backend.services.cache_service import get_cached, set_cached
from backend.utils.prompt_utils import build_revision_prompt, build_important_points_prompt

revision_bp = Blueprint("revision", __name__, url_prefix="/api/revision")
_RATE = f"{Config.RATE_LIMIT_PER_MINUTE} per minute;{Config.RATE_LIMIT_PER_DAY} per day"

VALID_TYPES = {"flashcards", "quick_notes", "exam_sheet"}


@revision_bp.route("/generate", methods=["POST"])
@limiter.limit(_RATE)
def generate_revision():
    """
    POST /api/revision/generate
    Body: {"doc_id": int, "type": "flashcards|quick_notes|exam_sheet", "count": int}
    """
    data  = request.get_json(silent=True) or {}
    doc_id = data.get("doc_id")
    rev_type = (data.get("type") or "quick_notes").lower()
    count    = min(max(int(data.get("count", 10)), 5), 30)

    if not doc_id:
        return jsonify({"error": "doc_id is required."}), 400
    if rev_type not in VALID_TYPES:
        return jsonify({"error": f"type must be one of: {', '.join(VALID_TYPES)}."}), 400

    doc = get_document(int(doc_id))
    if not doc or doc["status"] != "indexed":
        return jsonify({"error": "Document not found or not yet indexed."}), 404

    cache_key = f"revision:{rev_type}:{count}"
    cached = get_cached(cache_key, doc_id)
    if cached:
        payload = json.loads(cached) if rev_type == "flashcards" else cached
        return jsonify({"result": payload, "cached": True}), 200

    context, _ = retrieve_context(
        "revision study material key concepts",
        doc_ids=[int(doc_id)],
        top_k=8,
    )
    if not context:
        return jsonify({"error": "No content found for this document."}), 404

    prompt = build_revision_prompt(context, rev_type, count)
    try:
        raw = get_llm().generate(prompt, max_new_tokens=1200)
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 503

    if rev_type == "flashcards":
        result = _parse_flashcard_json(raw)
        if not result:
            return jsonify({"error": "Could not parse flashcards from AI response."}), 500
        set_cached(cache_key, doc_id, json.dumps(result))
        return jsonify({"result": result, "cached": False}), 200
    else:
        set_cached(cache_key, doc_id, raw)
        return jsonify({"result": raw, "cached": False}), 200


@revision_bp.route("/important-points", methods=["POST"])
@limiter.limit(_RATE)
def important_points():
    """
    POST /api/revision/important-points
    Body: {"doc_id": int}
    """
    data   = request.get_json(silent=True) or {}
    doc_id = data.get("doc_id")

    if not doc_id:
        return jsonify({"error": "doc_id is required."}), 400

    doc = get_document(int(doc_id))
    if not doc or doc["status"] != "indexed":
        return jsonify({"error": "Document not found or not yet indexed."}), 404

    cached = get_cached("important_points", doc_id)
    if cached:
        return jsonify({"result": cached, "cached": True}), 200

    context, _ = retrieve_context(
        "key formulas definitions important concepts",
        doc_ids=[int(doc_id)],
        top_k=8,
    )
    if not context:
        return jsonify({"error": "No content found for this document."}), 404

    prompt = build_important_points_prompt(context)
    try:
        result = get_llm().generate(prompt, max_new_tokens=1000)
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 503

    set_cached("important_points", doc_id, result)
    return jsonify({"result": result, "cached": False}), 200


def _parse_flashcard_json(raw: str) -> list | None:
    raw = raw.strip()
    start = raw.find("[")
    end   = raw.rfind("]")
    if start == -1 or end == -1:
        return None
    try:
        return json.loads(raw[start:end + 1])
    except json.JSONDecodeError:
        return None
