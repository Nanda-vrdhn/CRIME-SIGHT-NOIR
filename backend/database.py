"""Connection factory, schema creation and first-run seeding.

The schema (``sql/schema.sql``) and the seed data (``sql/seed.sql``) are the
single source of truth for the database; this module only executes them.

Paths are resolved relative to the repository root, so the server can be
started from any working directory.
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

# Repository root = parent of the ``backend`` package.
ROOT = Path(__file__).resolve().parent.parent
SQL_DIR = ROOT / "sql"
FRONTEND_FILE = ROOT / "frontend" / "index.html"

#: Override with the CSN_DB_PATH environment variable (useful for tests).
DB_PATH = Path(os.environ.get("CSN_DB_PATH") or (ROOT / "backend" / "crimesight.db"))

# Columns added to ``users`` after the first release. Kept for databases that
# were created by an older version of this project.
_USER_COLUMNS = (
    ("badge", "TEXT"),
    ("rank", "TEXT"),
    ("station_name", "TEXT"),
    ("district", "TEXT"),
    ("state", "TEXT"),
    ("squad", "TEXT"),
    ("official_id", "TEXT"),
    ("designation", "TEXT"),
    ("department", "TEXT"),
    ("zone", "TEXT"),
)


def dict_factory(cursor, row):
    """Convert a sqlite3 row into a plain dict so jsonify() can serialise it."""
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


def get_db():
    """Open a connection that returns dicts instead of tuples.

    The caller owns the connection and must close it (``try/finally``).
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = dict_factory
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _read_sql(name: str) -> str:
    path = SQL_DIR / name
    if not path.is_file():
        raise FileNotFoundError(
            f"Missing SQL file: {path}. Run the server from a full checkout "
            "of the repository."
        )
    return path.read_text(encoding="utf-8")


def _migrate_users(conn) -> None:
    """Add any missing profile columns to a legacy ``users`` table."""
    table = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
    ).fetchone()
    if not table:
        return
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(users)")}
    for col, typedef in _USER_COLUMNS:
        if col not in existing:
            # Column names come from the _USER_COLUMNS allow-list above, never
            # from user input, so this interpolation is safe.
            conn.execute(f"ALTER TABLE users ADD COLUMN {col} {typedef}")


def init_db() -> Path:
    """Create the schema and, on a brand new database, load the seed data.

    Safe to call more than once: ``schema.sql`` uses ``IF NOT EXISTS`` and the
    seed script uses ``INSERT OR IGNORE``.
    """
    conn = get_db()
    try:
        conn.executescript(_read_sql("schema.sql"))
        conn.commit()

        row = conn.execute("SELECT COUNT(*) AS c FROM police_stations").fetchone()
        if row["c"] == 0:
            conn.executescript(_read_sql("seed.sql"))
            conn.commit()
            print(
                f"[*] Seeded {DB_PATH.name}: 25 stations, 20 officers, "
                "11 criminals, 75 FIR cases, 3 demo users."
            )

        _migrate_users(conn)
        conn.commit()
    finally:
        conn.close()
    return DB_PATH


def table_counts() -> dict:
    """Row counts per table — handy for smoke tests and /api/stats."""
    conn = get_db()
    try:
        out = {}
        for name in ("police_stations", "officers", "criminals", "cases", "users"):
            out[name] = conn.execute(f"SELECT COUNT(*) AS c FROM {name}").fetchone()["c"]
        return out
    finally:
        conn.close()
