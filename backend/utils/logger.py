"""
utils/logger.py — Structured application logger for Saral.

A single logger factory used across all modules.
- Never logs API keys, file contents, or user data beyond metadata.
- Log level is controlled by FLASK_DEBUG in .env.
- Format is consistent and grep-friendly.
"""

import logging
import sys
import io
from backend.config import Config

# Ensure stdout/stderr handle Unicode safely on Windows consoles
for stream_name in ("stdout", "stderr"):
    stream = getattr(sys, stream_name, None)
    if stream and hasattr(stream, "reconfigure"):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


class SafeStreamHandler(logging.StreamHandler):
    """A StreamHandler that safely handles UnicodeEncodeError on Windows."""
    def emit(self, record):
        try:
            super().emit(record)
        except UnicodeEncodeError:
            try:
                msg = self.format(record)
                stream = self.stream
                stream.write(msg.encode(stream.encoding or "utf-8", errors="replace").decode(stream.encoding or "utf-8", errors="replace") + self.terminator)
                self.flush()
            except Exception:
                self.handleError(record)
        except Exception:
            self.handleError(record)


def get_logger(name: str) -> logging.Logger:
    """
    Return a named logger with consistent formatting.

    Usage:
        from backend.utils.logger import get_logger
        log = get_logger(__name__)
        log.info("Document %d indexed: %d chunks", doc_id, chunk_count)
    """
    logger = logging.getLogger(name)

    # Avoid adding duplicate handlers on repeated calls
    if logger.handlers:
        return logger

    level = logging.DEBUG if Config.DEBUG else logging.INFO
    logger.setLevel(level)

    handler = SafeStreamHandler(sys.stdout)
    handler.setLevel(level)

    fmt = logging.Formatter(
        fmt="%(asctime)s [%(levelname)-5s] %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(fmt)
    logger.addHandler(handler)

    # Prevent propagation to the root logger (avoids duplicate output)
    logger.propagate = False

    return logger
