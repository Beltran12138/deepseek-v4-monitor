import os, sys
from datetime import datetime, timezone
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
os.environ["DB_PATH"] = ":memory:"
import db

def setup_function():
    db.init_db()

def test_insert_signal_returns_id():
    sid = db.insert_signal("2026-01-01T00:00:00", "arxiv", "deepseek", "paper_unique_a", 5)
    assert sid is not None
    assert isinstance(sid, int)

def test_insert_duplicate_returns_none():
    db.insert_signal("2026-01-01T00:00:00", "arxiv", "deepseek", "dup_content_xyz", 5)
    result = db.insert_signal("2026-01-01T00:00:00", "arxiv", "deepseek", "dup_content_xyz", 5)
    assert result is None

def test_update_signal_llm():
    sid = db.insert_signal("2026-01-01T00:00:00", "github_new_branch", "openai", "branch_v5_unique", 4)
    db.update_signal_llm(sid, 8, "strong signal")
    rows = db.get_recent_signals(10)
    row = next(r for r in rows if r["id"] == sid)
    assert row["llm_score"] == 8
    assert row["llm_reason"] == "strong signal"

def test_upsert_market_insert_and_replace():
    db.upsert_market("slug-upsert-test", "Will GPT-5 release?", "openai", 0.75, 100000.0, "2026-01-01T00:00:00")
    markets = db.get_markets()
    assert any(m["slug"] == "slug-upsert-test" for m in markets)
    # replace: update price
    db.upsert_market("slug-upsert-test", "Will GPT-5 release?", "openai", 0.90, 200000.0, "2026-01-02T00:00:00")
    markets = db.get_markets()
    updated = next(m for m in markets if m["slug"] == "slug-upsert-test")
    assert updated["current_price"] == 0.90
    assert updated["volume"] == 200000.0

def test_count_llm_calls_today():
    today = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    sid = db.insert_signal(today, "arxiv", "anthropic", "count_test_signal_utc", 5)
    db.update_signal_llm(sid, 9, "confirmed")
    count = db.count_llm_calls_today()
    assert count >= 1
