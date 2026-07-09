"""
extensions.py — Flask extension instances.

Initialised here without an app object (application factory pattern).
Bound to the app in app.py via init_app().
"""

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_cors import CORS

# Rate limiter — storage is in-memory (suitable for single-user local deployment)
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri="memory://",
    default_limits=[],  # per-route limits are applied explicitly
)

cors = CORS()
