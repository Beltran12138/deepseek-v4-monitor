#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DeepSeek V4 发布信号监控器
监控：HuggingFace / GitHub / Polymarket / Reddit r/LocalLLaMA
"""

import requests
import json
import time
import sys
import os
import re
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# Windows 控制台 UTF-8 设置（在所有 print 之前）
if sys.platform == "win32":
    os.system("chcp 65001 > nul 2>&1")
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ===================== 用户配置 =====================
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")  # 从环境变量获取
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "300"))
PRICE_ALERT_THRESHOLD = float(os.getenv("PRICE_ALERT_THRESHOLD", "0.04"))

# Telegram 通知配置
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
# 如果你在国内使用，可能需要配置代理，例如: {"https": "http://127.0.0.1:7890"}
proxy_env = os.getenv("TELEGRAM_PROXIES")
TELEGRAM_PROXIES = {"https": proxy_env} if proxy_env else None

# Polymarket 监控配置
POLYMARKET_SLUGS = [
    "deepseek-v4-released-by-march-31",
    "deepseek-v4-released-by-march-15"
]

# Twitter (X) 监控账号 (通过 RSSHub)
TWITTER_ACCOUNTS = ["deepseek_ai", "_akhaliq", "swyx", "bindureddy"]
RSSHUB_INSTANCES = [
    "https://rsshub.app",
    "https://rsshub.rssforever.com",
    "https://rsshub-instance.zeabur.app",
]

# 监控的 GitHub 基础设施仓库
GITHUB_REPOS = ["DeepGEMM", "FlashMLA", "DeepEP", "3FS", "EPLB", "LPLB", "DeepSeek-V3", "DeepSeek-R1"]

# V4 相关关键词（出现在仓库名/分支名中即触发告警）
V4_KEYWORDS = ["v4", "V4", "next-gen", "nextgen", "model1", "MODEL1",
               "v4-support", "v4-base", "v4-chat", "deepseek-v4"]

STATE_FILE = Path(__file__).parent / "state.json"

# ===================== 终端颜色 =====================
class C:
    RED    = "\033[91m"
    YELLOW = "\033[93m"
    GREEN  = "\033[92m"
    CYAN   = "\033[96m"
    BOLD   = "\033[1m"
    RESET  = "\033[0m"
    GRAY   = "\033[90m"

def log(level, message):
    now = datetime.now().strftime("%H:%M:%S")
    icons = {
        "ALERT": f"{C.RED}{C.BOLD}!! [告警]{C.RESET}",
        "WARN":  f"{C.YELLOW}** [注意]{C.RESET}",
        "OK":    f"{C.GREEN}ok [正常]{C.RESET}",
        "INFO":  f"{C.CYAN}-- [信息]{C.RESET}",
    }
    try:
        print(f"{C.GRAY}[{now}]{C.RESET} {icons.get(level, '')} {message}")
    except UnicodeEncodeError:
        safe_msg = message.encode("ascii", errors="replace").decode("ascii")
        print(f"[{now}] {level}: {safe_msg}")

# ===================== 通知推送 =====================
def notify_windows(title, body):
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, body[:512], title, 0x40 | 0x1000)
    except Exception:
        pass

def send_telegram_notification(title, body):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        text = f"<b>{title}</b>\n\n{body}"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "HTML"
        }
        r = requests.post(url, json=payload, proxies=TELEGRAM_PROXIES, timeout=15)
        r.raise_for_status()
        log("INFO", "[Telegram] 通知已发送")
    except Exception as e:
        log("WARN", f"[Telegram] 发送失败: {e}")

# ===================== 状态管理 =====================
def load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "hf_models": [],
        "hf_datasets": [],
        "github_branches": {},
        "github_latest_commit": {},
        "polymarket_prices": {},
        "reddit_seen": [],
        "twitter_seen": {},
        "first_run": True,
    }

def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")

# ===================== HuggingFace 监控 =====================
def check_huggingface(state):
    alerts = []
    first_run = state.get("first_run", True)

    for endpoint, state_key, label in [
        ("models",   "hf_models",   "模型"),
        ("datasets", "hf_datasets", "数据集"),
    ]:
        try:
            url = f"https://huggingface.co/api/{endpoint}"
            params = {"author": "deepseek-ai", "sort": "lastModified",
                      "direction": -1, "limit": 30}
            r = requests.get(url, params=params, timeout=15)
            r.raise_for_status()
            items = r.json()
            current_ids = {m["id"] for m in items if isinstance(m, dict)}
            prev_ids = set(state.get(state_key, []))

            if not first_run:
                for new_id in current_ids - prev_ids:
                    alerts.append(("ALERT", f"[HuggingFace {label}] 新仓库出现！→ {new_id}"))

            # 无论新旧，检查关键词
            for item_id in current_ids:
                name_lower = item_id.lower()
                for kw in V4_KEYWORDS:
                    if kw.lower() in name_lower:
                        if item_id not in prev_ids or first_run:
                            alerts.append(("ALERT", f"[HuggingFace {label}] [!!] V4关键词仓库 → {item_id}"))
                        break

            state[state_key] = list(current_ids)
            if not any(f"HuggingFace {label}" in a[1] for a in alerts):
                log("OK", f"[HuggingFace {label}] 共 {len(current_ids)} 个，无异动")

        except Exception as e:
            log("WARN", f"[HuggingFace {label}] 请求失败: {e}")

    return alerts

# ===================== GitHub 监控 =====================
def check_github(state):
    alerts = []
    first_run = state.get("first_run", True)
    headers = {"Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"

    # 检查组织下是否新增仓库
    try:
        url = "https://api.github.com/orgs/deepseek-ai/repos?per_page=100&sort=created&direction=desc"
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code == 200:
            repos = r.json()
            current_repo_names = {repo["name"] for repo in repos if isinstance(repo, dict)}
            prev_repo_names = set(state.get("github_all_repos", []))
            
            if not first_run:
                new_repos = current_repo_names - prev_repo_names
                for new_repo in new_repos:
                    alerts.append(("ALERT", f"[GitHub] 🔥 新仓库创建！→ deepseek-ai/{new_repo}"))
                    for kw in V4_KEYWORDS:
                        if kw.lower() in new_repo.lower():
                            alerts.append(("ALERT", f"[GitHub] 🔥🔥 V4关键词匹配！→ {new_repo}"))
            
            state["github_all_repos"] = list(current_repo_names)
            log("OK", f"[GitHub/Org] 共有 {len(current_repo_names)} 个公开仓库")
    except Exception as e:
        log("WARN", f"[GitHub] 组织仓库列表获取失败: {e}")

    # 逐个检查基础设施仓库
    for repo in GITHUB_REPOS:
        try:
            # 检查分支
            r = requests.get(
                f"https://api.github.com/repos/deepseek-ai/{repo}/branches?per_page=100",
                headers=headers, timeout=10
            )
            if r.status_code == 404:
                continue
            if r.status_code != 200:
                log("WARN", f"[GitHub/{repo}] API 返回 {r.status_code}")
                continue

            branches = r.json()
            branch_names = [b["name"] for b in branches if isinstance(b, dict)]
            prev_branches = set(state["github_branches"].get(repo, []))
            curr_branches = set(branch_names)

            if not first_run:
                for new_b in curr_branches - prev_branches:
                    alerts.append(("WARN", f"[GitHub/{repo}] 新分支出现 → {new_b}"))

            for b in branch_names:
                for kw in V4_KEYWORDS:
                    if kw.lower() in b.lower():
                        if b not in prev_branches or first_run:
                            alerts.append(("ALERT", f"[GitHub/{repo}] [!!] V4关键词分支！→ {b}"))
                        break

            state["github_branches"][repo] = branch_names

            # 检查最新 commit
            r2 = requests.get(
                f"https://api.github.com/repos/deepseek-ai/{repo}/commits?per_page=3",
                headers=headers, timeout=10
            )
            if r2.status_code == 200 and r2.json():
                commits = r2.json()
                latest = commits[0]
                latest_sha = latest["sha"][:7]
                latest_msg = latest["commit"]["message"].split("\n")[0][:60]
                prev_sha = state["github_latest_commit"].get(repo)

                if not first_run and prev_sha and prev_sha != latest_sha:
                    # 检查近3条commit消息有无V4关键词
                    for c in commits:
                        msg = c["commit"]["message"].lower()
                        for kw in V4_KEYWORDS:
                            if kw.lower() in msg:
                                alerts.append(("ALERT",
                                    f"[GitHub/{repo}] [!!] V4关键词commit！→ {c['commit']['message'].split(chr(10))[0][:50]}"))
                                break
                    alerts.append(("WARN", f"[GitHub/{repo}] 新commit: {latest_msg}"))

                state["github_latest_commit"][repo] = latest_sha

            if not any(repo in a[1] for a in alerts):
                log("OK", f"[GitHub/{repo}] {len(branch_names)} 个分支，最新commit: {state['github_latest_commit'].get(repo, '?')}")

        except Exception as e:
            log("WARN", f"[GitHub/{repo}] 检查失败: {e}")

    return alerts

# ===================== Polymarket 监控 =====================
def check_polymarket(state):
    alerts = []
    first_run = state.get("first_run", True)

    for slug in POLYMARKET_SLUGS:
        try:
            # 获取事件详情
            url = f"https://gamma-api.polymarket.com/events/slug/{slug}"
            r = requests.get(url, timeout=15)
            if r.status_code != 200:
                continue
            
            event = r.json()
            title = event.get("title", slug)
            markets = event.get("markets", [])
            
            for market in markets:
                # 只关心 "Yes" 结局的市场（通常是第一个）
                market_id = str(market.get("id", ""))
                outcomes = json.loads(market.get("outcomes", "[]"))
                prices = json.loads(market.get("outcomePrices", "[]"))
                
                if not prices or len(prices) < 1:
                    continue
                
                # 通常 outcomes[0] 是 "Yes"
                yes_price = float(prices[0])
                label = f"{title} [{outcomes[0]}]"
                
                prev_price = state["polymarket_prices"].get(market_id)
                if not first_run and prev_price is not None:
                    change = yes_price - float(prev_price)
                    if abs(change) >= PRICE_ALERT_THRESHOLD:
                        direction = "/\ 上涨" if change > 0 else "\/ 下跌"
                        alerts.append(("ALERT", 
                            f"[Polymarket] {direction} {change:+.1%}！"
                            f"现价={yes_price:.0%} | {title[:40]}"))

                state["polymarket_prices"][market_id] = yes_price
                log("OK", f"[Polymarket] YES={yes_price:.0%} | {title[:50]}")

                # 检查交易额异动
                volume_24h = float(market.get("volume24hr", 0))
                if not first_run and volume_24h > 10000: # 24h 交易额大于 1w USD 提醒
                     log("INFO", f"[Polymarket] 24h交易活跃: ${volume_24h:,.0f}")

        except Exception as e:
            log("WARN", f"[Polymarket/{slug}] 检查失败: {e}")

    return alerts

# ===================== Twitter (X) 监控 =====================
def check_twitter(state):
    alerts = []
    first_run = state.get("first_run", True)
    
    for user in TWITTER_ACCOUNTS:
        success = False
        for instance in RSSHUB_INSTANCES:
            try:
                url = f"{instance}/twitter/user/{user}"
                r = requests.get(url, timeout=15)
                if r.status_code != 200:
                    continue
                
                # 简单解析 RSS XML (不使用外部库)
                items = re.findall(r"<item>(.*?)</item>", r.text, re.DOTALL)
                seen_ids = state["twitter_seen"].get(user, [])
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
                            if not first_run:
                                # 检查关键词
                                is_v4 = any(kw.lower() in title.lower() for kw in V4_KEYWORDS)
                                level = "ALERT" if is_v4 else "INFO"
                                alerts.append((level, f"[Twitter/@{user}] {'🔥 ' if is_v4 else ''}{title[:100]}"))
                
                state["twitter_seen"][user] = (new_ids + seen_ids)[:50]
                log("OK", f"[Twitter/@{user}] 检查完成，共 {len(items)} 条")
                success = True
                break
            except Exception:
                continue
        
        if not success:
            log("WARN", f"[Twitter/@{user}] RSSHub 所有实例均失败")
            
    return alerts

# ===================== Reddit r/LocalLLaMA 监控 =====================
def check_reddit(state):
    alerts = []
    first_run = state.get("first_run", True)

    try:
        url = "https://www.reddit.com/r/LocalLLaMA/search.json"
        params = {"q": "DeepSeek V4", "sort": "new", "limit": 15, "t": "week"}
        headers = {"User-Agent": "Mozilla/5.0 DeepSeekMonitor/1.0 (personal research)"}
        r = requests.get(url, params=params, headers=headers, timeout=15)
        r.raise_for_status()

        posts = r.json()["data"]["children"]
        seen = set(state.get("reddit_seen", []))
        new_posts = []

        for post in posts:
            d = post["data"]
            if d["id"] not in seen:
                new_posts.append(d)
                seen.add(d["id"])

        if not first_run:
            for p in sorted(new_posts, key=lambda x: x.get("score", 0), reverse=True):
                score = p.get("score", 0)
                title = p.get("title", "")[:70]
                level = "ALERT" if score >= 50 else "WARN"
                alerts.append((level, f"[Reddit] 新帖(+{score}): {title}"))

        state["reddit_seen"] = list(seen)[-200:]

        if not new_posts or first_run:
            log("OK", f"[Reddit] 无新帖 (已追踪 {len(seen)} 篇)")

    except Exception as e:
        log("WARN", f"[Reddit] 检查失败: {e}")

    return alerts

# ===================== 主循环 =====================
def main():
    # Windows 控制台 UTF-8
    if sys.platform == "win32":
        os.system("chcp 65001 > nul 2>&1")
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    banner = f"""
{C.BOLD}{C.CYAN}╔══════════════════════════════════════════════╗
║     DeepSeek V4 发布信号监控器  v1.2         ║
║  HF · GitHub · PolyMarket · Reddit · X · TG  ║
╚══════════════════════════════════════════════╝{C.RESET}
  检查间隔: {CHECK_INTERVAL}秒 ({CHECK_INTERVAL//60}分钟)
  状态文件: {STATE_FILE}
  按 Ctrl+C 停止
"""
    print(banner)

    state = load_state()
    round_num = 0

    while True:
        round_num += 1
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n{C.BOLD}{'─'*55}")
        print(f"  第 {round_num} 轮检查  {ts}")
        print(f"{'─'*55}{C.RESET}")

        all_alerts = []
        all_alerts += check_huggingface(state)
        all_alerts += check_github(state)
        all_alerts += check_polymarket(state)
        all_alerts += check_reddit(state)
        all_alerts += check_twitter(state)

        # 首轮运行完毕后取消 first_run 标记
        if state.get("first_run"):
            state["first_run"] = False

        save_state(state)

        if all_alerts:
            print(f"\n{C.RED}{C.BOLD}{'!!' * 18}{C.RESET}")
            for level, msg in all_alerts:
                log(level, msg)
            print(f"{C.RED}{C.BOLD}{'!!' * 18}{C.RESET}\n")

            # 告警推送（电脑弹窗 + Telegram）
            alert_body = "\n".join(msg for _, msg in all_alerts[:5])
            notify_windows("!! DeepSeek V4 监控告警！", alert_body)
            send_telegram_notification("DeepSeek V4 监控告警", alert_body)
        else:
            print(f"\n{C.GREEN}  ok 本轮无异动{C.RESET}")

        print(f"\n{C.GRAY}  下次检查: {CHECK_INTERVAL}秒后...{C.RESET}")
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{C.YELLOW}已停止监控。再见！{C.RESET}\n")
