# AI Release Radar 🔭

> Real-time intelligence dashboard for next-generation AI model launches — tracking DeepSeek V5, GPT-5, Claude 5, and Gemini 3 across prediction markets, GitHub, arXiv, HuggingFace, Reddit, and Twitter.

<!-- Replace with your actual demo GIF: record dashboard + a signal appearing -->
![Demo](docs/demo.gif)

## What it does

When a lab is about to drop a major model, signals appear *before* the announcement:
- New branches in infrastructure repos (`DeepGEMM`, `FlashMLA`, `3FS`…)
- Unusual price movement in Polymarket prediction markets
- arXiv papers with "V5" / "GPT-5" in the title
- Spikes in r/LocalLLaMA discussion
- Tweets from key researchers

**AI Release Radar** aggregates all of these, scores them with a hybrid rule engine + DeepSeek LLM, and surfaces high-confidence signals in a live dashboard.

## Architecture

```
Sources (5 platforms)          Scorer              Storage & Output
─────────────────────          ──────              ────────────────
GitHub (branches/commits) ─┐
HuggingFace (models/data) ─┤
Reddit r/LocalLLaMA       ─┼─► rule_score()  ─┬─► SQLite DB
Twitter via RSSHub        ─┤   + LLM score()  ├─► Telegram alert
arXiv papers              ─┘   (DeepSeek API) ├─► Flask SSE dashboard
                                               └─► state.json (dedup)
Polymarket Gamma API ──────────────────────────► price spike signals
```

## Dashboard

3-panel live view — signals stream in via Server-Sent Events (no polling):

| Panel | Content |
|-------|---------|
| **Live Signals** | Color-coded 🔴 red / 🟡 yellow / ⚪ gray by confidence |
| **Polymarket** | Auto-discovered markets with price bars |
| **Breakdown** | Signal counts by model and level |

## Signal Scoring

Each signal gets a **rule score** (source weight) + optional **LLM score** (0–10):

| Source | Rule Score | LLM triggered when |
|--------|-----------|-------------------|
| arXiv paper | 5 | score ≥ 7 |
| GitHub new branch | 4 | score ≥ 7 |
| GitHub new commit | 4 | score ≥ 7 |
| HuggingFace new model | 4 | score ≥ 7 |
| Polymarket price spike | 3 | — |
| Reddit post | 2 | — |
| Twitter | 1 | — |

Final level: `red` (LLM ≥ 7) · `yellow` (rule ≥ 4 or LLM < 7) · `gray` (rule < 4)

## Quick Start

```bash
git clone https://github.com/YOUR_USERNAME/ai-release-radar.git
cd ai-release-radar
pip install -r requirements.txt
cp .env.example .env          # fill in keys (all optional)
```

**Terminal 1 — dashboard:**
```bash
python dashboard/app.py
# Open http://localhost:5000
```

**Terminal 2 — monitor:**
```bash
python monitor.py
# Polls every 5 minutes, streams signals to dashboard via SSE
```

**One-shot mode** (for GitHub Actions / cron):
```bash
python monitor.py --once
```

## Configuration

Copy `.env.example` → `.env`. All keys are optional — the system runs on rule-based scoring without any API keys.

| Variable | Purpose | Required |
|----------|---------|----------|
| `DEEPSEEK_API_KEY` | LLM signal scoring | Optional |
| `MONITOR_GITHUB_TOKEN` | GitHub API rate limit 60→5000/h | Optional |
| `TELEGRAM_BOT_TOKEN` | Push notifications | Optional |
| `TELEGRAM_CHAT_ID` | Push notifications | Optional |
| `CHECK_INTERVAL` | Poll interval in seconds (default: 300) | Optional |
| `MAX_LLM_CALLS_PER_DAY` | Cost guard (default: 20) | Optional |

## Automated Monitoring via GitHub Actions

```yaml
# .github/workflows/monitor.yml
name: AI Signal Monitor
on:
  schedule:
    - cron: '*/15 * * * *'   # every 15 minutes
  workflow_dispatch:
jobs:
  monitor:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - run: pip install -r requirements.txt
      - run: python monitor.py --once
        env:
          DEEPSEEK_API_KEY: ${{ secrets.DEEPSEEK_API_KEY }}
          MONITOR_GITHUB_TOKEN: ${{ secrets.MONITOR_GITHUB_TOKEN }}
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
```

> **Note:** GitHub Actions free tier allows ~2000 min/month. At 15-min intervals that's ~2880 runs/month — consider 30-min intervals on free accounts.

## Tech Stack

- **Python 3.11** — stdlib only for SQLite, threading, SSE
- **Flask 3** + **Server-Sent Events** — live push without WebSocket overhead
- **SQLite** — zero-ops storage with content-hash deduplication
- **DeepSeek API** — LLM scoring with daily call cap
- **requests** — all external API calls

## Project Structure

```
├── monitor.py          # Main dispatcher loop
├── sources.py          # Platform signal extractors (GitHub/HF/Reddit/Twitter/arXiv)
├── discoverer.py       # Polymarket Gamma API auto-discovery
├── scorer.py           # Hybrid rule + LLM signal scoring
├── db.py               # SQLite layer (thread-safe, dedup)
├── notifier.py         # Telegram push notifications
├── dashboard/
│   ├── app.py          # Flask + SSE server
│   └── templates/
│       └── index.html  # 3-panel live UI
└── tests/              # 21 unit tests
```

## License

MIT
