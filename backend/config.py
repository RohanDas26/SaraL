"""
config.py — Centralised configuration for Saral.

All settings are read from environment variables (loaded from .env by
python-dotenv).  Changing a model, endpoint, or limit requires only a
change to .env — no code edits needed.
"""

import os
from dotenv import load_dotenv, find_dotenv

# Load .env from the project root.
# find_dotenv() walks up from this file's location, so it always finds the
# .env regardless of which directory the process is launched from.
_env_path = find_dotenv(filename=".env", raise_error_if_not_found=False)
# override=True ensures .env values take precedence over any stale
# system-level environment variables.
load_dotenv(_env_path, override=True)


class Config:
    # ── Flask ──────────────────────────────────────────────────────────
    SECRET_KEY: str = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-in-production")
    DEBUG: bool = os.environ.get("FLASK_DEBUG", "false").lower() == "true"

    # ── File upload ────────────────────────────────────────────────────
    # MAX_UPLOAD_SIZE_MB is the canonical env var (MB is human-readable).
    # MAX_UPLOAD_BYTES is kept as a fallback for backward compatibility.
    _upload_mb: int = int(os.environ.get("MAX_UPLOAD_SIZE_MB", os.environ.get("MAX_UPLOAD_BYTES_FALLBACK", "25")))
    MAX_CONTENT_LENGTH: int = _upload_mb * 1024 * 1024
    ALLOWED_EXTENSIONS: set = {"pdf", "docx", "txt"}
    # Store uploads in project_root/uploads/ — outside the static directory
    UPLOAD_FOLDER: str = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")

    # ── Database ───────────────────────────────────────────────────────
    INSTANCE_FOLDER: str = os.path.join(os.path.dirname(os.path.dirname(__file__)), "instance")
    DB_PATH: str = os.path.join(INSTANCE_FOLDER, "saral.db")

    # ── ChromaDB ───────────────────────────────────────────────────────
    CHROMA_PATH: str = os.path.join(os.path.dirname(os.path.dirname(__file__)), "vectordb")

    # ── IBM watsonx.ai ────────────────────────────────────────────────
    WATSONX_API_KEY: str = os.environ.get("WATSONX_API_KEY", "")
    WATSONX_PROJECT_ID: str = os.environ.get("WATSONX_PROJECT_ID", "")
    WATSONX_URL: str = os.environ.get("WATSONX_URL", "https://au-syd.ml.cloud.ibm.com")
    WATSONX_MODEL_ID: str = os.environ.get("WATSONX_MODEL_ID", "meta-llama/llama-3-3-70b-instruct")

    # ── LLM generation defaults ────────────────────────────────────────
    LLM_MAX_NEW_TOKENS: int = 800
    LLM_TEMPERATURE: float = 0.7
    LLM_TOP_P: float = 0.9
    LLM_REPETITION_PENALTY: float = 1.1

    # ── RAG settings ───────────────────────────────────────────────────
    RAG_TOP_K: int = 3                     # retrieve top 3 chunks
    CHUNK_SIZE: int = 512                  # characters per chunk (≈ 128 tokens)
    CHUNK_OVERLAP: int = 64               # character overlap between chunks

    # ── Rate limiting ──────────────────────────────────────────────────
    RATE_LIMIT_PER_MINUTE: str = os.environ.get("RATE_LIMIT_PER_MINUTE", "5")
    RATE_LIMIT_PER_DAY: str = os.environ.get("RATE_LIMIT_PER_DAY", "50")

    @classmethod
    def validate(cls) -> None:
        """
        Called at startup.  Warns (does not crash) if IBM credentials are missing
        so the app can still serve the UI while the user configures .env.
        """
        if not cls.WATSONX_API_KEY:
            print("[WARN] WATSONX_API_KEY is not set.  AI features will not work.")
        if not cls.WATSONX_PROJECT_ID:
            print("[WARN] WATSONX_PROJECT_ID is not set.  AI features will not work.")
