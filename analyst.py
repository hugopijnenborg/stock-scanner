from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
import json
import math
import os
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

CACHE_PATH = Path(__file__).resolve().parent / "data" / "analyst_cache.json"
CACHE_TTL_HOURS = 24
CACHE_VERSION = 6
RETRY_MINUTES = 60

FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "").strip()
OANOR_API_KEY = os.getenv("OANOR_API_KEY", "").strip()
FINNHUB_BASE = "https://finnhub.io/api/v1"
OANOR_BASE = "https://api.oanor.com/analyst-api"

RATING_WEIGHTS = {"strongbuy": 100.0, "buy": 75.0, "hold": 50.0, "sell": 25.0, "strongsell": 0.0}


def _num(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def _text(v):
    if v is None:
        return None
    s = str(v).strip()
    return s if s and s.lower() != "nan" else None


def _request_json(url: str, headers: dict[str, str] | None = None, timeout: int = 12):
    req = Request(url, headers={"User-Agent": "MarketIntel/1.0", **(headers or {})})
    with urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _finnhub(symbol: str, endpoint: str):
    if not FINNHUB_API_KEY:
        return None
    url = f"{FINNHUB_BASE}/{endpoint}?{urlencode({'symbol': symbol, 'token': FINNHUB_API_KEY})}"
    try:
        return _request_json(url)
    except Exception:
        return None


def _oanor(symbol: str, endpoint: str):
    if not OANOR_API_KEY:
        return None
    url = f"{OANOR_BASE}/{endpoint}?{urlencode({'symbol': symbol})}"
    try:
        return _request_json(url, {"x-oanor-key": OANOR_API_KEY})
    except Exception:
        return None


def _rating_key(value):
    if value is None:
        return None
    s = str(value).strip().lower().replace(" ", "").replace("_", "").replace("-", "")
    return {"strongbuy": "STRONG BUY", "buy": "BUY", "hold": "HOLD", "sell": "SELL", "strongsell": "STRONG SELL"}.get(s)


def _consensus_score(counts):
    total = sum(float(counts.get(k, 0) or 0) for k in RATING_WEIGHTS)
    if total <= 0:
        return None
    return sum(float(counts.get(k, 0) or 0) * w for k, w in RATING_WEIGHTS.items()) / total


def _normalise_payload(payload):
    if isinstance(payload, dict):
        for key in ("data", "result", "consensus", "target"):
            value = payload.get(key)
            if isinstance(value, dict):
                return value
        return payload
    if isinstance(payload, list):
        return payload[0] if payload and isinstance(payload[0], dict) else {}
    return {}


def _finnhub_counts(symbol: str):
    raw = _finnhub(symbol, "stock/recommendation")
    if not isinstance(raw, list) or not raw:
        return {}, None, None
    row = raw[0] if isinstance(raw[0], dict) else {}
    counts = {
        "strongbuy": int(_num(row.get("strongBuy")) or 0),
        "buy": int(_num(row.get("buy")) or 0),
        "hold": int(_num(row.get("hold")) or 0),
        "sell": int(_num(row.get("sell")) or 0),
        "strongsell": int(_num(row.get("strongSell")) or 0),
    }
    return counts, _consensus_score(counts), row.get("period")


def _oanor_consensus(symbol: str):
    raw = _normalise_payload(_oanor(symbol, "v1/consensus"))
    counts_raw = raw.get("aggregate_ratings") or raw.get("ratings") or raw
    counts = {
        "strongbuy": int(_num(counts_raw.get("strong_buy", counts_raw.get("strongBuy"))) or 0),
        "buy": int(_num(counts_raw.get("buy")) or 0),
        "hold": int(_num(counts_raw.get("hold")) or 0),
        "sell": int(_num(counts_raw.get("sell")) or 0),
        "strongsell": int(_num(counts_raw.get("strong_sell", counts_raw.get("strongSell"))) or 0),
    }
    rating = raw.get("consensus_rating") or raw.get("consensusRating") or raw.get("rating")
    score = _num(raw.get("consensus_score") or raw.get("mean_rating") or raw.get("average_rating"))
    if score is None and sum(counts.values()) > 0:
        score = _consensus_score(counts)
    count = _num(raw.get("total_analyst_count") or raw.get("analyst_count") or raw.get("totalAnalystCount"))
    return counts, score, int(count) if count is not None else None, _rating_key(rating)


def _oanor_targets(symbol: str):
    raw = _normalise_payload(_oanor(symbol, "v1/target"))
    current = _num(raw.get("current_price") or raw.get("currentPrice") or raw.get("price"))
    mean = _num(raw.get("mean") or raw.get("average") or raw.get("target_mean") or raw.get("mean_target") or raw.get("consensus_price_target"))
    median = _num(raw.get("median") or raw.get("median_target"))
    low = _num(raw.get("low") or raw.get("low_target") or raw.get("target_low"))
    high = _num(raw.get("high") or raw.get("high_target") or raw.get("target_high"))
    upside = _num(raw.get("implied_upside") or raw.get("upside"))
    if upside is not None and abs(upside) > 2:
        upside /= 100.0
    if upside is None and current and mean:
        upside = mean / current - 1.0
    return current, mean, median, low, high, upside


def _oanor_history(symbol: str):
    raw = _oanor(symbol, "v1/history")
    data = raw.get("data") if isinstance(raw, dict) else raw
    if not isinstance(data, list):
        return []
    out = []
    for row in data[:12]:
        if not isinstance(row, dict):
            continue
        out.append({
            "date": _text(row.get("date") or row.get("period")),
            "target": _num(row.get("target") or row.get("mean_target") or row.get("consensus_price_target")),
            "buy": _num(row.get("buy")),
            "hold": _num(row.get("hold")),
            "sell": _num(row.get("sell")),
        })
    return out


def _recent_news(symbol: str):
    raw = _finnhub(symbol, "company-news")
    if not isinstance(raw, list):
        return []
    # The endpoint requires from/to on many plans. Keep this enrichment optional.
    return []


def _one(ticker):
    counts_f, score_f, period = _finnhub_counts(ticker)
    counts_o, score_o, analyst_count_o, rating_o = _oanor_consensus(ticker)
    current, mean, median, low, high, upside = _oanor_targets(ticker)

    # Oanor is the primary target/consensus source. Finnhub supplies the five-way
    # recommendation distribution and acts as the free fallback for consensus counts.
    counts = counts_o if sum(counts_o.values()) > 0 else counts_f
    score = score_o if score_o is not None else score_f
    if sum(counts.values()) > 0 and (score is None or score < 0 or score > 100):
        score = _consensus_score(counts)

    total = sum(counts.values())
    analyst_count = analyst_count_o or (total if total > 0 else None)
    recommendation = rating_o
    if recommendation is None and total > 0:
        recommendation = _rating_key(max(counts, key=counts.get))

    history = _oanor_history(ticker)
    target_upside = upside
    changes_30d = 0
    if len(history) >= 2:
        first_target = history[-1].get("target")
        latest_target = history[0].get("target")
        if first_target and latest_target and first_target != latest_target:
            changes_30d = 1

    completeness = 0
    completeness += 1 if score is not None else 0
    completeness += 1 if mean is not None else 0
    completeness += 1 if analyst_count else 0
    completeness += 1 if total > 0 else 0

    return {
        "ticker": ticker,
        "analyst_recommendation": recommendation,
        "analyst_consensus_score": round(score, 1) if score is not None else None,
        "analyst_strong_buy": counts.get("strongbuy", 0),
        "analyst_buy": counts.get("buy", 0),
        "analyst_hold": counts.get("hold", 0),
        "analyst_sell": counts.get("sell", 0),
        "analyst_strong_sell": counts.get("strongsell", 0),
        "analyst_count": analyst_count,
        "analyst_target_current": current,
        "analyst_target_mean": mean,
        "analyst_target_median": median,
        "analyst_target_low": low,
        "analyst_target_high": high,
        "analyst_target_upside": target_upside,
        "analyst_changes_30d": changes_30d,
        "analyst_bullish_changes_30d": None,
        "analyst_bearish_changes_30d": None,
        "analyst_target_changes_30d": changes_30d,
        "analyst_recent_changes": history,
        # Free sources do not expose reliable firm-by-firm targets through these endpoints.
        # Keep the field explicit so the frontend can show unavailable instead of fake values.
        "analyst_firm_targets": [],
        "analyst_completeness": round(completeness / 4 * 100, 1),
        "analyst_cache_stale": False,
        "analyst_refresh_failed": False,
        "analyst_error": None if completeness else "No analyst data returned by Finnhub/Oanor",
        "last_earnings_date": None,
        "last_earnings_surprise_pct": None,
        "next_earnings_date": None,
        "recent_news": _recent_news(ticker),
        "analyst_source": "Oanor + Finnhub",
        "analyst_finnhub_period": period,
    }


def _has_data(row):
    if not isinstance(row, dict):
        return False
    return any([
        row.get("analyst_consensus_score") is not None,
        row.get("analyst_target_mean") is not None,
        row.get("analyst_count") is not None and row.get("analyst_count", 0) > 0,
        sum((row.get(k) or 0) for k in ("analyst_strong_buy", "analyst_buy", "analyst_hold", "analyst_sell", "analyst_strong_sell")) > 0,
    ])


def _load_cache():
    try:
        data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def _save_cache(cache):
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=2, allow_nan=False), encoding="utf-8")


