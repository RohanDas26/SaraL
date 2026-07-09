"""
routes/summary_routes.py
"""
from flask import Blueprint, request, jsonify
from backend.extensions import limiter
from backend.config import Config
from backend.services.llm_service import get_llm
from backend.services.rag_service import retrieve_context
from backend.services.document_service import get_document
from backend.services.cache_service import get_cached, set_cached
from backend.utils.prompt_utils import build_summary_prompt

summary_bp = Blueprint("summary", __name__, url_prefix="/api")
_RATE = f"{Config.RATE_LIMIT_PER_MINUTE} per minute;{Config.RATE_LIMIT_PER_DAY} per day"

VALID_TYPES = {"short", "detailed", "bullet", "one_minute", "exam_notes"}


@summary_bp.route("/summary", methods=["POST"])
@limiter.limit(_RATE)
def summary():
    """
    POST /api/summary
    Body: {"doc_id": int, "type": "short|detailed|bullet|one_minute|exam_notes"}
    """
    data     = request.get_json(silent=True) or {}
    doc_id   = data.get("doc_id")
    sum_type = (data.get("type") or "short").lower()

    if not doc_id:
        return jsonify({"error": "doc_id is required."}), 400
    if sum_type not in VALID_TYPES:
        return jsonify({"error": f"type must be one of: {', '.join(VALID_TYPES)}."}), 400

    doc = get_document(int(doc_id))
    if not doc or doc["status"] != "indexed":
        return jsonify({"error": "Document not found or not yet indexed."}), 404

    cached = get_cached(f"summary:{sum_type}", doc_id)
    if cached:
        return jsonify({"result": cached, "cached": True}), 200

    # Retrieve broad context (use more chunks for summaries)
    context, _ = retrieve_context(
        "summarize the document",
        doc_ids=[int(doc_id)],
        top_k=8,
    )
    if not context:
        return jsonify({"error": "No content found for this document."}), 404

    prompt = build_summary_prompt(context, sum_type)
    try:
        result = get_llm().generate(prompt, max_new_tokens=1000)
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 503

    set_cached(f"summary:{sum_type}", doc_id, result)
    return jsonify({"result": result, "cached": False}), 200
