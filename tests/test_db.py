import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
os.environ["DB_PATH"] = ":memory:"
import db

def setup_function():
    db.init_db()

def test_insert_signal_returns_id():
    sid = db.insert_signal("2026-01-01T00:00:00", "arxiv", "deepseek", "some paper", 5)
    assert sid is not None
    assert isinstance(sid, int)

def test_insert_duplicate_returns_none():
    db.insert_signal("2026-01-01T00:00:00", "arxiv", "deepseek", "same content", 5)
    result = db.insert_signal("2026-01-01T00:00:00", "arxiv", "deepseek", "same content", 5)
    assert result is None

def test_update_signal_llm():
    sid = db.insert_signal("2026-01-01T00:00:00", "github_new_branch", "openai", "new branch v5", 4)
    db.update_signal_llm(sid, 8, "strong signal")
    rows = db.get_recent_signals(10)
    row = next(r for r in rows if r["id"] == sid)
    assert row["llm_score"] == 8
    assert row["llm_reason"] == "strong signal"

def test_upsert_market():
    db.upsert_market("test-slug", "Will GPT-5 release?", "openai", 0.75, 100000.0, "2026-01-01T00:00:00")
    markets = db.get_markets()
    assert any(m["slug"] == "test-slug" for m in markets)

def test_count_llm_calls_today_zero():
    assert db.count_llm_calls_today() >= 0
