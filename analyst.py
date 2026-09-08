from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path

import pandas as pd
import yfinance as yf

CACHE_PATH = Path(__file__).resolve().parent / "data" / "analyst_cache.json"
CACHE_TTL_HOURS = 24
CACHE_VERSION = 9
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
    for name in (attribute, method):
        if not name:
            continue
        try:
            value = getattr(ticker, name, None)
            if callable(value):
                value = value()
            if isinstance(value, pd.DataFrame) and not value.empty:
                return value
        except Exception:
            continue
    return pd.DataFrame()


def _get_yahoo_dict(ticker, attribute, method=None):
    for name in (method, attribute):
        if not name:
            continue
        try:
            value = getattr(ticker, name, None)
            if callable(value):
                value = value()
            if isinstance(value, dict) and value:
                return value
        except Exception:
            continue
    return {}


def _first_num(mapping, keys):
    if not isinstance(mapping, dict):
        return None
    for key in keys:
        value = _num(mapping.get(key))
        if value is not None and value > 0:
            return value
    return None


def _target_from_row(row, keys=None):
    keys = keys or (
        "currentPriceTarget",
        "current_price_target",
        "priceTarget",
        "price_target",
        "targetPrice",
        "target_price",
        "newTarget",
        "new_target",
        "target",
        "toPrice",
        "to_price",
        "currentTarget",
        "current_target",
    )
    for key in keys:
        try:
            value = _num(row.get(key))
        except Exception:
            value = None
        if value is not None and value > 0:
            return value
    return None


def _parse_target_summary(targets, info):
    current = _first_num(targets, ("current", "currentPrice", "current_price"))
    low = _first_num(targets, ("low", "targetLow", "target_low"))
    high = _first_num(targets, ("high", "targetHigh", "target_high"))
    mean = _first_num(targets, ("mean", "average", "targetMean", "target_mean"))
    median = _first_num(targets, ("median", "targetMedian", "target_median"))

    # Yahoo also exposes the same consensus targets through quote/info on some
    # symbols. Use those only as fallbacks, never as replacements for a valid
    # analyst_price_targets response.
    current = current or _first_num(info, ("currentPrice", "regularMarketPrice"))
    low = low or _first_num(info, ("targetLowPrice",))
    high = high or _first_num(info, ("targetHighPrice",))
    mean = mean or _first_num(info, ("targetMeanPrice",))
    median = median or _first_num(info, ("targetMedianPrice",))
    return current, mean, median, low, high


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
        firm = _clean_text(row.get("firm")) or _clean_text(row.get("company"))
        to_grade = _clean_text(row.get("toGrade")) or _clean_text(row.get("to_grade"))
        from_grade = _clean_text(row.get("fromGrade")) or _clean_text(row.get("from_grade"))
        target = _target_from_row(row)
        prior_target = _target_from_row(row, (
            "priorPriceTarget", "prior_price_target", "previousPriceTarget", "previous_price_target"
        ))
        target_action = _clean_text(row.get("priceTargetAction")) or _clean_text(row.get("price_target_action"))
        action_l = (action or "").lower().replace(" ", "")
        target_action_l = (target_action or "").lower().replace(" ", "")

        if ts is not None and ts.to_pydatetime() >= cutoff:
            recent_count += 1
            if any(x in action_l for x in BULLISH_ACTIONS):
                bullish += 1
            if any(x in action_l for x in BEARISH_ACTIONS):
                bearish += 1
            if "target" in action_l or target_action:
                target_changes += 1

        item = {
            "date": ts.isoformat() if ts is not None else None,
            "firm": firm,
            "action": action,
            "from_grade": from_grade,
            "to_grade": to_grade,
            "target": target,
            "prior_target": prior_target,
            "target_action": target_action,
        }
        if len(changes) < 30:
            changes.append(item)

        # Only expose firm-level entries when Yahoo actually supplied a target.
        # This prevents the UI from pretending a rating change is a bank price target.
        if firm and firm not in seen and target is not None:
            seen.add(firm)
            firms.append({
                "firm": firm,
                "date": ts.isoformat() if ts is not None else None,
                "action": action,
                "from_grade": from_grade,
                "to_grade": to_grade,
                "target": target,
                "prior_target": prior_target,
                "target_action": target_action,
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
        yahoo = yf.Ticker(ticker)
        counts = {key: 0 for key in RATING_WEIGHTS}
        consensus = None
        recommendation_key = None
        info = {}

        # Recommendations. Yahoo has exposed both the summary and the full
        # recommendation table under different names across yfinance versions.
        for attribute, method in (
            ("recommendations_summary", "get_recommendations_summary"),
            ("recommendations", "get_recommendations"),
        ):
            if sum(counts.values()) > 0:
                break
            frame = _get_yahoo_frame(yahoo, attribute, method)
            if not frame.empty:
                counts, consensus = _parse_recommendations(frame)

        try:
            info = yahoo.info or {}
            recommendation_key = info.get("recommendationKey")
        except Exception:
            info = {}

        # IMPORTANT: explicitly call get_analyst_price_targets first. The
        # property is only a wrapper in current yfinance, but the method is the
        # documented analyst-price-target API and is less likely to be confused
        # with an empty cached property.
        targets = _get_yahoo_dict(yahoo, "analyst_price_targets", "get_analyst_price_targets")
        current, mean, median, low, high = _parse_target_summary(targets, info)

        # Yahoo's upgrades/downgrades feed can contain individual firm target
        # changes. It is the source used for bank/firm-level target history.
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
    cache = _load_cache()
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=refresh_hours)
    retry_cutoff = now - timedelta(minutes=ANALYST_RETRY_MINUTES)
    result = {}
    stale = []

    for ticker in dict.fromkeys(tickers):
        item = cache.get(ticker) or {}
        updated = _cached_timestamp(item)
        payload = {k: v for k, v in item.items() if not k.startswith("_")}
        good = _has_analyst_data(payload)

        if item.get("_cache_version") == CACHE_VERSION and updated and updated >= cutoff and good:
            result[ticker] = payload
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
                    cache[ticker] = row
                    result[ticker] = {k: v for k, v in row.items() if not k.startswith("_")}
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
