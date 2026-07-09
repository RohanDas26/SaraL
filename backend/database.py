"""
database.py — SQLite connection and schema initialisation.

Uses Python's built-in sqlite3 module.  No ORM.
Call init_db() once at application startup.
"""

import sqlite3
import os
from backend.config import Config
from backend.utils.logger import get_logger

log = get_logger(__name__)


def get_db() -> sqlite3.Connection:
    """
    Return a new SQLite connection with row_factory set so rows behave
    like dictionaries (access columns by name).
    """
    os.makedirs(Config.INSTANCE_FOLDER, exist_ok=True)
    conn = sqlite3.connect(Config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")   # better concurrent read performance
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    """
    Create all tables if they do not already exist.
    Safe to call multiple times (idempotent).
    Runs ALTER TABLE to add new columns to existing databases (migration).
    """
    conn = get_db()
    cursor = conn.cursor()

    # ── documents ─────────────────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            filename      TEXT    NOT NULL,          -- UUID-based safe filename on disk
            display_name  TEXT    NOT NULL,          -- original user-facing filename
            file_path     TEXT    NOT NULL,          -- absolute path on disk
            file_type     TEXT    NOT NULL,          -- pdf | docx | txt
            file_size_kb  INTEGER NOT NULL,
            file_hash     TEXT    UNIQUE,            -- SHA-256 of file contents (dedup)
            page_count    INTEGER,
            chunk_count   INTEGER DEFAULT 0,
            status        TEXT    NOT NULL DEFAULT 'pending',
            progress_pct  INTEGER DEFAULT 0,         -- 0-100 for progress polling
            error_message TEXT,
            created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at    DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Migration: add new columns to existing databases.
    # NOTE: SQLite does not allow ADD COLUMN with UNIQUE — the UNIQUE
    # constraint on file_hash is only enforced on new databases (CREATE TABLE).
    # Existing databases get the column without the constraint, which is
    # acceptable for a single-user local app.
    _add_column_if_missing(cursor, "documents", "file_hash",    "TEXT")
    _add_column_if_missing(cursor, "documents", "progress_pct", "INTEGER DEFAULT 0")

    # ── chat_messages ──────────────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_messages (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id  TEXT    NOT NULL,
            doc_id      INTEGER REFERENCES documents(id) ON DELETE SET NULL,
            role        TEXT    NOT NULL CHECK(role IN ('user', 'assistant')),
            content     TEXT    NOT NULL,
            sources     TEXT,
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── settings ───────────────────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)

    # Insert defaults only if not yet present (INSERT OR IGNORE)
    defaults = [
        ("learning_level", "intermediate"),
        ("response_length", "medium"),
        ("temperature", "0.7"),
        ("theme", "light"),
    ]
    cursor.executemany(
        "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
        defaults,
    )

    conn.commit()
    conn.close()
    log.info("Database initialised at %s", Config.DB_PATH)


def _add_column_if_missing(cursor: sqlite3.Cursor, table: str, column: str, definition: str) -> None:
    """
    Add a column to an existing table if it does not already exist.
    Used for lightweight schema migrations without dropping data.
    """
    cursor.execute(f"PRAGMA table_info({table})")
    existing_columns = {row[1] for row in cursor.fetchall()}
    if column not in existing_columns:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        log.info("Migration: added column '%s' to table '%s'", column, table)
