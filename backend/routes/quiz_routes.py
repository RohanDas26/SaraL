"""
routes/quiz_routes.py
"""
import json
import random
import re
from flask import Blueprint, request, jsonify
from backend.extensions import limiter
from backend.config import Config
from backend.services.llm_service import get_llm
from backend.services.rag_service import retrieve_context
from backend.services.document_service import get_document
from backend.services.cache_service import get_cached, set_cached
from backend.utils.prompt_utils import build_quiz_prompt
from backend.utils.json_utils import parse_llm_json_array

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
        top_k=15,
    )
    if not context:
        return jsonify({"error": "No content found for this document."}), 404

    prompt = build_quiz_prompt(context, quiz_type, count, difficulty)
    try:
        raw = get_llm().generate(prompt, max_new_tokens=3000)
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 503

    # Parse JSON output from the model
    questions = parse_llm_json_array(raw)
    if not questions:
        return jsonify({"error": "Could not parse quiz from AI response. Please try again."}), 500

    # Shuffle MCQ options so the correct answer is randomly distributed across A/B/C/D
    questions = _shuffle_mcq_options(questions)

    set_cached(cache_key, doc_id, json.dumps(questions))
    return jsonify({"questions": questions, "cached": False}), 200


def _shuffle_mcq_options(questions: list) -> list:
    """
    Randomize option positions across A/B/C/D so that the correct option is not
    always placed in the same position (e.g. D) by the LLM.
    """
    for q in questions:
        if isinstance(q, dict) and "options" in q and isinstance(q["options"], list) and len(q["options"]) > 1:
            options = q["options"]
            answer = str(q.get("answer", "")).strip()

            # Find the option index that currently matches 'answer'
            correct_idx = -1
            for idx, opt in enumerate(options):
                opt_str = str(opt).strip()
                if opt_str == answer:
                    correct_idx = idx
                    break
                # Check match after stripping letter prefix (A) , B) , etc.)
                clean_opt = re.sub(r'^[A-Ea-e][\.\)\:]\s*', '', opt_str).strip()
                clean_ans = re.sub(r'^[A-Ea-e][\.\)\:]\s*', '', answer).strip()
                if clean_opt and clean_opt == clean_ans:
                    correct_idx = idx
                    break

            if correct_idx != -1:
                # Strip prefixes from all options to get raw option strings
                raw_options = [re.sub(r'^[A-Ea-e][\.\)\:]\s*', '', str(o)).strip() for o in options]
                correct_raw = raw_options[correct_idx]

                # Don't shuffle if options contain positional phrases like "all of the above"
                has_special = any(
                    "all of the above" in o.lower()
                    or "none of the above" in o.lower()
                    or "both " in o.lower()
                    for o in raw_options
                )
                if not has_special:
                    random.shuffle(raw_options)

                # Reassign A) , B) , C) , D) prefixes
                letters = ["A) ", "B) ", "C) ", "D) ", "E) "]
                new_options = []
                new_answer = answer
                for idx, r_opt in enumerate(raw_options):
                    prefix = letters[idx] if idx < len(letters) else f"{idx+1}) "
                    new_options.append(prefix + r_opt)
                    if r_opt == correct_raw:
                        new_answer = prefix + r_opt

                q["options"] = new_options
                q["answer"] = new_answer
    return questions

