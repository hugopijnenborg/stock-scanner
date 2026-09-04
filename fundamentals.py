from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path

import yfinance as yf

CACHE_PATH = Path(__file__).resolve().parent / "data" / "fundamentals_cache.json"
CACHE_TTL_HOURS = 24


def _num(value):
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (TypeError, ValueError):
        return None


def _latest(stmt, names):
    for name in names:
        if name in stmt.index:
            s = stmt.loc[name].dropna()
            if len(s):
                return _num(s.iloc[0])
    return None


def _growth(stmt, names):
    for name in names:
        if name in stmt.index:
            s = stmt.loc[name].dropna()
            if len(s) >= 2 and s.iloc[1] != 0:
                return _num((s.iloc[0] / s.iloc[1]) - 1)
    return None


def _score_high(value, zero, full):
    if value is None:
        return None
    if value <= zero:
        return 0.0
    if value >= full:
        return 100.0
    return 100.0 * (value - zero) / (full - zero)


def _score_low(value, full, zero):
    if value is None:
        return None
    if value <= full:
        return 100.0
    if value >= zero:
        return 0.0
    return 100.0 * (zero - value) / (zero - full)


def _one(ticker: str) -> dict:
    out = {"fundamental_score": None, "fundamental_completeness": 0.0}
    try:
        t = yf.Ticker(ticker)
        inc = t.income_stmt
        bal = t.balance_sheet
        cf = t.cashflow
        revenue = _latest(inc, ["Total Revenue", "Operating Revenue"])
        net_income = _latest(inc, ["Net Income", "Net Income Common Stockholders"])
        eps = _latest(inc, ["Diluted EPS", "Basic EPS"])
        gross_profit = _latest(inc, ["Gross Profit"])
        equity = _latest(bal, ["Stockholders Equity", "Common Stock Equity", "Total Equity Gross Minority Interest"])
        debt = _latest(bal, ["Total Debt", "Long Term Debt And Capital Lease Obligation"])
        cash = _latest(bal, ["Cash Cash Equivalents And Short Term Investments", "Cash And Cash Equivalents"])
        fcf = _latest(cf, ["Free Cash Flow"])
        if fcf is None:
            op_cf = _latest(cf, ["Operating Cash Flow", "Total Cash From Operating Activities"])
            capex = _latest(cf, ["Capital Expenditure", "Capital Expenditure Reported"])
            if op_cf is not None and capex is not None:
                fcf = op_cf + capex if capex < 0 else op_cf - capex

        revenue_growth = _growth(inc, ["Total Revenue", "Operating Revenue"])
        eps_growth = _growth(inc, ["Diluted EPS", "Basic EPS"])
        fcf_growth = _growth(cf, ["Free Cash Flow"])
        net_margin = net_income / revenue if revenue else None
        gross_margin = gross_profit / revenue if revenue else None
        roe = net_income / equity if equity else None
        debt_equity = debt / equity if equity else None
        fcf_margin = fcf / revenue if fcf is not None and revenue else None

        try:
            info = t.info
        except Exception:
            info = {}
        pe = _num(info.get("trailingPE"))
        forward_pe = _num(info.get("forwardPE"))
        peg = _num(info.get("pegRatio"))
        market_cap = _num(info.get("marketCap"))
        sector = info.get("sector") or None

        out.update({
            "revenue": revenue, "revenue_growth": revenue_growth, "eps": eps,
            "eps_growth": eps_growth, "net_margin": net_margin, "gross_margin": gross_margin,
            "fcf": fcf, "fcf_growth": fcf_growth, "fcf_margin": fcf_margin, "roe": roe,
            "debt_equity": debt_equity, "cash": cash, "pe": pe,
            "forward_pe": forward_pe, "peg": peg, "market_cap": market_cap,
            "sector": sector,
        })

        components = {
            "revenue_growth": _score_high(revenue_growth, -0.05, 0.30),
            "eps_growth": _score_high(eps_growth, -0.10, 0.30),
            "net_margin": _score_high(net_margin, 0.0, 0.25),
            "fcf_margin": _score_high(fcf_margin, -0.05, 0.20),
            "fcf_growth": _score_high(fcf_growth, -0.20, 0.30),
            "roe": _score_high(roe, 0.0, 0.30),
            "debt_equity": _score_low(debt_equity, 0.25, 2.0),
            "eps_positive": 100.0 if eps is not None and eps > 0 else (0.0 if eps is not None else None),
            "pe": _score_low(pe, 15.0, 60.0),
            "peg": _score_low(peg, 1.0, 3.0),
        }
        weights = {
            "revenue_growth": 0.16, "eps_growth": 0.14, "net_margin": 0.12,
            "fcf_margin": 0.12, "fcf_growth": 0.08, "roe": 0.10,
            "debt_equity": 0.08, "eps_positive": 0.06, "pe": 0.08, "peg": 0.06,
        }
        usable = [(k, w) for k, w in weights.items() if components.get(k) is not None]
        total_weight = sum(w for _, w in usable)
        out["fundamental_completeness"] = round(100.0 * total_weight / sum(weights.values()), 1)
        out["fundamental_score"] = round(sum(components[k] * w for k, w in usable) / total_weight, 1) if total_weight else None
    except Exception as exc:
        out["fundamental_error"] = str(exc)[:160]
    return {"ticker": ticker, **out}


