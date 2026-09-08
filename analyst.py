from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path
import time

import pandas as pd
import yfinance as yf

CACHE_PATH = Path(__file__).resolve().parent / "data" / "analyst_cache.json"
CACHE_TTL_HOURS = 24
CACHE_VERSION = 8
ANALYST_RETRY_MINUTES = 60
RATING_WEIGHTS = {
    "strongbuy": 100.0,
    "buy": 75.0,
    "hold": 50.0,
    "sell": 25.0,
    "strongsell": 0.0,
}
RATING_ALIASES = {
    "strongbuy": ["strongbuy", "strong_buy", "strongBuy"],
    "buy": ["buy"],
    "hold": ["hold"],
    "sell": ["sell"],
    "strongsell": ["strongsell", "strong_sell", "strongSell"],
}
BULLISH_ACTIONS = {"up", "upgrade", "upgraded", "init", "initiated"}
BEARISH_ACTIONS = {"down", "downgrade", "downgraded"}


def _num(value):
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def _clean_text(value):
    if value is None:
        return None
    text = str(value).strip()
    return text if text and text.lower() != "nan" else None


def _rating_key(value):
    if value is None:
        return None
    normalized = str(value).strip().lower().replace(" ", "").replace("_", "").replace("-", "")
    return {
        "strongbuy": "STRONG BUY",
        "buy": "BUY",
        "hold": "HOLD",
        "sell": "SELL",
        "strongsell": "STRONG SELL",
    }.get(normalized, str(value).strip().upper())


def _consensus_score(counts):
    total = sum(float(counts.get(key, 0) or 0) for key in RATING_WEIGHTS)
    if total <= 0:
        return None
    return sum(float(counts.get(key, 0) or 0) * weight for key, weight in RATING_WEIGHTS.items()) / total


def _parse_recommendations(df):
    counts = {key: 0 for key in RATING_WEIGHTS}
    if not isinstance(df, pd.DataFrame) or df.empty:
        return counts, None

    row = df.iloc[0]
    for key in counts:
        for alias in RATING_ALIASES[key]:
            if alias in row.index:
                counts[key] = int(_num(row[alias]) or 0)
                break
    return counts, _consensus_score(counts)


def _get_yahoo_frame(ticker, attribute, method=None):
    """Read a yfinance analyst frame with a method fallback for API changes."""
    try:
        value = getattr(ticker, attribute, None)
        if callable(value):
            value = value()
        if isinstance(value, pd.DataFrame) and not value.empty:
            return value
    except Exception:
        pass

    if method:
        try:
            fn = getattr(ticker, method, None)
            if callable(fn):
                value = fn()
                if isinstance(value, pd.DataFrame) and not value.empty:
                    return value
        except Exception:
            pass
    return pd.DataFrame()


def _get_yahoo_dict(ticker, attribute, method=None):
    try:
        value = getattr(ticker, attribute, None)
        if callable(value):
            value = value()
        if isinstance(value, dict) and value:
            return value
    except Exception:
        pass

    if method:
        try:
            fn = getattr(ticker, method, None)
            if callable(fn):
                value = fn()
                if isinstance(value, dict) and value:
                    return value
        except Exception:
            pass
    return {}


def _target_from_row(row):
    for key in (
        "currentPriceTarget",
        "priceTarget",
        "targetPrice",
        "newTarget",
        "target",
        "toPrice",
        "to_price",
        "currentTarget",
    ):
        value = _num(row.get(key))
        if value is not None and value > 0:
            return value
    return None


