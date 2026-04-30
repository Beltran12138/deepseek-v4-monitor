import hashlib
import os
import sqlite3
from pathlib import Path

DB_PATH = os.getenv("DB_PATH", str(Path(__file__).parent / "intelligence.db"))

_conn_cache: sqlite3.Connection | None = None

def get_conn() -> sqlite3.Connection:
    global _conn_cache
    if DB_PATH == ":memory:":
        if _conn_cache is None:
            _conn_cache = sqlite3.connect(DB_PATH, check_same_thread=False)
            _conn_cache.row_factory = sqlite3.Row
        return _conn_cache
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                source TEXT NOT NULL,
                target_model TEXT NOT NULL,
                content TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                rule_score INTEGER NOT NULL,
                llm_score INTEGER,
                llm_reason TEXT,
                notified BOOLEAN DEFAULT FALSE,
                UNIQUE(source, content_hash)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS markets (
                slug TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                model TEXT,
                current_price REAL,
                volume REAL,
                last_updated TEXT NOT NULL
            )
        """)

def hash_content(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()[:16]

def insert_signal(timestamp, source, target_model, content, rule_score):
    h = hash_content(content)
    try:
        with get_conn() as conn:
            cur = conn.execute(
                """INSERT INTO signals
                   (timestamp, source, target_model, content, content_hash, rule_score)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (timestamp, source, target_model, content, h, rule_score),
            )
            return cur.lastrowid
    except sqlite3.IntegrityError:
        return None

def update_signal_llm(signal_id: int, llm_score: int, llm_reason: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE signals SET llm_score=?, llm_reason=? WHERE id=?",
            (llm_score, llm_reason, signal_id),
        )

def mark_notified(signal_id: int):
    with get_conn() as conn:
        conn.execute("UPDATE signals SET notified=TRUE WHERE id=?", (signal_id,))

def get_recent_signals(limit=50):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM signals ORDER BY timestamp DESC LIMIT ?", (limit,)
        ).fetchall()

def upsert_market(slug, title, model, current_price, volume, last_updated):
    with get_conn() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO markets
               (slug, title, model, current_price, volume, last_updated)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (slug, title, model, current_price, volume, last_updated),
        )

def get_markets():
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM markets ORDER BY volume DESC"
        ).fetchall()

def count_llm_calls_today():
    with get_conn() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM signals "
            "WHERE llm_score IS NOT NULL AND date(timestamp)=date('now')"
        ).fetchone()[0]
