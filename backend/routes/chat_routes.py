"""
routes/chat_routes.py — Conversational Q&A (Ask Saral).
"""

import json
from flask import Blueprint, request, jsonify

from backend.extensions import limiter
from backend.config import Config
from backend.database import get_db
from backend.services.rag_service import retrieve_context, has_indexed_documents
from backend.services.llm_service import get_llm
from backend.services.cache_service import get_cached, set_cached
from backend.utils.prompt_utils import build_rag_prompt
from backend.utils.logger import get_logger

log = get_logger(__name__)

chat_bp = Blueprint("chat", __name__, url_prefix="/api/chat")
_RATE = f"{Config.RATE_LIMIT_PER_MINUTE} per minute;{Config.RATE_LIMIT_PER_DAY} per day"


def _get_recent_history(session_id: str, limit: int = 6) -> list[dict]:
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT role, content FROM chat_messages WHERE session_id=? ORDER BY created_at DESC LIMIT ?",
            (session_id, limit),
        ).fetchall()
        return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]
    except Exception as e:
        log.warning("Could not fetch recent chat history: %s", e)
        return []
    finally:
        conn.close()


def _resolve_search_query(question: str, history: list[dict]) -> str:
    if not history:
        return question

    followup_keywords = (
        "detail",
        "marks",
        "more",
        "why",
        "how",
        "what about",
        "example",
        "elaborate",
        "first point",
        "second point",
        "summarize",
        "explain",
        "continue",
    )
    word_count = len(question.split())
    is_followup = word_count <= 8 or any(
        k in question.lower() for k in followup_keywords
    )

    if is_followup:
        last_user_msg = next(
            (
                m["content"]
                for m in reversed(history)
                if m["role"] == "user" and len(m["content"].split()) > 2
            ),
            "",
        )
        if last_user_msg and last_user_msg != question:
            return f"{last_user_msg} — {question}"

    return question


@chat_bp.route("/ask", methods=["POST"])
@limiter.limit(_RATE)
def ask():
    data           = request.get_json(silent=True) or {}
    question       = (data.get("question") or "").strip()
    doc_ids        = data.get("doc_ids") or []
    session_id     = data.get("session_id", "default")
    learning_level = data.get("learning_level", "intermediate")

    if not question:
        return jsonify({"error": "Question cannot be empty."}), 400

    history = _get_recent_history(session_id, limit=6)
    search_query = _resolve_search_query(question, history)
    no_cache = bool(data.get("no_cache", False))

    scope = str(sorted(doc_ids)) if doc_ids else "all"
    if not no_cache:
        cached = get_cached(search_query, scope)
        if cached:
            _save_messages(session_id, doc_ids, question, cached, [])
            return jsonify({"answer": cached, "sources": [], "cached": True}), 200

    if not has_indexed_documents():
        return jsonify({
            "answer": "I couldn't find this information in your uploaded study material. "
                      "Please upload a relevant document and try again.",
            "sources": [],
        }), 200

    context, sources = retrieve_context(search_query, doc_ids or None)

    if not context:
        return jsonify({
            "answer": "I couldn't find this information in your uploaded study material. "
                      "Please upload a relevant document and try again.",
            "sources": [],
        }), 200

    prompt = build_rag_prompt(context, question, learning_level, history=history)
    try:
        answer = get_llm().generate(prompt)
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 503

    set_cached(search_query, scope, answer)
    _save_messages(session_id, doc_ids, question, answer, sources)

    return jsonify({"answer": answer, "sources": sources, "cached": False}), 200


@chat_bp.route("/history/<session_id>", methods=["GET"])
def get_history(session_id: str):
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT id, role, content, sources, created_at FROM chat_messages "
            "WHERE session_id=? ORDER BY created_at ASC",
            (session_id,),
        ).fetchall()
        messages = [
            {
                "id":         r["id"],
                "role":       r["role"],
                "content":    r["content"],
                "sources":    json.loads(r["sources"]) if r["sources"] else [],
                "created_at": r["created_at"],
            }
            for r in rows
        ]
        return jsonify({"messages": messages}), 200
    finally:
        conn.close()


@chat_bp.route("/history/<session_id>", methods=["DELETE"])
def clear_history(session_id: str):
    conn = get_db()
    try:
        conn.execute("DELETE FROM chat_messages WHERE session_id=?", (session_id,))
        conn.commit()
        return jsonify({"message": "Chat history cleared."}), 200
    finally:
        conn.close()


def _save_messages(session_id, doc_ids, question, answer, sources):
    conn = get_db()
    try:
        doc_id = doc_ids[0] if doc_ids else None
        conn.execute(
            "INSERT INTO chat_messages (session_id, doc_id, role, content, sources) VALUES (?,?,?,?,?)",
            (session_id, doc_id, "user", question, None),
        )
        conn.execute(
            "INSERT INTO chat_messages (session_id, doc_id, role, content, sources) VALUES (?,?,?,?,?)",
            (session_id, doc_id, "assistant", answer, json.dumps(sources)),
        )
        conn.commit()
    finally:
        conn.close()