def _parse_changes(df):
    if not isinstance(df, pd.DataFrame) or df.empty:
        return [], 0, 0, 0, 0, []

    data = df.copy()
    if not isinstance(data.index, pd.DatetimeIndex):
        try:
            data.index = pd.to_datetime(data.index, utc=True)
        except Exception:
            pass

    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    changes = []
    firms = []
    seen = set()
    bullish = bearish = target_changes = recent_count = 0

    for idx, row in data.head(100).iterrows():
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
        target = _target_from_row(row)
        action_l = (action or "").lower().replace(" ", "")

        if ts is not None and ts.to_pydatetime() >= cutoff:
            recent_count += 1
            if any(x in action_l for x in BULLISH_ACTIONS):
                bullish += 1
            if any(x in action_l for x in BEARISH_ACTIONS):
                bearish += 1
            if "target" in action_l:
                target_changes += 1

        if len(changes) < 30:
            changes.append({
                "date": ts.isoformat() if ts is not None else None,
                "firm": firm,
                "action": action,
                "from_grade": from_grade,
                "to_grade": to_grade,
                "target": target,
            })

        if firm and firm not in seen:
            seen.add(firm)
            firms.append({
                "firm": firm,
                "date": ts.isoformat() if ts is not None else None,
                "action": action,
                "from_grade": from_grade,
                "to_grade": to_grade,
                "target": target,
            })

    return changes, recent_count, bullish, bearish, target_changes, firms[:30]


def _parse_news(items):
    out = []
    if not isinstance(items, list):
        return out
    for item in items[:10]:
        content = item.get("content", item) if isinstance(item, dict) else {}
        title = _clean_text(content.get("title"))
        if not title:
            continue
        provider = content.get("provider", {}) if isinstance(content, dict) else {}
        out.append({
            "title": title,
            "publisher": _clean_text(provider.get("displayName")) if isinstance(provider, dict) else None,
            "published": _clean_text(content.get("pubDate") or content.get("displayTime")),
        })
    return out[:5]


def _parse_earnings_history(df):
    if not isinstance(df, pd.DataFrame) or df.empty:
        return None, None
    data = df.copy().sort_index(ascending=False)
    try:
        idx = pd.Timestamp(data.index[0])
        if idx.tzinfo is None:
            idx = idx.tz_localize("UTC")
        idx = idx.tz_convert("UTC")
    except Exception:
        idx = None
    return idx.isoformat() if idx is not None else None, _num(data.iloc[0].get("surprisePercent"))


def _has_analyst_data(row):
    if not isinstance(row, dict):
        return False
    return any([
        row.get("analyst_consensus_score") is not None,
        row.get("analyst_target_mean") is not None,
        row.get("analyst_count") is not None and row.get("analyst_count", 0) > 0,
        any((row.get(key) or 0) > 0 for key in (
            "analyst_strong_buy", "analyst_buy", "analyst_hold", "analyst_sell", "analyst_strong_sell"
        )),
        (row.get("analyst_changes_30d") or 0) > 0,
    ])


def _usable_fields(row):
    return sum(bool(x) for x in (
        row.get("analyst_consensus_score") is not None,
        row.get("analyst_target_mean") is not None,
        row.get("analyst_count") is not None,
        bool(row.get("analyst_recent_changes")),
    ))


