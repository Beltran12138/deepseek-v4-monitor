#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

if sys.platform == "win32":
    os.system("chcp 65001 > nul 2>&1")
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import db
import scorer
import sources
import discoverer
import notifier

CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "300"))
STATE_FILE = Path(__file__).parent / "state.json"

_SOURCE_FNS = [
    sources.check_github,
    sources.check_huggingface,
    sources.check_reddit,
    sources.check_twitter,
    sources.check_arxiv,
    discoverer.discover_markets,
]


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"first_run": True}


def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def _run_cycle(state: dict) -> int:
    db.init_db()
    llm_calls = db.count_llm_calls_today()
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

    all_signals: list[dict] = []
    for fn in _SOURCE_FNS:
        try:
            all_signals.extend(fn(state))
        except Exception as e:
            print(f"[monitor] {fn.__name__} error: {e}", file=sys.stderr)

    for sig in all_signals:
        scored = scorer.score_signal(sig["source"], sig["content"], llm_calls)
        if scored["llm_score"] is not None:
            llm_calls += 1

        sid = db.insert_signal(
            ts,
            sig["source"],
            sig["target_model"],
            sig["content"],
            scored["rule_score"],
        )
        if sid is None:
            continue  # duplicate

        if scored["llm_score"] is not None:
            db.update_signal_llm(sid, scored["llm_score"], scored["llm_reason"])

        level = scored["level"]
        if level in ("red", "yellow"):
            sent = notifier.notify(
                sid, level, sig["source"], sig["target_model"], sig["content"],
                scored["rule_score"], scored["llm_score"], scored["llm_reason"],
            )
            if sent:
                db.mark_notified(sid)

        try:
            from dashboard.app import broadcast
            broadcast({
                "type": "signal",
                "id": sid,
                "level": level,
                "source": sig["source"],
                "target_model": sig["target_model"],
                "content": sig["content"],
                "rule_score": scored["rule_score"],
                "llm_score": scored["llm_score"],
                "timestamp": ts,
            })
        except Exception:
            pass

    if state.get("first_run"):
        state["first_run"] = False

    return len(all_signals)


def main():
    print(f"AI Intelligence Monitor — interval={CHECK_INTERVAL}s | Ctrl-C to stop")
    state = load_state()
    round_num = 0
    while True:
        round_num += 1
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n[{ts}] Round {round_num}")
        n = _run_cycle(state)
        save_state(state)
        print(f"  {n} signals processed")
        time.sleep(CHECK_INTERVAL)


def run_once():
    """Single-shot mode for GitHub Actions / cron."""
    state = load_state()
    n = _run_cycle(state)
    save_state(state)
    print(f"run_once: {n} signals processed")


if __name__ == "__main__":
    if "--once" in sys.argv:
        run_once()
    else:
        try:
            main()
        except KeyboardInterrupt:
            print("\nStopped.")
