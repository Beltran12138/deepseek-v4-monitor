#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Platform-specific signal extraction for AI model release monitoring.
Each function: fn(state: dict) -> list[dict] where each dict has keys:
  - source: str (platform name)
  - target_model: str (detected target model: deepseek, openai, anthropic, google)
  - content: str (human-readable signal description)
"""

import os
import re
import xml.etree.ElementTree as ET

import requests
from dotenv import load_dotenv

import scorer as _scorer

load_dotenv()

_UA_HEADERS = {"User-Agent": "AIMonitor/2.0 (personal research)"}

# ===================== GitHub =====================
def check_github(state: dict) -> list[dict]:
    """Extract GitHub signals: new repos, branches, commits with AI model keywords."""
    signals = []
    first_run = state.get("first_run", True)
    github_token = _get_github_token()
    headers = {"Accept": "application/vnd.github.v3+json"}
    if github_token:
        headers["Authorization"] = f"token {github_token}"

    # List of repos to monitor
    repos_to_monitor = ["DeepGEMM", "FlashMLA", "DeepEP", "3FS", "EPLB", "LPLB", "DeepSeek-V3", "DeepSeek-R1"]

    for repo in repos_to_monitor:
        try:
            # Check branches
            r = requests.get(
                f"https://api.github.com/repos/deepseek-ai/{repo}/branches?per_page=100",
                headers=headers, timeout=10,
            )
            if r.status_code in (404, 403):
                continue
            r.raise_for_status()

            branch_names = [b["name"] for b in r.json() if isinstance(b, dict)]
            prev_branches = set(state.get("github_branches", {}).get(repo, []))

            for b in branch_names:
                if b not in prev_branches and not first_run:
                    target = _scorer.detect_target(b)
                    if target:
                        signals.append({
                            "source": "github_new_branch",
                            "target_model": target,
                            "content": f"[GitHub/{repo}] New branch: {b}",
                        })

            state.setdefault("github_branches", {})[repo] = branch_names

            # Check latest commits with deduplication
            r2 = requests.get(
                f"https://api.github.com/repos/deepseek-ai/{repo}/commits?per_page=5",
                headers=headers, timeout=10,
            )
            if r2.status_code == 200 and r2.json():
                commits = r2.json()
                prev_shas = set(state.get("github_commits", {}).get(repo, []))
                for c in commits:
                    sha = c.get("sha", "")
                    if sha in prev_shas or first_run:
                        continue
                    msg = c["commit"]["message"]
                    target = _scorer.detect_target(msg)
                    if target:
                        first_line = msg.split("\n")[0][:80]
                        signals.append({
                            "source": "github_new_commit",
                            "target_model": target,
                            "content": f"[GitHub/{repo}] Commit: {first_line}",
                        })
                new_shas = {c.get("sha") for c in commits if c.get("sha")}
                merged = list(prev_shas | new_shas)
                state.setdefault("github_commits", {})[repo] = merged[-200:]

        except Exception:
            continue

    return signals


def _get_github_token():
    return os.getenv("MONITOR_GITHUB_TOKEN", os.getenv("GITHUB_TOKEN", ""))


# ===================== HuggingFace =====================
def check_huggingface(state: dict) -> list[dict]:
    """Extract HuggingFace signals: new models/datasets from deepseek-ai org."""
    signals = []

    for endpoint, state_key, label in [
        ("models", "hf_models", "model"),
        ("datasets", "hf_datasets", "dataset"),
    ]:
        try:
            url = f"https://huggingface.co/api/{endpoint}"
            params = {"author": "deepseek-ai", "sort": "lastModified", "direction": -1, "limit": 30}
            r = requests.get(url, params=params, timeout=15)
            r.raise_for_status()
            items = r.json()
            current_ids = {m["id"] for m in items if isinstance(m, dict)}
            prev_ids = set(state.get(state_key, []))

            # Check for new releases with target model keywords
            for item_id in current_ids:
                target = _scorer.detect_target(item_id)
                if target and item_id not in prev_ids:
                    signals.append({
                        "source": "huggingface",
                        "target_model": target,
                        "content": f"[HuggingFace {label}] 新仓库 → {item_id}",
                    })

            state[state_key] = list(current_ids)

        except Exception:
            continue

    return signals


# ===================== Reddit r/LocalLLaMA =====================
_REDDIT_QUERIES = ["DeepSeek V5", "GPT-5", "Claude 5", "Gemini 3"]
_REDDIT_HEADERS = {"User-Agent": "Mozilla/5.0 AIMonitor/2.0 (personal research)"}

def check_reddit(state: dict) -> list[dict]:
    """Extract Reddit signals: new posts mentioning AI model keywords."""
    signals = []
    first_run = state.get("first_run", True)
    seen = set(state.get("reddit_seen", []))

    for query in _REDDIT_QUERIES:
        try:
            r = requests.get(
                "https://www.reddit.com/r/LocalLLaMA/search.json",
                params={"q": query, "sort": "new", "limit": 10, "t": "week"},
                headers=_REDDIT_HEADERS,
                timeout=15,
            )
            r.raise_for_status()
            posts = r.json()["data"]["children"]
            new_posts = []
            for post in posts:
                d = post["data"]
                if d["id"] not in seen:
                    new_posts.append(d)
                    seen.add(d["id"])
            if not first_run:
                for p in sorted(new_posts, key=lambda x: x.get("score", 0), reverse=True):
                    title = p.get("title", "")
                    target = _scorer.detect_target(title)
                    if target:
                        score = p.get("score", 0)
                        signals.append({
                            "source": "reddit_hot",
                            "target_model": target,
                            "content": f"[Reddit] (+{score}) {title[:100]}",
                        })
        except Exception:
            continue

    state["reddit_seen"] = list(seen)[-400:]
    return signals


# ===================== Twitter (X) via RSSHub =====================
def check_twitter(state: dict) -> list[dict]:
    """Extract Twitter signals: posts from AI researcher accounts mentioning model keywords."""
    signals = []
    first_run = state.get("first_run", True)

    twitter_accounts = ["deepseek_ai", "_akhaliq", "swyx", "bindureddy"]
    rsshub_instances = [
        "https://rsshub.app",
        "https://rsshub.rssforever.com",
        "https://rsshub-instance.zeabur.app",
    ]

    for user in twitter_accounts:
        success = False
        for instance in rsshub_instances:
            try:
                url = f"{instance}/twitter/user/{user}"
                r = requests.get(url, timeout=15)
                if r.status_code != 200:
                    continue

                # Parse RSS XML for items
                items = re.findall(r"<item>(.*?)</item>", r.text, re.DOTALL)
                seen_ids = state.get("twitter_seen", {}).get(user, [])
                new_ids = []

                for item in items:
                    title_match = re.search(r"<title><!\[CDATA\[(.*?)]]></title>", item)
                    if not title_match:
                        title_match = re.search(r"<title>(.*?)</title>", item)

                    link_match = re.search(r"<link>(.*?)</link>", item)

                    if title_match and link_match:
                        title = title_match.group(1)
                        link = link_match.group(1)
                        tweet_id = link.split("/")[-1]

                        if tweet_id not in seen_ids:
                            new_ids.append(tweet_id)
                            target = _scorer.detect_target(title)
                            if target and not first_run:
                                signals.append({
                                    "source": "twitter",
                                    "target_model": target,
                                    "content": f"[Twitter/@{user}] {title[:100]}",
                                })

                state.setdefault("twitter_seen", {})[user] = (new_ids + seen_ids)[:50]
                success = True
                break

            except Exception:
                continue

    return signals


# ===================== arXiv =====================
def check_arxiv(state: dict) -> list[dict]:
    """Extract arXiv signals: papers mentioning AI model keywords."""
    signals = []
    seen = set(state.get("arxiv_seen", []))

    arxiv_targets = list(_scorer.TARGETS.keys())  # ["deepseek", "openai", "anthropic", "google"]
    arxiv_api = "https://export.arxiv.org/api/query"

    for kw in arxiv_targets:
        try:
            resp = requests.get(
                arxiv_api,
                params={"search_query": f"ti:{kw}", "sortBy": "submittedDate", "max_results": 5},
                timeout=10,
            )
            resp.raise_for_status()
            root = ET.fromstring(resp.content)
            ns = {"atom": "http://www.w3.org/2005/Atom"}

            for entry in root.findall("atom:entry", ns):
                entry_id_elem = entry.find("atom:id", ns)
                title_elem = entry.find("atom:title", ns)

                if entry_id_elem is None or title_elem is None:
                    continue

                raw_id = entry_id_elem.text.strip()
                arxiv_id = raw_id.split("/abs/")[-1].split("v")[0]
                title = title_elem.text.strip()

                if arxiv_id in seen:
                    continue

                seen.add(arxiv_id)  # deduplicate unconditionally
                target = _scorer.detect_target(title)
                if target:
                    signals.append({
                        "source": "arxiv",
                        "target_model": target,
                        "content": f"[arXiv] {title} — {raw_id}",
                    })

        except Exception:
            continue

    state["arxiv_seen"] = list(seen)[-500:]
    return signals