def _one(ticker):
    out = {"ticker": ticker, "analyst_completeness": 0.0, "recent_news": []}

    try:
        # yfinance's Ticker object is deliberately kept per stock. This avoids
        # sharing mutable provider state between worker threads.
        yahoo = yf.Ticker(ticker)

        counts = {key: 0 for key in RATING_WEIGHTS}
        consensus = None
        recommendation_key = None
        info = {}

        # Yahoo has exposed both recommendations_summary and recommendations
        # over time. Try both, plus the explicit get_recommendations method.
        for attribute, method in (
            ("recommendations_summary", "get_recommendations"),
            ("recommendations", "get_recommendations"),
        ):
            if sum(counts.values()) > 0:
                break
            frame = _get_yahoo_frame(yahoo, attribute, method)
            if not frame.empty:
                counts, consensus = _parse_recommendations(frame)

        # RecommendationKey/numberOfAnalystOpinions are useful fallbacks when
        # Yahoo's recommendation table is temporarily incomplete.
        try:
            info = yahoo.info or {}
            recommendation_key = info.get("recommendationKey")
        except Exception:
            info = {}

        targets = _get_yahoo_dict(yahoo, "analyst_price_targets", "get_analyst_price_targets")

        current = (
            _num(targets.get("current"))
            or _num(info.get("currentPrice"))
            or _num(info.get("regularMarketPrice"))
        )
        mean = _num(targets.get("mean")) or _num(info.get("targetMeanPrice"))
        median = _num(targets.get("median")) or _num(info.get("targetMedianPrice"))
        low = _num(targets.get("low")) or _num(info.get("targetLowPrice"))
        high = _num(targets.get("high")) or _num(info.get("targetHighPrice"))

        # Analyst history contains the individual firms and their target/rating
        # changes. Keep it because the detail page uses these firm-level events.
        changes = []
        recent_count = bullish = bearish = target_changes = 0
        firm_targets = []
        upgrades = _get_yahoo_frame(yahoo, "upgrades_downgrades", "get_upgrades_downgrades")
        if not upgrades.empty:
            changes, recent_count, bullish, bearish, target_changes, firm_targets = _parse_changes(upgrades)

        earnings_last_date = earnings_surprise = None
        earnings_history = _get_yahoo_frame(yahoo, "earnings_history", "get_earnings_history")
        if not earnings_history.empty:
            earnings_last_date, earnings_surprise = _parse_earnings_history(earnings_history)

        next_earnings = None
        try:
            dates = yahoo.get_earnings_dates(limit=8)
            if isinstance(dates, pd.DataFrame) and not dates.empty:
                now = pd.Timestamp.now(tz="UTC")
                for idx in dates.index:
                    ts = pd.Timestamp(idx)
                    if ts.tzinfo is None:
                        ts = ts.tz_localize("UTC")
                    ts = ts.tz_convert("UTC")
                    if ts >= now:
                        next_earnings = ts.isoformat()
                        break
        except Exception:
            pass

        recent_news = []
        try:
            recent_news = _parse_news(yahoo.get_news(count=10, tab="news"))
        except Exception:
            pass

        upside = (mean / current - 1) if current and mean else None
        total_ratings = sum(counts.values())
        info_count = _num(info.get("numberOfAnalystOpinions"))
        analyst_count = total_ratings or (int(info_count) if info_count else None)

        if consensus is None and recommendation_key:
            normalized = str(recommendation_key).replace(" ", "").replace("_", "").lower()
            consensus = RATING_WEIGHTS.get(normalized)

        fallback_rating = _rating_key(recommendation_key)
        if not fallback_rating and total_ratings:
            fallback_rating = _rating_key(max(counts, key=counts.get))

        usable = _usable_fields({
            "analyst_consensus_score": consensus,
            "analyst_target_mean": mean,
            "analyst_count": analyst_count,
            "analyst_recent_changes": changes,
        })

        out.update({
            "ticker": ticker,
            "analyst_recommendation": fallback_rating,
            "analyst_consensus_score": round(consensus, 1) if consensus is not None else None,
            "analyst_strong_buy": counts["strongbuy"],
            "analyst_buy": counts["buy"],
            "analyst_hold": counts["hold"],
            "analyst_sell": counts["sell"],
            "analyst_strong_sell": counts["strongsell"],
            "analyst_count": analyst_count,
            "analyst_target_current": current,
            "analyst_target_mean": mean,
            "analyst_target_median": median,
            "analyst_target_low": low,
            "analyst_target_high": high,
            "analyst_target_upside": upside,
            "analyst_changes_30d": recent_count,
            "analyst_bullish_changes_30d": bullish,
            "analyst_bearish_changes_30d": bearish,
            "analyst_target_changes_30d": target_changes,
            "analyst_recent_changes": changes,
            "analyst_firm_targets": firm_targets,
            "analyst_completeness": round(min(100.0, usable / 4 * 100), 1),
            "analyst_cache_stale": False,
            "analyst_refresh_failed": False,
            "analyst_error": None,
            "last_earnings_date": earnings_last_date,
            "last_earnings_surprise_pct": earnings_surprise,
            "next_earnings_date": next_earnings,
            "recent_news": recent_news,
            "analyst_source": "Yahoo Finance / yfinance",
        })
    except Exception as exc:
        out["analyst_error"] = str(exc)[:180]

    return out


