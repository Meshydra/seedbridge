"""SQLite storage. One connection per call keeps it safe for the background AI threads."""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from .config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY,
  email TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('founder','sponsor')),
  org TEXT,
  password_hash TEXT NOT NULL,
  avatar_path TEXT, bio TEXT, website TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ideas (
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id),
  title TEXT NOT NULL,
  one_liner TEXT, problem TEXT, solution TEXT, sector TEXT, stage TEXT, country TEXT,
  ask_usd INTEGER, business_model TEXT, team TEXT, traction TEXT, use_of_funds TEXT,
  product_status TEXT, deck_path TEXT, research_json TEXT,
  share INTEGER NOT NULL DEFAULT 1,
  status TEXT NOT NULL DEFAULT 'pending',
  profile_json TEXT, gaps_json TEXT, deck_json TEXT, review_json TEXT, embedding_json TEXT,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS programs (
  id INTEGER PRIMARY KEY,
  sponsor_id INTEGER NOT NULL REFERENCES users(id),
  name TEXT NOT NULL, kind TEXT NOT NULL, description TEXT, criteria TEXT,
  min_usd INTEGER, max_usd INTEGER,
  sectors TEXT, stages TEXT, countries TEXT, deadline TEXT,
  embedding_json TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS matches (
  id INTEGER PRIMARY KEY,
  idea_id INTEGER NOT NULL REFERENCES ideas(id) ON DELETE CASCADE,
  program_id INTEGER NOT NULL REFERENCES programs(id) ON DELETE CASCADE,
  similarity REAL, fit_score INTEGER, reason TEXT, concerns TEXT,
  created_at TEXT NOT NULL,
  UNIQUE (idea_id, program_id)
);
CREATE TABLE IF NOT EXISTS ai_steps (
  id INTEGER PRIMARY KEY,
  idea_id INTEGER REFERENCES ideas(id) ON DELETE CASCADE,
  application_id INTEGER,
  step TEXT NOT NULL, model TEXT NOT NULL, status TEXT NOT NULL,
  latency_ms INTEGER, input_tokens INTEGER, output_tokens INTEGER, cost_usd REAL,
  demo INTEGER NOT NULL DEFAULT 0, error TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS kb_chunks (
  id INTEGER PRIMARY KEY,
  source TEXT NOT NULL, title TEXT NOT NULL, text TEXT NOT NULL,
  embedding_json TEXT
);
CREATE TABLE IF NOT EXISTS applications (
  id INTEGER PRIMARY KEY,
  idea_id INTEGER NOT NULL REFERENCES ideas(id) ON DELETE CASCADE,
  program_id INTEGER NOT NULL REFERENCES programs(id) ON DELETE CASCADE,
  draft TEXT,
  status TEXT NOT NULL DEFAULT 'drafting',
  sponsor_note TEXT,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  UNIQUE (idea_id, program_id)
);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def connect():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


# Columns added after the first release; added in place so existing databases keep working.
MIGRATIONS = {
    "users": ["avatar_path TEXT", "bio TEXT", "website TEXT"],
    "ideas": ["product_status TEXT", "research_json TEXT"],
}


def init():
    with connect() as c:
        c.execute("PRAGMA journal_mode = WAL")
        c.executescript(SCHEMA)
        for table, cols in MIGRATIONS.items():
            have = {r["name"] for r in c.execute(f"PRAGMA table_info({table})")}
            for col in cols:
                if col.split()[0] not in have:
                    c.execute(f"ALTER TABLE {table} ADD COLUMN {col}")


def one(sql, *args):
    with connect() as c:
        row = c.execute(sql, args).fetchone()
        return dict(row) if row else None


def all_(sql, *args):
    with connect() as c:
        return [dict(r) for r in c.execute(sql, args).fetchall()]


def run(sql, *args) -> int:
    with connect() as c:
        cur = c.execute(sql, args)
        return cur.lastrowid


def loads(value, default=None):
    if not value:
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default
