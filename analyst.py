from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
import json
import math
import os
from pathlib import Path
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

CACHE_PATH = Path(__file__).resolve().parent / "data" / "analyst_cache.json"
CACHE_TTL_HOURS = 24
CACHE_VERSION = 7
RETRY_MINUTES = 60

FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "").strip()
OANOR_API_KEY = os.getenv("OANOR_API_KEY", "").strip()
FINNHUB_BASE = "https://finnhub.io/api/v1"
OANOR_BASE = "https://api.oanor.com/analyst-api"

RATING_WEIGHTS = {
    "strongbuy": 100.0,
    "buy": 75.0,
    "hold": 50.0,
    "sell": 25.0,
    "strongsell": 0.0,
}

# Oanor's public documentation is inconsistent about the free-tier rate limit.
# The FAQ says 1 request/sec, while the current pricing card says 3 requests/sec.
# Use 1 request/sec so the scanner remains safe on the stricter limit.
_oanor_lock = threading.Lock()
_oanor_last_request = 0.0
_finnhub_lock = threading.Lock()
_finnhub_last_request = 0.0


def _num(value):
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def _text(value):
    if value is None:
        return None
    text = str(value).strip()
    return text if text and text.lower() != "nan" else None


def _rate_limit(provider: str):
    global _oanor_last_request, _finnhub_last_request
    if provider == "oanor":
        lock = _oanor_lock
        interval = 1.05
        last_name = "oanor"
    else:
        lock = _finnhub_lock
        interval = 0.10
        last_name = "finnhub"

    with lock:
        now = time.monotonic()
        last = _oanor_last_request if last_name == "oanor" else _finnhub_last_request
        wait = interval - (now - last)
        if wait > 0:
            time.sleep(wait)
        current = time.monotonic()
        if last_name == "oanor":
            _oanor_last_request = current
        else:
            _finnhub_last_request = current


def _request_json(url: str, headers: dict[str, str] | None = None, timeout: int = 20):
    request = Request(url, headers={"User-Agent": "MarketIntel/1.0", **(headers or {})})
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _provider_request(provider: str, url: str, headers: dict[str, str] | None = None):
    _rate_limit(provider)
    try:
        return _request_json(url, headers), None
    except HTTPError as exc:
        try:
            body = exc.read().decode("utf-8", errors="replace")[:180]
        except Exception:
            body = ""
        return None, f"{provider} HTTP {exc.code}{': ' + body if body else ''}"
    except (URLError, TimeoutError) as exc:
        return None, f"{provider} network error: {str(exc)[:140]}"
    except Exception as exc:
        return None, f"{provider} error: {str(exc)[:140]}"


def _finnhub(symbol: str):
    if not FINNHUB_API_KEY:
        return None, "FINNHUB_API_KEY ontbreekt"
    query = urlencode({"symbol": symbol, "token": FINNHUB_API_KEY})
    return _provider_request("finnhub", f"{FINNHUB_BASE}/stock/recommendation?{query}")


def _oanor(symbol: str, endpoint: str):
    if not OANOR_API_KEY:
        return None, "OANOR_API_KEY ontbreekt"
    query = urlencode({"symbol": symbol})
    return _provider_request(
        "oanor",
        f"{OANOR_BASE}/{endpoint}?{query}",
        {"x-oanor-key": OANOR_API_KEY},
    )


def _consensus_score(counts):
    total = sum(float(counts.get(key, 0) or 0) for key in RATING_WEIGHTS)
    if total <= 0:
        return None
    return sum(float(counts.get(key, 0) or 0) * weight for key, weight in RATING_WEIGHTS.items()) / total


def _dominant_rating(counts):
    if sum(counts.values()) <= 0:
        return None
    key = max(counts, key=counts.get)
    return {
        "strongbuy": "STRONG BUY",
        "buy": "BUY",
        "hold": "HOLD",
        "sell": "SELL",
        "strongsell": "STRONG SELL",
    }[key]


def _unwrap(payload):
    if isinstance(payload, dict):
        for key in ("data", "result", "target", "consensus"):
            value = payload.get(key)
            if isinstance(value, dict):
                return value
            if isinstance(value, list) and value and isinstance(value[0], dict):
                return value[0]
        return payload
    if isinstance(payload, list) and payload and isinstance(payload[0], dict):
        return payload[0]
    return {}


def _finnhub_counts(payload):
    if not isinstance(payload, list) or not payload:
        return {}, None, None
    row = payload[0] if isinstance(payload[0], dict) else {}
    counts = {
        "strongbuy": int(_num(row.get("strongBuy")) or 0),
        "buy": int(_num(row.get("buy")) or 0),
        "hold": int(_num(row.get("hold")) or 0),
        "sell": int(_num(row.get("sell")) or 0),
        "strongsell": int(_num(row.get("strongSell")) or 0),
    }
    score = _consensus_score(counts)
    return counts, score, _text(row.get("period"))