def _load_cache():
    try:
        data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def _save_cache(cache):
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=2, allow_nan=False), encoding="utf-8")


def _cached_timestamp(item):
    try:
        updated = datetime.fromisoformat(item.get("_cached_at", "")) if item else None
        if updated and updated.tzinfo is None:
            updated = updated.replace(tzinfo=timezone.utc)
        return updated
    except (TypeError, ValueError):
        return None


def download_analyst_data(tickers, workers=4, refresh_hours=CACHE_TTL_HOURS):
    """Fetch analyst data from Yahoo Finance and cache successful results.

    Yahoo remains the single source of truth for analyst data. The cache is
    intentionally conservative: a failed/empty refresh never replaces a good
    previous result.
    """
    cache = _load_cache()
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=refresh_hours)
    retry_cutoff = now - timedelta(minutes=ANALYST_RETRY_MINUTES)
    fresh = {}
    stale = []

    for ticker in dict.fromkeys(tickers):
        item = cache.get(ticker) or {}
        updated = _cached_timestamp(item)
        payload = {key: value for key, value in item.items() if not key.startswith("_")}
        good = _has_analyst_data(payload)

        if (
            item.get("_cache_version") == CACHE_VERSION
            and updated
            and updated >= cutoff
            and good
        ):
            fresh[ticker] = payload
            continue

        last_attempt = _cached_timestamp({"_cached_at": item.get("_last_attempt_at")})
        if (
            item.get("_cache_version") == CACHE_VERSION
            and item.get("_refresh_failed")
            and last_attempt
            and last_attempt >= retry_cutoff
        ):
            if good:
                payload["analyst_cache_stale"] = True
                payload["analyst_refresh_failed"] = True
                fresh[ticker] = payload
            continue

        stale.append(ticker)

    if stale:
        # Four workers is fast enough while avoiding the burst of simultaneous
        # Yahoo requests that previously caused incomplete responses.
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
                        "recent_news": [],
                        "analyst_error": str(exc)[:180],
                    }

                if _has_analyst_data(row):
                    row["analyst_cache_stale"] = False
                    row["analyst_refresh_failed"] = False
                    row["_cached_at"] = now.isoformat()
                    row["_last_attempt_at"] = now.isoformat()
                    row["_cache_version"] = CACHE_VERSION
                    row["_refresh_failed"] = False
                    cache[ticker] = row
                    fresh[ticker] = {key: value for key, value in row.items() if not key.startswith("_")}
                elif _has_analyst_data(old_payload):
                    old_payload["analyst_cache_stale"] = True
                    old_payload["analyst_refresh_failed"] = True
                    old_payload["analyst_error"] = row.get("analyst_error") or "Yahoo Finance returned incomplete analyst data"
                    cache[ticker] = {
                        **old_payload,
                        "_cached_at": old.get("_cached_at"),
                        "_last_attempt_at": now.isoformat(),
                        "_cache_version": CACHE_VERSION,
                        "_refresh_failed": True,
                    }
                    fresh[ticker] = old_payload
                else:
                    cache[ticker] = {
                        **row,
                        "_cached_at": None,
                        "_last_attempt_at": now.isoformat(),
                        "_cache_version": CACHE_VERSION,
                        "_refresh_failed": True,
                    }

        _save_cache(cache)

    # Small pause between batches keeps repeated scanner invocations from
    # immediately hammering Yahoo after a failed run.
    if stale:
        time.sleep(0.1)

    return fresh
