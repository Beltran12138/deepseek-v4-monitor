import os
import sys
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import notifier


def test_notify_red_sends_telegram():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    with patch("notifier.requests.post", return_value=mock_resp), \
         patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "tok", "TELEGRAM_CHAT_ID": "123"}):
        notifier._TELEGRAM_TOKEN = "tok"
        notifier._TELEGRAM_CHAT_ID = "123"
        result = notifier.notify(1, "red", "arxiv", "deepseek", "paper content", 5, 9, "strong")
    assert result is True


def test_notify_no_token_returns_false():
    notifier._TELEGRAM_TOKEN = ""
    notifier._TELEGRAM_CHAT_ID = ""
    result = notifier.notify(2, "yellow", "github_new_branch", "openai", "branch v5", 4, None, None)
    assert result is False


def test_notify_includes_llm_reason():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    captured = {}

    def fake_post(url, json=None, timeout=None):
        captured["text"] = json["text"]
        return mock_resp

    notifier._TELEGRAM_TOKEN = "tok"
    notifier._TELEGRAM_CHAT_ID = "123"
    with patch("notifier.requests.post", side_effect=fake_post):
        notifier.notify(3, "red", "arxiv", "deepseek", "v5 paper", 5, 8, "Confirmed V5 signal")
    assert "Confirmed V5 signal" in captured["text"]
    assert "🔴" in captured["text"]
