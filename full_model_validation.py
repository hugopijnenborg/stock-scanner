"""Walk-forward validation of the CURRENT live methodology.

Technical (dislocation x confirmation, 55%) + Fundamentals (30%) +
Valuation (10%) + Analyst direction (5%) + earnings adjustment + regime
multiplier -- exactly model.assemble_new_score(), called directly here,
so this validation cannot drift from what the live scanner actually
computes. Only the INPUTS differ: point-in-time-approximated
fundamentals/analyst data is built per evaluation day instead of using
today's live snapshot.

Replaces walk_forward_validation.py, which validated the old trader-
similarity + technical (70/30) formula -- not the live formula for a
while now. That script is left in place for the historical record; this
one is what the validation page should read going forward.

Honest limitations, read before trusting the output:
  - Point-in-time fundamentals: quarterly financials are assumed public
    45 days after period end (yfinance gives no real filing date).
  - Market cap (for EV/Sales, loss-making companies only) uses CURRENT
    shares outstanding x historical price. Share count drifts over time
    (buybacks/issuance), so this is an approximation, not exact --
    usually small for large-caps over a few years, but not zero.
  - Forward P/E and PEG cannot be reconstructed historically (need
    forward estimates that don't exist retroactively). Trailing P/E
    (from point-in-time TTM EPS) is used in forward_pe's place, and PEG
    is trailing-P/E divided by trailing EPS growth -- both proxies for
    what the live scanner uses when real forward data is available.
  - Sector-relative valuation (pe_vs_sector) is NOT computed here -- it
    would need the whole universe's point-in-time P/E on every
    evaluation day, multiplying the cost of this script substantially.
    Absolute P/E thresholds are used instead of sector-relative ones.
  - Analyst direction and earnings surprises ARE reliably point-in-time:
    yfinance gives dated historical logs for both, so those two
    components carry no timing risk beyond the source data's own
    quality (which has its own known gaps, see analyst.py).
  - No trader-pattern component -- the live formula doesn't have one
    anymore either, so there's nothing missing here that's present live.

Usage:
    python full_model_validation.py --start 2022-01-01 --step 5
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

from config import DEFAULT_START
from data import download_benchmarks, download_ohlcv
from indicators import add_indicators
from model import assemble_new_score
from universe import load_top_us_stocks
from walk_forward_validation import (
    _naive_day_index, forward_metrics, _summary_horizon, _band_key,
    _event_summary, build_trade_events, THRESHOLDS, SCORE_BANDS,
    TRADE_EVENT_COOLDOWN_DAYS, MIN_RANK_N,
)

EVAL_START = pd.Timestamp("2022-01-01")
PIT_CACHE_DIR = Path("data/full_model_pit_cache")
PIT_CACHE_DIR.mkdir(parents=True, exist_ok=True)
FUNDAMENTALS_LAG_DAYS = 45


def fetch_pit_raw(ticker: str) -> dict:
    """Raw historical data fetched ONCE per ticker, then sliced per
    evaluation day below -- not re-fetched per day."""
    cache_path = PIT_CACHE_DIR / f"{ticker}.pkl"
    if cache_path.exists():
        return pd.read_pickle(cache_path)
    t = yf.Ticker(ticker)
    data: dict = {}
    try:
        data["quarterly_financials"] = t.quarterly_financials
        data["quarterly_balance_sheet"] = t.quarterly_balance_sheet
        data["quarterly_cashflow"] = t.quarterly_cashflow
    except Exception:
        data["quarterly_financials"] = data["quarterly_balance_sheet"] = data["quarterly_cashflow"] = None
    try:
        data["earnings_dates"] = t.get_earnings_dates(limit=60)
    except Exception:
        data["earnings_dates"] = None
    try:
        data["upgrades_downgrades"] = t.get_upgrades_downgrades()
    except Exception:
        data["upgrades_downgrades"] = None
    try:
        info = t.info
        data["shares_outstanding"] = info.get("sharesOutstanding")
        data["sector"] = info.get("sector")
    except Exception:
        data["shares_outstanding"] = None
        data["sector"] = None
    pd.to_pickle(data, cache_path)
    time.sleep(0.2)
    return data


def _cols_before(df, cutoff):
    if df is None or df.empty:
        return []
    tz = df.columns.tz if hasattr(df.columns, "tz") else None
    cutoff_cmp = cutoff.tz_localize(None) if tz is None else cutoff
    cols = [c for c in df.columns if (pd.Timestamp(c).tz_localize(None) if tz is None else pd.Timestamp(c)) < cutoff_cmp]
    return sorted(cols, reverse=True)


def build_fund_dict(pit: dict, date: pd.Timestamp, price: float | None) -> dict:
    """Point-in-time fundamentals dict with the exact keys
    model.fundamentals_score_v2() / valuation_score_v2() expect."""
    cutoff = date - pd.Timedelta(days=FUNDAMENTALS_LAG_DAYS)
    qf, qcf, qbs = pit.get("quarterly_financials"), pit.get("quarterly_cashflow"), pit.get("quarterly_balance_sheet")

    revenue_growth = eps_growth = net_margin = gross_margin = eps = None
    fcols = _cols_before(qf, cutoff)
    if qf is not None and len(fcols) >= 1:
        revenue = qf.loc["Total Revenue", fcols[0]] if "Total Revenue" in qf.index else None
        net_income = qf.loc["Net Income", fcols[0]] if "Net Income" in qf.index else None
        gross_profit = qf.loc["Gross Profit", fcols[0]] if "Gross Profit" in qf.index else None
        if pd.notna(revenue) and revenue:
            if pd.notna(net_income):
                net_margin = float(net_income / revenue)
            if pd.notna(gross_profit):
                gross_margin = float(gross_profit / revenue)
        if len(fcols) >= 5 and "Total Revenue" in qf.index:
            rev_prior = qf.loc["Total Revenue", fcols[4]]
            if pd.notna(revenue) and pd.notna(rev_prior) and rev_prior:
                revenue_growth = float(revenue / rev_prior - 1)
        if "Diluted EPS" in qf.index:
            eps_series = qf.loc["Diluted EPS", fcols[:4]].dropna()
            if len(eps_series):
                eps = float(eps_series.iloc[0])
            if len(fcols) >= 5:
                eps_now = qf.loc["Diluted EPS", fcols[0]] if "Diluted EPS" in qf.index else None
                eps_prior = qf.loc["Diluted EPS", fcols[4]] if "Diluted EPS" in qf.index else None
                if pd.notna(eps_now) and pd.notna(eps_prior) and eps_prior:
                    eps_growth = float(eps_now / eps_prior - 1)

    fcf = fcf_margin = None
    ccols = _cols_before(qcf, cutoff)
    if qcf is not None and ccols:
        if "Free Cash Flow" in qcf.index:
            v = qcf.loc["Free Cash Flow", ccols[0]]
            fcf = float(v) if pd.notna(v) else None
        if fcf is not None and qf is not None and fcols:
            revenue = qf.loc["Total Revenue", fcols[0]] if "Total Revenue" in qf.index else None
            if pd.notna(revenue) and revenue:
                fcf_margin = float(fcf / revenue)

    roe = debt_equity = debt = None
    bcols = _cols_before(qbs, cutoff)
    if qbs is not None and bcols:
        equity = qbs.loc["Stockholders Equity", bcols[0]] if "Stockholders Equity" in qbs.index else None
        debt_v = qbs.loc["Total Debt", bcols[0]] if "Total Debt" in qbs.index else None
        if pd.notna(debt_v):
            debt = float(debt_v)
        if pd.notna(equity) and equity and qf is not None and fcols:
            net_income = qf.loc["Net Income", fcols[0]] if "Net Income" in qf.index else None
            if pd.notna(net_income):
                roe = float(net_income / equity)
            if debt is not None:
                debt_equity = float(debt / equity)

    # Trailing P/E from point-in-time TTM EPS + the historical price on
    # this date. No forward estimates exist retroactively, so this
    # stands in for forward_pe (same fallback the live scanner uses when
    # forward_pe itself is unavailable).
    pe = peg = ev_sales = None
    if qf is not None and "Diluted EPS" in qf.index and len(fcols) >= 4 and price:
        ttm_eps = qf.loc["Diluted EPS", fcols[:4]].dropna()
        if len(ttm_eps) == 4:
            ttm = float(ttm_eps.sum())
            if ttm > 0:
                pe = price / ttm
                if eps_growth is not None and eps_growth > 0:
                    peg = pe / (eps_growth * 100)
    if (eps is None or eps <= 0) and price and pit.get("shares_outstanding") and qf is not None and fcols:
        revenue = qf.loc["Total Revenue", fcols[0]] if "Total Revenue" in qf.index else None
        if pd.notna(revenue) and revenue:
            market_cap = price * pit["shares_outstanding"]  # current share count, see module docstring
            enterprise_value = market_cap + (debt or 0)
            ev_sales = float(enterprise_value / (revenue * 4))  # quarterly revenue annualized

    return {
        "revenue_growth": revenue_growth, "eps_growth": eps_growth, "net_margin": net_margin,
        "gross_margin": gross_margin, "fcf": fcf, "fcf_margin": fcf_margin, "roe": roe,
        "debt_equity": debt_equity, "eps": eps, "pe": pe, "forward_pe": None,
        "pe_vs_sector": None, "peg": peg, "ev_sales": ev_sales,
    }


def build_analyst_dict(pit: dict, date: pd.Timestamp) -> dict:
    ud = pit.get("upgrades_downgrades")
    bullish = bearish = 0
    if ud is not None and not ud.empty and "Action" in ud.columns:
        idx = ud.index.tz_localize(None) if ud.index.tz is not None else ud.index
        window = ud[(idx < date) & (idx >= date - pd.Timedelta(days=30))]
        bullish = int((window["Action"].str.lower() == "up").sum())
        bearish = int((window["Action"].str.lower() == "down").sum())

    ed = pit.get("earnings_dates")
    last_surprise = last_earnings_date = next_earnings_date = None
    if ed is not None and not ed.empty:
        idx = ed.index.tz_localize(None) if ed.index.tz is not None else ed.index
        past = ed[idx < date]
        if "Surprise(%)" in ed.columns:
            past_s = past.dropna(subset=["Surprise(%)"])
            if not past_s.empty:
                last_surprise = float(past_s.iloc[0]["Surprise(%)"])
                last_earnings_date = past_s.index[0].isoformat() if hasattr(past_s.index[0], "isoformat") else str(past_s.index[0])
        future = ed[idx >= date]
        if not future.empty:
            next_earnings_date = future.index[-1].isoformat() if hasattr(future.index[-1], "isoformat") else str(future.index[-1])

    return {
        "analyst_bullish_changes_30d": bullish, "analyst_bearish_changes_30d": bearish,
        "last_earnings_surprise_pct": last_surprise, "last_earnings_date": last_earnings_date,
        "next_earnings_date": next_earnings_date,
    }


def run(output_csv: str = "full_model_validation.csv", summary_json: str = "public/data/full_model_validation.json",
        start: str = "2022-01-01", step: int = 5, limit: int = 1000) -> dict:
    eval_start = pd.Timestamp(start)
    universe = load_top_us_stocks(limit)
    tickers = universe["ticker"].tolist()
    print(f"Universe: {len(tickers)} tickers vanaf {start}")

    benchmarks = download_benchmarks(DEFAULT_START)
    spy = benchmarks.get("SPY")
    spy_close = pd.to_numeric(spy["Close"], errors="coerce").dropna() if spy is not None else None
    if spy_close is not None:
        spy_close.index = _naive_day_index(spy_close.index)
        spy_200dma = spy_close.rolling(200).mean()
        market_dates = _naive_day_index(spy_close.index)
    else:
        spy_200dma = None
        market_dates = None

    prices = download_ohlcv(tickers, DEFAULT_START)
    if market_dates is None:
        market_dates = _naive_day_index(sorted({idx for df in prices.values() for idx in df.index}))
    all_eval_dates = sorted(d for d in market_dates.unique() if d >= eval_start)
    eval_dates = all_eval_dates[::step] if step > 1 else all_eval_dates
    if not eval_dates:
        raise RuntimeError("No historical market dates available")
    print(f"{len(eval_dates)} evaluatiedagen (elke {step}e handelsdag vanaf {all_eval_dates[0].date()})")

    results = []
    for n, ticker in enumerate(tickers, 1):
        df = prices.get(ticker)
        if df is None or df.empty or "Close" not in df.columns:
            continue
        features = add_indicators(df, spy_close).copy()
        features.index = _naive_day_index(features.index)
        features = features[~features.index.duplicated(keep="last")]
        close = pd.to_numeric(features["Close"], errors="coerce").dropna()
        close.index = _naive_day_index(close.index)
        aligned = features.reindex(eval_dates, method="ffill")

        pit = fetch_pit_raw(ticker)

        for date, row in aligned.iterrows():
            date = pd.Timestamp(date)
            if row.isna().all() or date not in close.index and date > close.index.max():
                continue
            price = float(row.get("Close")) if pd.notna(row.get("Close")) else None
            row = row.copy()
            row["sector_relative_strength_20d"] = np.nan  # see module docstring: not computed historically

            fund = build_fund_dict(pit, date, price)
            analyst = build_analyst_dict(pit, date)
            bear_regime = False
            if spy_200dma is not None and date in spy_close.index and date in spy_200dma.index:
                sma = spy_200dma.loc[date]
                if pd.notna(sma):
                    bear_regime = float(spy_close.loc[date]) < float(sma)

            scores = assemble_new_score(row, fund, analyst, bear_regime)
            metrics = forward_metrics(close, date)
            results.append({
                "date": date.date().isoformat(), "ticker": ticker,
                "score": scores["overall_score_v2"],
                "technical_score": scores["technical_score_v2"],
                "fundamentals_score": scores["fundamentals_score_v2"],
                "valuation_score": scores["valuation_score_v2"],
                "analyst_score": scores["analyst_direction_score"],
                "confidence": scores["confidence"],
                "gate_excluded": scores["gate_excluded"],
                **metrics,
            })
        if n % 20 == 0:
            print(f"  {n}/{len(tickers)} tickers verwerkt, {len(results)} scenario's tot nu toe")

    df = pd.DataFrame(results)
    if df.empty:
        raise RuntimeError("Full-model validation produced no scenarios")
    df = df[~df["gate_excluded"]]  # the gate blocks ALERT live, so gated rows shouldn't count as 80+ opportunities
    df.to_csv(output_csv, index=False)

    events = build_trade_events(df)
    event_csv = Path(output_csv).with_name("full_model_validation_trade_events.csv")
    events.to_csv(event_csv, index=False)

    summary: dict[str, object] = {
        "method": (
            "Daily walk-forward validation of the full live methodology (Technical dislocation x confirmation 55%, "
            "Fundamentals 30%, Valuation 10%, Analyst direction 5%, earnings adjustment, regime multiplier), calling "
            "model.assemble_new_score() directly so this cannot drift from what the live scanner computes. Point-in-time "
            "fundamentals are approximated with a 45-day publication lag; forward P/E and sector-relative valuation are "
            "not reconstructable historically and are approximated or omitted (see the script's docstring for the full list "
            "of limitations). Rows the live fundamentals gate would exclude are dropped before scoring, same as live."
        ),
        "evaluation_start": eval_start.date().isoformat(),
        "step_days": step,
        "scenarios": int(len(df)),
        "alerts_80_plus": int((df["score"] >= 80).sum()),
        "trade_events_80_plus": int(len(events)),
        "unique_dates": int(df["date"].nunique()),
        "unique_tickers": int(df["ticker"].nunique()),
        "trade_event_rule": f"First 80+ signal per ticker, then no new event for {TRADE_EVENT_COOLDOWN_DAYS} calendar days.",
        "min_rank_n": MIN_RANK_N,
        "horizons": {"1d": "1 trading day", "5d": "5 trading days", "10d": "10 trading days", "20d": "20 trading days", "30d": "30 trading days", "60d": "60 calendar days"},
        "thresholds": {},
        "score_bands": {},
        "trade_events": {},
    }

    for threshold in THRESHOLDS:
        x = df[df["score"] >= threshold]
        threshold_summary: dict[str, object] = {"alerts": int(len(x))}
        for horizon in ["1d", "5d", "10d", "20d", "30d", "60d"]:
            stats = _summary_horizon(x, horizon)
            threshold_summary[f"n_{horizon}"] = stats["n"]
            threshold_summary[f"winrate_{horizon}"] = stats["winrate"]
            threshold_summary[f"avg_return_{horizon}"] = stats["avg_return"]
            threshold_summary[f"median_return_{horizon}"] = stats["median_return"]
        threshold_summary["avg_max_gain_60d"] = float(x["max_gain_60d"].mean()) if x["max_gain_60d"].notna().any() else None
        threshold_summary["avg_max_drawdown_60d"] = float(x["max_drawdown_60d"].mean()) if x["max_drawdown_60d"].notna().any() else None
        summary["thresholds"][str(threshold)] = threshold_summary

    for lo, hi in SCORE_BANDS:
        x = df[(df["score"] >= lo) & (df["score"] < hi)]
        key = _band_key(lo, hi)
        summary["score_bands"][key] = {"scenarios": int(len(x))}
        for horizon in ["5d", "20d", "30d", "60d"]:
            stats = _summary_horizon(x, horizon)
            summary["score_bands"][key][f"n_{horizon}"] = stats["n"]
            summary["score_bands"][key][f"winrate_{horizon}"] = stats["winrate"]
            summary["score_bands"][key][f"avg_return_{horizon}"] = stats["avg_return"]
            summary["score_bands"][key][f"median_return_{horizon}"] = stats["median_return"]

    for threshold in THRESHOLDS:
        x = events[events["entry_score"] >= threshold] if not events.empty else events
        summary["trade_events"][str(threshold)] = _event_summary(x, str(threshold))

    Path(summary_json).parent.mkdir(parents=True, exist_ok=True)
    Path(summary_json).write_text(json.dumps(summary, indent=2, allow_nan=False), encoding="utf-8")
    return summary


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2022-01-01")
    parser.add_argument("--step", type=int, default=5)
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--output", default="full_model_validation.csv")
    parser.add_argument("--summary", default="public/data/full_model_validation.json")
    args = parser.parse_args()
    result = run(output_csv=args.output, summary_json=args.summary, start=args.start, step=args.step, limit=args.limit)
    print(json.dumps(result, indent=2))
