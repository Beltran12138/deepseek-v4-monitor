import os
import requests
from dotenv import load_dotenv

load_dotenv()

SIGNAL_WEIGHTS = {
    "arxiv":                 5,
    "github_new_branch":     4,
    "huggingface_new_model": 4,
    "polymarket_price_spike":3,
    "reddit_hot":            2,
    "twitter":               1,
}

TARGETS = {
    "deepseek":  ["v5", "V5", "deepseek-v5", "v4.5", "next-gen"],
    "openai":    ["gpt-5", "gpt5", "o4", "o5"],
    "anthropic": ["claude-5", "claude5", "claude-next"],
    "google":    ["gemini-3", "gemini3"],
}

MAX_LLM_CALLS_PER_DAY = int(os.getenv("MAX_LLM_CALLS_PER_DAY", "20"))
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")

def detect_target(text: str):
    text_lower = text.lower()
    for model, keywords in TARGETS.items():
        if any(kw.lower() in text_lower for kw in keywords):
            return model
    return None

def rule_score(source: str) -> int:
    return SIGNAL_WEIGHTS.get(source, 0)

def _llm_evaluate(content: str):
    """Returns (score int 0-10, reason str) or (None, reason) on failure."""
    if not DEEPSEEK_API_KEY:
        return None, "no API key"
    try:
        resp = requests.post(
            "https://api.deepseek.com/chat/completions",
            headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}"},
            json={
                "model": "deepseek-chat",
                "messages": [{
                    "role": "user",
                    "content": (
                        "Rate this AI release signal's relevance to a next-generation model "
                        "launch (0=noise, 10=strong signal). Reply with exactly:\n"
                        "SCORE: <int>\nREASON: <one sentence>\n\n"
                        f"Signal: {content[:500]}"
                    ),
                }],
                "max_tokens": 80,
            },
            timeout=15,
        )
        resp.raise_for_status()
        text = resp.json()["choices"][0]["message"]["content"]
        lines = text.splitlines()
        score_line = next((l for l in lines if l.startswith("SCORE:")), None)
        reason_line = next((l for l in lines if l.startswith("REASON:")), None)
        if score_line is None or reason_line is None:
            return None, "LLM format error"
        score = int(score_line.split(":")[1].strip())
        reason = reason_line.split(":", 1)[1].strip()
        return min(max(score, 0), 10), reason
    except Exception:
        return None, "LLM error"

def score_signal(source: str, content: str, llm_calls_today: int) -> dict:
    rs = rule_score(source)
    llm_score = None
    llm_reason = None

    if rs >= 7 and llm_calls_today < MAX_LLM_CALLS_PER_DAY:
        llm_score, llm_reason = _llm_evaluate(content)
        if llm_score is None:
            level = "yellow"  # LLM failed; fall back to rule confidence
        else:
            level = "red" if llm_score >= 7 else "yellow"
    elif rs >= 4:
        level = "yellow"
    else:
        level = "gray"

    return {
        "rule_score": rs,
        "llm_score": llm_score,
        "llm_reason": llm_reason,
        "level": level,
    }
