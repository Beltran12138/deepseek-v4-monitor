import os
import requests
from dotenv import load_dotenv

load_dotenv()

_TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
_TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

_LEVEL_PREFIX = {
    "red":    "🔴 RED ALERT",
    "yellow": "🟡 SIGNAL",
    "gray":   "⚪ INFO",
}


def notify(signal_id: int, level: str, source: str, target_model: str, content: str,
           rule_score: int, llm_score: int | None, llm_reason: str | None) -> bool:
    """Send Telegram notification for a signal. Returns True if sent successfully."""
    prefix = _LEVEL_PREFIX.get(level, "⚪ INFO")
    score_str = f"rule={rule_score}"
    if llm_score is not None:
        score_str += f" llm={llm_score}"
        if llm_reason:
            score_str += f" ({llm_reason})"

    text = (
        f"{prefix}\n"
        f"Model: {target_model} | Source: {source}\n"
        f"Scores: {score_str}\n"
        f"{content}"
    )
    return _send_telegram(text)


def _send_telegram(text: str) -> bool:
    if not _TELEGRAM_TOKEN or not _TELEGRAM_CHAT_ID:
        return False
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{_TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": _TELEGRAM_CHAT_ID, "text": text},
            timeout=10,
        )
        return r.status_code == 200
    except Exception:
        return False
