from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path

import pandas as pd
import yfinance as yf

CACHE_PATH = Path(__file__).resolve().parent / "data" / "analyst_cache.json"
CACHE_TTL_HOURS = 12

RATING_WEIGHTS = {"strongbuy": 100.0, "buy": 75.0, "hold": 50.0, "sell": 25.0, "strongsell": 0.0}
BULLISH_ACTIONS = {"up", "upgrade", "upgraded", "init", "initiated", "reiterated"}
BEARISH_ACTIONS = {"down", "downgrade", "downgraded"}


def _num(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def _clean_text(v):
    if v is None:
        return None
    text = str(v).strip()
    return text if text and text.lower() != "nan" else None


def _rating_key(value):
    if value is None:
        return None
    s = str(value).strip().lower().replace(" ", "").replace("_", "").replace("-", "")
    aliases = {"strongbuy": "STRONG BUY", "buy": "BUY", "hold": "HOLD", "sell": "SELL", "strongsell": "STRONG SELL"}
    return aliases.get(s, str(value).strip().upper())


def _consensus_score(counts):
    total = sum(float(counts.get(k, 0) or 0) for k in RATING_WEIGHTS)
    if total <= 0:
        return None
    return sum(float(counts.get(k, 0) or 0) * weight for k, weight in RATING_WEIGHTS.items()) / total


def _parse_recommendations(df):
    counts = {k: 0 for k in RATING_WEIGHTS}
    if not isinstance(df, pd.DataFrame) or df.empty:
        return counts, None
    row = df.iloc[-1]
    for key in counts:
        if key in row.index:
            counts[key] = int(_num(row[key]) or 0)
    return counts, _consensus_score(counts)


def _parse_changes(df):
    if not isinstance(df, pd.DataFrame) or df.empty:
        return [], 0, 0, 0
    d = df.copy()
    if not isinstance(d.index, pd.DatetimeIndex):
        try:
            d.index = pd.to_datetime(d.index, utc=True)
        except Exception:
            pass
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=30)
    changes = []
    bullish = bearish = target_changes = 0
    for idx, row in d.head(20).iterrows():
        try:
            ts = pd.Timestamp(idx)
            if ts.tzinfo is None:
                ts = ts.tz_localize("UTC")
            ts = ts.tz_convert("UTC")
        except Exception:
            ts = None
        action = _clean_text(row.get("action"))
        firm = _clean_text(row.get("firm"))
        to_grade = _clean_text(row.get("toGrade"))
        from_grade = _clean_text(row.get("fromGrade"))
        action_l = (action or "").lower().replace(" ", "")
        if ts is not None and ts.to_pydatetime() >= cutoff:
            if any(x in action_l for x in BULLISH_ACTIONS):
                bullish += 1
            if any(x in action_l for x in BEARISH_ACTIONS):
                bearish += 1
            if "target" in action_l:
                target_changes += 1
        if len(changes) < 6:
            changes.append({
                "date": ts.isoformat() if ts is not None else None,
                "firm": firm,
                "action": action,
                "from_grade": from_grade,
                "to_grade": to_grade,
            })
    return changes, bullish, bearish, target_changes


def _one(ticker):
    out = {"ticker": ticker, "analyst_completeness": 0.0}
    try:
        t = yf.Ticker(ticker)
        counts = {k: 0 for k in RATING_WEIGHTS}
        consensus_score = None
        recommendation_key = None
        try:
            summary = t.recommendations_summary
            counts, consensus_score = _parse_recommendations(summary)
        except Exception:
            pass
        try:
            info = t.info or {}
            recommendation_key = info.get("recommendationKey")
        except Exception:
            info = {}

        targets = {}
        try:
            raw_targets = t.analyst_price_targets or {}
            if isinstance(raw_targets, dict):
                targets = {str(k): _num(v) for k, v in raw_targets.items()}
        except Exception:
            pass

        changes, bullish_30d, bearish_30d, target_changes_30d = [], 0, 0, 0
        try:
            changes, bullish_30d, bearish_30d, target_changes_30d = _parse_changes(t.upgrades_downgrades)
        except Exception:
            pass

        current = targets.get("current")
        mean = targets.get("mean")
        median = targets.get("median")
        low = targets.get("low")
        high = targets.get("high")
        upside = (mean / current - 1) if current and mean else None
        total_ratings = sum(counts.values())
        usable = 0
        if total_ratings:
            usable += 1
        if mean is not None:
            usable += 1
        if changes:
            usable += 1
        out.update({
            "analyst_recommendation": _rating_key(recommendation_key) or _rating_key(max(counts, key=counts.get)) if total_ratings else _rating_key(recommendation_key),
            "analyst_consensus_score": round(consensus_score, 1) if consensus_score is not None else None,
            "analyst_strong_buy": counts["strongbuy"],
            "analyst_buy": counts["buy"],
            "analyst_hold": counts["hold"],
            "analyst_sell": counts["sell"],
            "analyst_strong_sell": counts["strongsell"],
            "analyst_count": total_ratings or None,
            "analyst_target_current": current,
            "analyst_target_mean": mean,
            "analyst_target_median": median,
            "analyst_target_low": low,
            "analyst_target_high": high,
            "analyst_target_upside": upside,
            "analyst_changes_30d": len([x for x in changes if x.get("date")]),
            "analyst_bullish_changes_30d": bullish_30d,
            "analyst_bearish_changes_30d": bearish_30d,
            "analyst_target_changes_30d": target_changes_30d,
            "analyst_recent_changes": changes,
            "analyst_completeness": round(min(100.0, usable / 3 * 100), 1),
        })
    except Exception as exc:
        out["analyst_error"] = str(exc)[:160]
    return out


def _load_cache():
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def _save_cache(cache):
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=2, allow_nan=False), encoding="utf-8")


def download_analyst_data(tickers, workers=8, refresh_hours=CACHE_TTL_HOURS):
    cache = _load_cache()
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=refresh_hours)
    fresh, stale = {}, []
    for ticker in dict.fromkeys(tickers):
        item = cache.get(ticker)
        try:
            updated = datetime.fromisoformat(item.get("_cached_at", "")) if item else None
            if updated and updated.tzinfo is None:
                updated = updated.replace(tzinfo=timezone.utc)
            if item and updated and updated >= cutoff:
                fresh[ticker] = {k: v for k, v in item.items() if k != "_cached_at"}
            else:
                stale.append(ticker)
        except (TypeError, ValueError):
            stale.append(ticker)
    if stale:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_one, ticker): ticker for ticker in stale}
            for future in as_completed(futures):
                row = future.result()
                row["_cached_at"] = now.isoformat()
                cache[row["ticker"]] = row
                fresh[row["ticker"]] = {k: v for k, v in row.items() if k != "_cached_at"}
        _save_cache(cache)
    return fresh
