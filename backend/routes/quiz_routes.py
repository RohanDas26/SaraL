"""
routes/quiz_routes.py
"""
import json
from flask import Blueprint, request, jsonify
from backend.extensions import limiter
from backend.config import Config
from backend.services.llm_service import get_llm
from backend.services.rag_service import retrieve_context
from backend.services.document_service import get_document
from backend.services.cache_service import get_cached, set_cached
from backend.utils.prompt_utils import build_quiz_prompt

quiz_bp = Blueprint("quiz", __name__, url_prefix="/api/quiz")
_RATE = f"{Config.RATE_LIMIT_PER_MINUTE} per minute;{Config.RATE_LIMIT_PER_DAY} per day"

VALID_TYPES       = {"mcq", "true_false", "short", "long"}
VALID_DIFFICULTIES = {"easy", "medium", "hard"}


@quiz_bp.route("/generate", methods=["POST"])
@limiter.limit(_RATE)
def generate_quiz():
    """
    POST /api/quiz/generate
    Body: {
        "doc_id":     int,
        "type":       "mcq|true_false|short|long",
        "count":      int (1–20),
        "difficulty": "easy|medium|hard"
    }
    """
    data       = request.get_json(silent=True) or {}
    doc_id     = data.get("doc_id")
    quiz_type  = (data.get("type") or "mcq").lower()
    count      = min(max(int(data.get("count", 5)), 1), 20)
    difficulty = (data.get("difficulty") or "medium").lower()

    if not doc_id:
        return jsonify({"error": "doc_id is required."}), 400
    if quiz_type not in VALID_TYPES:
        return jsonify({"error": f"type must be one of: {', '.join(VALID_TYPES)}."}), 400
    if difficulty not in VALID_DIFFICULTIES:
        return jsonify({"error": f"difficulty must be one of: {', '.join(VALID_DIFFICULTIES)}."}), 400

    doc = get_document(int(doc_id))
    if not doc or doc["status"] != "indexed":
        return jsonify({"error": "Document not found or not yet indexed."}), 404

    cache_key = f"quiz:{quiz_type}:{count}:{difficulty}"
    cached = get_cached(cache_key, doc_id)
    if cached:
        return jsonify({"questions": json.loads(cached), "cached": True}), 200

    context, _ = retrieve_context(
        f"generate {quiz_type} questions",
        doc_ids=[int(doc_id)],
        top_k=6,
    )
    if not context:
        return jsonify({"error": "No content found for this document."}), 404

    prompt = build_quiz_prompt(context, quiz_type, count, difficulty)
    try:
        raw = get_llm().generate(prompt, max_new_tokens=1200)
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 503

    # Parse JSON output from the model
    questions = _parse_quiz_json(raw)
    if not questions:
        return jsonify({"error": "Could not parse quiz from AI response. Please try again."}), 500

    set_cached(cache_key, doc_id, json.dumps(questions))
    return jsonify({"questions": questions, "cached": False}), 200


def _parse_quiz_json(raw: str) -> list | None:
    """
    Extract the JSON array from the model's raw text output.
    The model is instructed to return only JSON, but may include
    preamble text — this function strips it.
    """
    raw = raw.strip()
    # Find the first '[' and last ']'
    start = raw.find("[")
    end   = raw.rfind("]")
    if start == -1 or end == -1:
        return None
    try:
        return json.loads(raw[start:end + 1])
    except json.JSONDecodeError:
        return None
