"""
app.py — Flask application factory for Saral.

Usage:
    python app.py                  (development)
    flask --app backend.app run    (flask CLI)
"""

import os
from flask import Flask, render_template, request

from backend.config import Config
from backend.database import init_db
from backend.extensions import limiter, cors


def create_app() -> Flask:
    """
    Application factory.  Creates and configures the Flask app,
    registers all blueprints, and initialises extensions.
    """
    # Resolve template and static folders relative to the project root
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    template_dir = os.path.join(project_root, "frontend", "templates")
    static_dir   = os.path.join(project_root, "frontend", "static")

    app = Flask(
        __name__,
        template_folder=template_dir,
        static_folder=static_dir,
        static_url_path="/static",
    )

    # ── Configuration ──────────────────────────────────────────────────
    app.config["SECRET_KEY"]         = Config.SECRET_KEY
    app.config["DEBUG"]              = Config.DEBUG
    app.config["MAX_CONTENT_LENGTH"] = Config.MAX_CONTENT_LENGTH

    # Validate credentials at startup (warns, does not crash)
    Config.validate()

    # ── Extensions ─────────────────────────────────────────────────────
    limiter.init_app(app)
    cors.init_app(app, resources={r"/api/*": {"origins": "*"}})

    # ── Database ────────────────────────────────────────────────────────
    init_db()

    # ── Create required runtime directories ────────────────────────────
    os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(Config.CHROMA_PATH,   exist_ok=True)

    # ── Register blueprints ────────────────────────────────────────────
    from backend.routes.document_routes import documents_bp
    from backend.routes.chat_routes     import chat_bp
    from backend.routes.simplify_routes import simplify_bp
    from backend.routes.summary_routes  import summary_bp
    from backend.routes.quiz_routes     import quiz_bp
    from backend.routes.explain_routes  import explain_bp
    from backend.routes.revision_routes import revision_bp
    from backend.routes.settings_routes import settings_bp

    app.register_blueprint(documents_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(simplify_bp)
    app.register_blueprint(summary_bp)
    app.register_blueprint(quiz_bp)
    app.register_blueprint(explain_bp)
    app.register_blueprint(revision_bp)
    app.register_blueprint(settings_bp)

    # ── Frontend page routes ───────────────────────────────────────────
    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/chat")
    def chat():
        return render_template("chat.html")

    @app.route("/simplify")
    def simplify():
        return render_template("simplify.html")

    @app.route("/summary")
    def summary():
        return render_template("summary.html")

    @app.route("/quiz")
    def quiz():
        return render_template("quiz.html")

    @app.route("/explain")
    def explain():
        return render_template("explain.html")

    @app.route("/revision")
    def revision():
        return render_template("revision.html")

    @app.route("/settings")
    def settings():
        return render_template("settings.html")

    # ── Global error handlers ──────────────────────────────────────────
    @app.errorhandler(413)
    def file_too_large(e):
        return {"error": "File exceeds the 10 MB upload limit."}, 413

    @app.errorhandler(429)
    def rate_limited(e):
        return {
            "error": (
                "The AI service has temporarily reached its free usage limit. "
                "Please try again later."
            )
        }, 429

    @app.errorhandler(404)
    def not_found(e):
        # Return JSON for API calls, HTML for browser navigation
        if request.path.startswith("/api/"):
            return {"error": "Resource not found."}, 404
        return render_template("404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        if request.path.startswith("/api/"):
            return {"error": "An unexpected server error occurred."}, 500
        return render_template("500.html"), 500

    return app


# ── Dev entry-point ────────────────────────────────────────────────────
if __name__ == "__main__":
    app = create_app()
    app.run(host="127.0.0.1", port=5000, debug=Config.DEBUG)
