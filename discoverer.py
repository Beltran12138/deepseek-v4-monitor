import datetime
import requests

import scorer
import db


def discover_markets(state: dict) -> list[dict]:
    """Query Polymarket Gamma API for active markets; detect price spikes."""
    signals = []
    prev_prices = state.get("market_prices", {})
    current_prices = {}

    for keyword in scorer.TARGETS:
        try:
            r = requests.get(
                "https://gamma-api.polymarket.com/markets",
                params={"q": keyword, "active": "true", "closed": "false"},
                timeout=15,
            )
            r.raise_for_status()
            items = r.json()
            if not isinstance(items, list):
                continue

            now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

            for item in items:
                slug = item.get("slug") or item.get("conditionId", "")
                if not slug:
                    continue
                title = item.get("question", "")
                outcome_prices = item.get("outcomePrices", ["0"])
                try:
                    current_price = float(outcome_prices[0])
                except (ValueError, IndexError):
                    current_price = 0.0
                try:
                    volume = float(item.get("volume", 0))
                except ValueError:
                    volume = 0.0

                model = scorer.detect_target(title) or "unknown"
                db.upsert_market(slug, title, model, current_price, volume, now)
                if slug in current_prices:
                    continue  # already processed this slug in this run
                current_prices[slug] = current_price

                if model == "unknown":
                    continue
                prev_price = prev_prices.get(slug)
                if prev_price is not None and volume >= 1000:
                    if abs(current_price - prev_price) >= 0.10:
                        signals.append({
                            "source": "polymarket_price_spike",
                            "target_model": model,
                            "content": f"[Polymarket] {title[:80]} | price {prev_price:.2f}→{current_price:.2f}",
                        })

        except Exception:
            continue

    state["market_prices"] = {**prev_prices, **current_prices}
    return signals
