from __future__ import annotations

import pandas as pd

from config import ALERT_THRESHOLD, STRONG_ALERT_THRESHOLD, EXCEPTIONAL_ALERT_THRESHOLD, WATCH_THRESHOLD, DEFAULT_START, MIN_AVG_DOLLAR_VOLUME, MIN_PRICE, REBOUND_WEIGHTS, QUALITY_WEIGHTS, CYCLICAL_WEIGHTS
from data import download_benchmarks, download_ohlcv
from fundamentals import download_fundamentals
from indicators import add_indicators
from model import score_row
from universe import load_top_us_stocks

FEATURE_COLUMNS = ["rsi_7", "rsi_14", "rsi_21", "macd", "macd_signal", "macd_histogram", "macd_histogram_change", "atr_pct", "bollinger_pct", "bollinger_width", "return_1d", "return_3d", "return_5d", "return_10d", "return_20d", "distance_sma20", "distance_sma50", "distance_sma200", "distance_1m_high", "distance_3m_high", "distance_6m_high", "distance_52w_high", "distance_support_20d", "distance_support_60d", "distance_support_120d", "volume_ratio", "volume_ratio_5d", "volatility_20d", "z_score", "close_location", "relative_strength_5d", "relative_strength_20d"]
FUNDAMENTAL_COLUMNS = ["revenue", "revenue_growth", "eps", "eps_growth", "net_margin", "gross_margin", "fcf", "fcf_growth", "fcf_margin", "roe", "debt_equity", "cash", "pe", "forward_pe", "peg", "fundamental_score", "fundamental_completeness"]


def _signal_label(score: float, fundamental_score) -> str:
    if fundamental_score is None:
        return "DATA_INCOMPLETE"
    if score >= ALERT_THRESHOLD:
        return "ALERT"
    if score >= WATCH_THRESHOLD:
        return "WATCH"
    return "NO_SIGNAL"


def _alert_tier(score: float, signal: str) -> str:
    if signal != "ALERT":
        return ""
    if score >= EXCEPTIONAL_ALERT_THRESHOLD:
        return "EXCEPTIONAL"
    if score >= STRONG_ALERT_THRESHOLD:
        return "STRONG"
    return "EARLY"


def _combined_score(trader_similarity, technical_score, fundamental_score):
    parts = []
    if pd.notna(trader_similarity):
        parts.append((float(trader_similarity), 0.45))
    if pd.notna(technical_score):
        parts.append((float(technical_score), 0.25))
    if pd.notna(fundamental_score):
        parts.append((float(fundamental_score), 0.30))
    if not parts:
        return None
    total_weight = sum(weight for _, weight in parts)
    return sum(value * weight for value, weight in parts) / total_weight


def scan(limit: int = 1000, top_n: int = 25) -> pd.DataFrame:
    universe = load_top_us_stocks(limit)
    company_map = universe.set_index("ticker")["company_name"].to_dict()
    tickers = universe["ticker"].tolist()
    benchmarks = download_benchmarks(DEFAULT_START)
    spy = benchmarks.get("SPY")
    benchmark_close = spy["Close"] if spy is not None and "Close" in spy else None
    market = download_ohlcv(tickers, DEFAULT_START)
    fundamentals = download_fundamentals(tickers)
    rows = []
    for ticker, prices in market.items():
        if prices.empty or "Close" not in prices.columns:
            continue
        features = add_indicators(prices, benchmark_close)
        row = features.iloc[-1].copy()
        avg_dollar_volume = (features["Close"] * features["Volume"]).rolling(20).mean().iloc[-1]
        if row.get("Close", 0) < MIN_PRICE or (pd.notna(avg_dollar_volume) and avg_dollar_volume < MIN_AVG_DOLLAR_VOLUME):
            continue
        scores = score_row(row, REBOUND_WEIGHTS, QUALITY_WEIGHTS, CYCLICAL_WEIGHTS)
        f = fundamentals.get(ticker, {})
        technical_score = scores.get("technical_opportunity_score")
        trader_similarity = scores.get("trader_similarity_score")
        fundamental_score = f.get("fundamental_score")
        combined_score = _combined_score(trader_similarity, technical_score, fundamental_score)
        if combined_score is None:
            continue
        signal = _signal_label(combined_score, fundamental_score)
        result = {
            "ticker": ticker,
            "company_name": company_map.get(ticker, ticker),
            "price": float(row["Close"]),
            "avg_dollar_volume_20d": float(avg_dollar_volume) if pd.notna(avg_dollar_volume) else None,
            "technical_score": round(float(technical_score), 1) if pd.notna(technical_score) else None,
            "trader_similarity_score": round(float(trader_similarity), 1) if pd.notna(trader_similarity) else None,
            "fundamental_score": round(float(fundamental_score), 1) if pd.notna(fundamental_score) else None,
            "fundamental_completeness": f.get("fundamental_completeness"),
            "overall_score": round(float(combined_score), 1),
            "signal": signal,
            "alert_tier": _alert_tier(float(combined_score), signal),
        }
        result.update({k: float(v) if isinstance(v, (int, float)) else v for k, v in scores.items() if k not in {"overall_score", "trader_similarity_score"}})
        result.update({k: float(row[k]) if pd.notna(row[k]) else None for k in FEATURE_COLUMNS if k in row})
        result.update({k: f.get(k) for k in FUNDAMENTAL_COLUMNS})
        rows.append(result)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(["overall_score", "trader_similarity_score", "reversal_trigger"], ascending=[False, False, False]).head(top_n).reset_index(drop=True)


if __name__ == "__main__":
    print(scan().to_string(index=False))
