"""
routes/explain_routes.py
"""
from flask import Blueprint, request, jsonify
from backend.extensions import limiter
from backend.config import Config
from backend.services.llm_service import get_llm
from backend.services.rag_service import retrieve_context
from backend.services.cache_service import get_cached, set_cached
from backend.utils.prompt_utils import build_explain_prompt

explain_bp = Blueprint("explain", __name__, url_prefix="/api")
_RATE = f"{Config.RATE_LIMIT_PER_MINUTE} per minute;{Config.RATE_LIMIT_PER_DAY} per day"


@explain_bp.route("/explain", methods=["POST"])
@limiter.limit(_RATE)
def explain():
    """
    POST /api/explain
    Body: {"term": string, "doc_id": int (optional)}
    """
    data   = request.get_json(silent=True) or {}
    term   = (data.get("term") or "").strip()
    doc_id = data.get("doc_id")

    if not term:
        return jsonify({"error": "Term cannot be empty."}), 400

    cached = get_cached(f"explain:{term}", doc_id)
    if cached:
        return jsonify({"result": cached, "cached": True}), 200

    context = ""
    if doc_id:
        context, _ = retrieve_context(term, doc_ids=[int(doc_id)], top_k=3)

    prompt = build_explain_prompt(term, context)
    try:
        result = get_llm().generate(prompt)
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 503

    set_cached(f"explain:{term}", doc_id, result)
    return jsonify({"result": result, "cached": False}), 200
