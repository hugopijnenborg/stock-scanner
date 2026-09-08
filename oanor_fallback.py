from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import threading
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

CACHE_PATH = Path(__file__).resolve().parent / "data" / "oanor_target_cache.json"
CACHE_TTL_HOURS = 24
BASE_URL = "https://api.oanor.com/analyst-api/v1/target"
# Oanor's current pricing card says 3 req/s, while its FAQ still says 1 req/s.
# Use the conservative limit so the free tier is not accidentally rate-limited.
MIN_REQUEST_INTERVAL = 1.05

_lock = threading.Lock()
_last_request = 0.0


def _num(value):
    try:
        value = float(value)
        return value if value > 0 else None
    except (TypeError, ValueError):
        return None


def _first(data: dict, keys: tuple[str, ...]):
    if not isinstance(data, dict):
        return None
    for key in keys:
        value = _num(data.get(key))
        if value is not None:
            return value
    return None


def _cache_load() -> dict:
    try:
        if not CACHE_PATH.exists():
            return {}
        with CACHE_PATH.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _cache_save(cache: dict) -> None:
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = CACHE_PATH.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as handle:
            json.dump(cache, handle, indent=2, sort_keys=True)
        tmp.replace(CACHE_PATH)
    except Exception:
        pass


def _rate_limit() -> None:
    global _last_request
    with _lock:
        now = time.monotonic()
        wait = MIN_REQUEST_INTERVAL - (now - _last_request)
        if wait > 0:
            time.sleep(wait)
        _last_request = time.monotonic()


def _request_json(symbol: str) -> dict:
    query = urlencode({"symbol": symbol})
    request = Request(
        f"{BASE_URL}?{query}",
        headers={"x-oanor-key": os.getenv("OANOR_API_KEY", ""), "User-Agent": "MarketIntel/1.0"},
    )
    with urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def _extract(payload: dict) -> dict:
    # Be tolerant of both a direct response object and common API wrappers.
    data = payload.get("data", payload) if isinstance(payload, dict) else {}
    if isinstance(data, list):
        data = data[0] if data else {}
    if not isinstance(data, dict):
        return {}

    current = _first(data, ("current", "currentPrice", "current_price", "price"))
    mean = _first(data, ("mean", "average", "targetMean", "target_mean", "mean_target", "consensus_price_target"))
    median = _first(data, ("median", "targetMedian", "target_median"))
    low = _first(data, ("low", "targetLow", "target_low"))
    high = _first(data, ("high", "targetHigh", "target_high"))
    upside = data.get("implied_upside", data.get("impliedUpside", data.get("upside")))
    try:
        upside = float(upside) if upside is not None else None
        if upside is not None and abs(upside) > 2:
            upside /= 100.0
    except (TypeError, ValueError):
        upside = None

    return {"current": current, "mean": mean, "median": median, "low": low, "high": high, "upside": upside}


def get_target(ticker: str, cache: dict | None = None) -> dict:
    ticker = str(ticker).upper().strip()
    cache = cache if cache is not None else _cache_load()
    now = datetime.now(timezone.utc)
    cached = cache.get(ticker)
    if isinstance(cached, dict):
        try:
            cached_at = datetime.fromisoformat(cached["cached_at"])
            if cached_at.tzinfo is None:
                cached_at = cached_at.replace(tzinfo=timezone.utc)
            if now - cached_at < timedelta(hours=CACHE_TTL_HOURS):
                return cached.get("data") or {}
        except Exception:
            pass

    if not os.getenv("OANOR_API_KEY"):
        return {}

    _rate_limit()
    try:
        data = _extract(_request_json(ticker))
    except Exception:
        return {}

    cache[ticker] = {"cached_at": now.isoformat(), "data": data}
    _cache_save(cache)
    return data


def enrich_missing_targets(analyst_data: dict) -> dict:
    """Fill only analyst target fields that Yahoo did not provide."""
    if not analyst_data or not os.getenv("OANOR_API_KEY"):
        return analyst_data

    cache = _cache_load()
    for ticker, row in analyst_data.items():
        if not isinstance(row, dict):
            continue

        target_fields = (
            "analyst_target_current",
            "analyst_target_mean",
            "analyst_target_median",
            "analyst_target_low",
            "analyst_target_high",
        )
        if all(row.get(field) is not None for field in target_fields):
            continue

        target = get_target(ticker, cache)
        if not target:
            continue

        row_changed = False
        mapping = {
            "analyst_target_current": target.get("current"),
            "analyst_target_mean": target.get("mean"),
            "analyst_target_median": target.get("median"),
            "analyst_target_low": target.get("low"),
            "analyst_target_high": target.get("high"),
        }
        for field, value in mapping.items():
            if row.get(field) is None and value is not None:
                row[field] = value
                row_changed = True

        current = row.get("analyst_target_current")
        mean = row.get("analyst_target_mean")
        if row.get("analyst_target_upside") is None:
            if target.get("upside") is not None:
                row["analyst_target_upside"] = target["upside"]
                row_changed = True
            elif current and mean:
                row["analyst_target_upside"] = mean / current - 1
                row_changed = True

        if row_changed:
            row["analyst_target_source"] = "Yahoo Finance / Oanor fallback"

    return analyst_data
