"""
routes/settings_routes.py — App settings + cache management.
"""

from flask import Blueprint, request, jsonify
from backend.database import get_db
from backend.services.cache_service import clear_cache, cache_size

settings_bp = Blueprint("settings", __name__, url_prefix="/api")

ALLOWED_KEYS = {"learning_level", "response_length", "temperature", "theme"}
ENUM_VALUES  = {
    "learning_level":  {"beginner", "intermediate", "advanced"},
    "response_length": {"short", "medium", "long"},
    "theme":           {"light", "dark"},
}


@settings_bp.route("/settings", methods=["GET"])
def get_settings():
    conn = get_db()
    try:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
        return jsonify({r["key"]: r["value"] for r in rows}), 200
    finally:
        conn.close()


@settings_bp.route("/settings", methods=["POST"])
def update_settings():
    data = request.get_json(silent=True) or {}
    if not data:
        return jsonify({"error": "No settings provided."}), 400

    conn = get_db()
    try:
        for key, value in data.items():
            if key not in ALLOWED_KEYS:
                continue
            if key in ENUM_VALUES and value not in ENUM_VALUES[key]:
                continue
            conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                (key, str(value)),
            )
        conn.commit()
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
        return jsonify({r["key"]: r["value"] for r in rows}), 200
    finally:
        conn.close()


@settings_bp.route("/cache/clear", methods=["POST"])
def clear_response_cache():
    """Clear the in-memory response cache."""
    clear_cache()
    return jsonify({"message": "Response cache cleared.", "size": 0}), 200


@settings_bp.route("/cache/size", methods=["GET"])
def get_cache_size():
    return jsonify({"size": cache_size()}), 200