def _oanor_targets(payload):
    raw = _unwrap(payload)
    current = _num(raw.get("current_price") or raw.get("currentPrice") or raw.get("price"))
    mean = _num(
        raw.get("mean")
        or raw.get("average")
        or raw.get("target_mean")
        or raw.get("mean_target")
        or raw.get("consensus_price_target")
        or raw.get("targetMean")
    )
    median = _num(raw.get("median") or raw.get("median_target") or raw.get("targetMedian"))
    low = _num(raw.get("low") or raw.get("low_target") or raw.get("target_low") or raw.get("targetLow"))
    high = _num(raw.get("high") or raw.get("high_target") or raw.get("target_high") or raw.get("targetHigh"))
    upside = _num(raw.get("implied_upside") or raw.get("upside") or raw.get("impliedUpside"))
    if upside is not None and abs(upside) > 2:
        upside /= 100.0
    if upside is None and current and mean:
        upside = mean / current - 1.0
    return current, mean, median, low, high, upside


def _one(ticker):
    errors = []

    # One request to each provider per ticker. This is deliberate. The previous
    # implementation made three Oanor requests plus an unnecessary Finnhub news
    # request for every stock, which made rate limits and partial results likely.
    finnhub_raw, finnhub_error = _finnhub(ticker)
    if finnhub_error:
        errors.append(finnhub_error)
    counts, score, period = _finnhub_counts(finnhub_raw)

    oanor_raw, oanor_error = _oanor(ticker, "v1/target")
    if oanor_error:
        errors.append(oanor_error)
    current, mean, median, low, high, upside = _oanor_targets(oanor_raw)

    total = sum(counts.values())
    analyst_count = total if total > 0 else None
    recommendation = _dominant_rating(counts)
    completeness = 0
    completeness += 1 if score is not None else 0
    completeness += 1 if mean is not None else 0
    completeness += 1 if analyst_count else 0
    completeness += 1 if total > 0 else 0

    has_provider_data = any(value is not None for value in (score, mean, median, low, high, upside)) or total > 0
    error = "; ".join(errors) if errors and not has_provider_data else None

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
        "analyst_target_upside": upside,
        "analyst_changes_30d": 0,
        "analyst_bullish_changes_30d": None,
        "analyst_bearish_changes_30d": None,
        "analyst_target_changes_30d": 0,
        "analyst_recent_changes": [],
        "analyst_firm_targets": [],
        "analyst_completeness": round(completeness / 4 * 100, 1),
        "analyst_cache_stale": False,
        "analyst_refresh_failed": False,
        "analyst_error": error,
        "last_earnings_date": None,
        "last_earnings_surprise_pct": None,
        "next_earnings_date": None,
        "recent_news": [],
        "analyst_source": "Finnhub recommendations + Oanor targets",
        "analyst_finnhub_period": period,
    }


def _has_data(row):
    if not isinstance(row, dict):
        return False
    return any([
        row.get("analyst_consensus_score") is not None,
        row.get("analyst_target_mean") is not None,
        row.get("analyst_count") is not None and row.get("analyst_count", 0) > 0,
        sum((row.get(key) or 0) for key in (
            "analyst_strong_buy", "analyst_buy", "analyst_hold", "analyst_sell", "analyst_strong_sell"
        )) > 0,
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
        timestamp = datetime.fromisoformat(value or "")
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        return timestamp
    except (TypeError, ValueError):
        return None


def download_analyst_data(tickers, workers=4, refresh_hours=CACHE_TTL_HOURS):
    """Load analyst data with durable GitHub Actions caching.

    Finnhub supplies the five recommendation buckets.
    Oanor supplies the current price and low/mean/median/high targets.
    Only two API requests are made per uncached ticker.
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
        payload = {key: value for key, value in item.items() if not key.startswith("_")}

        if item.get("_cache_version") == CACHE_VERSION and cached_at and cached_at >= cutoff and _has_data(payload):
            result[ticker] = payload
            continue

        attempted_at = _timestamp(item.get("_last_attempt_at"))
        if (
            item.get("_cache_version") == CACHE_VERSION
            and item.get("_refresh_failed")
            and attempted_at
            and attempted_at >= retry_cutoff
        ):
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
                old_payload = {key: value for key, value in old.items() if not key.startswith("_")}
                try:
                    row = future.result()
                except Exception as exc:
                    row = {
                        "ticker": ticker,
                        "analyst_completeness": 0.0,
                        "analyst_error": str(exc)[:180],
                    }

                if _has_data(row):
                    row["_cached_at"] = now.isoformat()
                    row["_last_attempt_at"] = now.isoformat()
                    row["_cache_version"] = CACHE_VERSION
                    row["_refresh_failed"] = False
                    cache[ticker] = row
                    result[ticker] = {key: value for key, value in row.items() if not key.startswith("_")}
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
