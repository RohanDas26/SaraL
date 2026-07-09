"""
routes/simplify_routes.py
"""
from flask import Blueprint, request, jsonify
from backend.extensions import limiter
from backend.config import Config
from backend.services.llm_service import get_llm
from backend.services.cache_service import get_cached, set_cached
from backend.utils.prompt_utils import build_simplify_prompt

simplify_bp = Blueprint("simplify", __name__, url_prefix="/api")
_RATE = f"{Config.RATE_LIMIT_PER_MINUTE} per minute;{Config.RATE_LIMIT_PER_DAY} per day"

VALID_LEVELS = {"beginner", "intermediate", "advanced"}


@simplify_bp.route("/simplify", methods=["POST"])
@limiter.limit(_RATE)
def simplify():
    """
    POST /api/simplify
    Body: {"text": string, "level": "beginner|intermediate|advanced", "no_cache": bool}
    When no_cache=true (sent by the Regenerate button), the cache lookup is skipped
    so the LLM is always called fresh.  The result is still stored in cache afterward.
    """
    data     = request.get_json(silent=True) or {}
    text     = (data.get("text") or "").strip()
    level    = (data.get("level") or "intermediate").lower()
    no_cache = bool(data.get("no_cache", False))

    if not text:
        return jsonify({"error": "Text cannot be empty."}), 400
    if level not in VALID_LEVELS:
        return jsonify({"error": f"Level must be one of: {', '.join(VALID_LEVELS)}."}), 400

    if not no_cache:
        cached = get_cached(f"simplify:{text}", level)
        if cached:
            return jsonify({"result": cached, "cached": True}), 200

    prompt = build_simplify_prompt(text, level)
    try:
        result = get_llm().generate(prompt)
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 503

    set_cached(f"simplify:{text}", level, result)
    return jsonify({"result": result, "cached": False}), 200