def _apply_sector_relative_valuation(rows: dict[str, dict]) -> dict[str, dict]:
    by_sector: dict[str, list[dict]] = {}
    for row in rows.values():
        sector = row.get("sector")
        if sector:
            by_sector.setdefault(sector, []).append(row)

    for row in rows.values():
        sector = row.get("sector")
        peers = by_sector.get(sector, []) if sector else []
        if len(peers) < 4:
            continue
        for field in ["pe", "forward_pe", "peg"]:
            values = [float(p[field]) for p in peers if p.get(field) is not None and float(p[field]) > 0]
            if not values or row.get(field) is None or float(row[field]) <= 0:
                continue
            values = sorted(values)
            median = values[len(values) // 2] if len(values) % 2 else (values[len(values)//2 - 1] + values[len(values)//2]) / 2
            relative = float(row[field]) / median
            row[f"sector_median_{field}"] = median
            row[f"{field}_vs_sector"] = relative

        replacements = {}
        if row.get("pe_vs_sector") is not None:
            replacements["pe"] = _score_low(row["pe_vs_sector"], 0.75, 1.75)
        if row.get("peg_vs_sector") is not None:
            replacements["peg"] = _score_low(row["peg_vs_sector"], 0.75, 1.75)
        if replacements:
            weights = {
                "revenue_growth": 0.16, "eps_growth": 0.14, "net_margin": 0.12,
                "fcf_margin": 0.12, "fcf_growth": 0.08, "roe": 0.10,
                "debt_equity": 0.08, "eps_positive": 0.06, "pe": 0.08, "peg": 0.06,
            }
            inc = {
                "revenue_growth": _score_high(row.get("revenue_growth"), -0.05, 0.30),
                "eps_growth": _score_high(row.get("eps_growth"), -0.10, 0.30),
                "net_margin": _score_high(row.get("net_margin"), 0.0, 0.25),
                "fcf_margin": _score_high(row.get("fcf_margin"), -0.05, 0.20),
                "fcf_growth": _score_high(row.get("fcf_growth"), -0.20, 0.30),
                "roe": _score_high(row.get("roe"), 0.0, 0.30),
                "debt_equity": _score_low(row.get("debt_equity"), 0.25, 2.0),
                "eps_positive": 100.0 if row.get("eps") is not None and row["eps"] > 0 else (0.0 if row.get("eps") is not None else None),
                "pe": replacements.get("pe", _score_low(row.get("pe"), 15.0, 60.0)),
                "peg": replacements.get("peg", _score_low(row.get("peg"), 1.0, 3.0)),
            }
            usable = [(k, w) for k, w in weights.items() if inc.get(k) is not None]
            total = sum(w for _, w in usable)
            if total:
                row["fundamental_score"] = round(sum(inc[k] * w for k, w in usable) / total, 1)
    return rows


def _load_cache() -> dict[str, dict]:
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def _save_cache(cache: dict[str, dict]) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=2, allow_nan=False), encoding="utf-8")


def download_fundamentals(tickers: list[str], workers: int = 16, refresh_hours: int = CACHE_TTL_HOURS) -> dict[str, dict]:
    """Return fundamentals from a persistent cache and refresh stale symbols."""
    cache = _load_cache()
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=refresh_hours)
    fresh = {}
    stale = []

    for ticker in dict.fromkeys(tickers):
        item = cache.get(ticker)
        if not item:
            stale.append(ticker)
            continue
        try:
            updated = datetime.fromisoformat(item.get("_cached_at", ""))
            if updated.tzinfo is None:
                updated = updated.replace(tzinfo=timezone.utc)
            if updated >= cutoff:
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

    fresh = _apply_sector_relative_valuation(fresh)
    return fresh
