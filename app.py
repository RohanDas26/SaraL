"""
app.py — Entry point for Saral.

Local development:  python app.py
Production (WSGI):  gunicorn --bind 0.0.0.0:$PORT app:application
"""
import sys, os, warnings, logging

# Silence noisy telemetry and deprecation warnings before any imports
logging.getLogger("chromadb.telemetry").setLevel(logging.ERROR)
warnings.filterwarnings("ignore", category=UserWarning, module="huggingface_hub")
warnings.filterwarnings("ignore", category=FutureWarning, module="transformers")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.app import create_app

# Module-level 'application' so gunicorn (Procfile: app:application) can import it.
# Also used by the __main__ block below for local development.
application = create_app()

if __name__ == "__main__":
    # use_reloader=False prevents a second process from spawning and
    # re-downloading the embedding model on every file-change restart.
    application.run(host="127.0.0.1", port=5000, debug=True, use_reloader=False)