def _timestamp(value):
    try:
        ts = datetime.fromisoformat(value or "")
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return ts
    except (TypeError, ValueError):
        return None


def download_analyst_data(tickers, workers=4, refresh_hours=CACHE_TTL_HOURS):
    """Load analyst data from free Oanor + Finnhub APIs with durable caching.

    Oanor supplies low/mean/high/median targets and consensus history.
    Finnhub supplies the five-category recommendation distribution.
    Empty provider responses never overwrite a previously good cache entry.
    """
    cache = _load_cache()
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=refresh_hours)
    retry_cutoff = now - timedelta(minutes=RETRY_MINUTES)
    result = {}
    stale = []

    for ticker in dict.fromkeys(tickers):
        item = cache.get(ticker) or {}
        cached_at = _timestamp(item.get("_cached_at"))
        payload = {k: v for k, v in item.items() if not k.startswith("_")}
        if item.get("_cache_version") == CACHE_VERSION and cached_at and cached_at >= cutoff and _has_data(payload):
            result[ticker] = payload
            continue
        attempted_at = _timestamp(item.get("_last_attempt_at"))
        if item.get("_cache_version") == CACHE_VERSION and item.get("_refresh_failed") and attempted_at and attempted_at >= retry_cutoff:
            if _has_data(payload):
                payload["analyst_cache_stale"] = True
                payload["analyst_refresh_failed"] = True
                result[ticker] = payload
            continue
        stale.append(ticker)

    if stale:
        with ThreadPoolExecutor(max_workers=max(1, min(int(workers), 4))) as pool:
            futures = {pool.submit(_one, ticker): ticker for ticker in stale}
            for future in as_completed(futures):
                ticker = futures[future]
                old = cache.get(ticker) or {}
                old_payload = {k: v for k, v in old.items() if not k.startswith("_")}
                try:
                    row = future.result()
                except Exception as exc:
                    row = {"ticker": ticker, "analyst_completeness": 0.0, "analyst_error": str(exc)[:160]}

                if _has_data(row):
                    row["_cached_at"] = now.isoformat()
                    row["_last_attempt_at"] = now.isoformat()
                    row["_cache_version"] = CACHE_VERSION
                    row["_refresh_failed"] = False
                    cache[ticker] = row
                    result[ticker] = {k: v for k, v in row.items() if not k.startswith("_")}
                elif _has_data(old_payload):
                    old_payload["analyst_cache_stale"] = True
                    old_payload["analyst_refresh_failed"] = True
                    old_payload["analyst_error"] = row.get("analyst_error") or "Provider returned incomplete analyst data"
                    cache[ticker] = {
                        **old_payload,
                        "_cached_at": old.get("_cached_at"),
                        "_last_attempt_at": now.isoformat(),
                        "_cache_version": CACHE_VERSION,
                        "_refresh_failed": True,
                    }
                    result[ticker] = old_payload
                else:
                    cache[ticker] = {
                        **row,
                        "_cached_at": None,
                        "_last_attempt_at": now.isoformat(),
                        "_cache_version": CACHE_VERSION,
                        "_refresh_failed": True,
                    }
        _save_cache(cache)

    return result
