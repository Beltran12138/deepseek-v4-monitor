import os
import sys
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
os.environ["DB_PATH"] = ":memory:"
import db
db.init_db()
import discoverer


def _mock_response(items):
    m = MagicMock()
    m.json.return_value = items
    m.status_code = 200
    return m


def test_discover_no_spike():
    items = [
        {"slug": "will-deepseek-v5", "question": "Will DeepSeek V5 launch?",
         "outcomePrices": ["0.50"], "volume": "50000"},
        {"slug": "will-gpt5", "question": "Will GPT-5 launch?",
         "outcomePrices": ["0.60"], "volume": "80000"},
    ]
    state = {"market_prices": {"will-deepseek-v5": 0.50, "will-gpt5": 0.60}}
    with patch("discoverer.requests.get", return_value=_mock_response(items)), \
         patch("discoverer.db.upsert_market"):
        signals = discoverer.discover_markets(state)
    assert signals == []


def test_discover_price_spike():
    items = [
        {"slug": "will-deepseek-v5-spike", "question": "Will DeepSeek V5 release in 2025?",
         "outcomePrices": ["0.75"], "volume": "50000"},
    ]
    state = {"market_prices": {"will-deepseek-v5-spike": 0.30}}
    with patch("discoverer.requests.get", return_value=_mock_response(items)), \
         patch("discoverer.db.upsert_market"):
        signals = discoverer.discover_markets(state)
    assert len(signals) == 1
    assert signals[0]["source"] == "polymarket_price_spike"
    assert "0.30→0.75" in signals[0]["content"]


def test_discover_skips_low_volume():
    items = [
        {"slug": "will-claude5", "question": "Will Claude 5 launch?",
         "outcomePrices": ["0.80"], "volume": "500"},
    ]
    state = {"market_prices": {"will-claude5": 0.30}}
    with patch("discoverer.requests.get", return_value=_mock_response(items)), \
         patch("discoverer.db.upsert_market"):
        signals = discoverer.discover_markets(state)
    assert signals == []
