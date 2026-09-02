from __future__ import annotations

from datetime import datetime, timedelta, timezone
import numpy as np
import pandas as pd

from config import ALERT_THRESHOLD, STRONG_ALERT_THRESHOLD, EXCEPTIONAL_ALERT_THRESHOLD, WATCH_THRESHOLD, MIN_AVG_DOLLAR_VOLUME, MIN_PRICE, REBOUND_WEIGHTS, QUALITY_WEIGHTS, CYCLICAL_WEIGHTS
from data import download_benchmarks, download_ohlcv, download_intraday, download_intraday_benchmarks
from fundamentals import download_fundamentals
from indicators import add_indicators
from model import score_row
from universe import load_top_us_stocks

FEATURE_COLUMNS = ["rsi_7", "rsi_14", "rsi_21", "macd", "macd_signal", "macd_histogram", "macd_histogram_change", "atr_pct", "bollinger_pct", "bollinger_width", "return_1d", "return_3d", "return_5d", "return_10d", "return_20d", "distance_sma20", "distance_sma50", "distance_sma200", "distance_1m_high", "distance_3m_high", "distance_6m_high", "distance_52w_high", "distance_support_20d", "distance_support_60d", "distance_support_120d", "volume_ratio", "volume_ratio_5d", "volatility_20d", "z_score", "close_location", "relative_strength_5d", "relative_strength_20d"]
FUNDAMENTAL_COLUMNS = ["revenue", "revenue_growth", "eps", "eps_growth", "net_margin", "gross_margin", "fcf", "fcf_growth", "fcf_margin", "roe", "debt_equity", "cash", "pe", "forward_pe", "peg", "fundamental_score", "fundamental_completeness"]
LIVE_HISTORY_DAYS = 450


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


def _intraday_confirmation(intraday: pd.DataFrame, benchmark: pd.DataFrame | None = None) -> dict[str, float | None]:
    """Turn recent 15-minute bars into a small live confirmation signal.

    This does not replace daily indicators. It captures what changed during the
    current session so a 30-minute scan is genuinely different from yesterday's
    close-based calculation.
    """
    if intraday is None or intraday.empty or "Close" not in intraday.columns:
        return {"intraday_score": None, "intraday_return_1h": None, "intraday_return_session": None, "intraday_volume_ratio": None, "intraday_vwap_distance": None}
    d = intraday.dropna(subset=["Close"]).copy().sort_index()
    if len(d) < 8:
        return {"intraday_score": None, "intraday_return_1h": None, "intraday_return_session": None, "intraday_volume_ratio": None, "intraday_vwap_distance": None}
    close = pd.to_numeric(d["Close"], errors="coerce")
    volume = pd.to_numeric(d.get("Volume", pd.Series(index=d.index, dtype=float)), errors="coerce").fillna(0)
    last = float(close.iloc[-1])
    one_hour = float(close.iloc[-1] / close.iloc[-5] - 1) if len(close) >= 5 and close.iloc[-5] else 0.0
    # Use the latest trading date in the downloaded window as today's session.
    latest_date = d.index[-1].date()
    session = d[d.index.date == latest_date]
    session_close = pd.to_numeric(session["Close"], errors="coerce").dropna()
    session_open = float(session["Open"].iloc[0]) if "Open" in session.columns and pd.notna(session["Open"].iloc[0]) else float(session_close.iloc[0])
    session_return = last / session_open - 1 if session_open else 0.0
    typical = (pd.to_numeric(session.get("High", session["Close"]), errors="coerce") + pd.to_numeric(session.get("Low", session["Close"]), errors="coerce") + pd.to_numeric(session["Close"], errors="coerce")) / 3
    vwap_den = float(pd.to_numeric(session.get("Volume", pd.Series(index=session.index, dtype=float)), errors="coerce").fillna(0).sum())
    vwap = float((typical * pd.to_numeric(session.get("Volume", pd.Series(index=session.index, dtype=float)), errors="coerce").fillna(0)).sum() / vwap_den) if vwap_den > 0 else last
    vwap_distance = last / vwap - 1 if vwap else 0.0
    baseline = float(volume.iloc[-21:-1].mean()) if len(volume) > 21 else float(volume.iloc[:-1].mean())
    volume_ratio = float(volume.iloc[-1] / baseline) if baseline > 0 else 1.0

    # Bounded components. Positive intraday action confirms a setup, but the
    # live signal is deliberately only 15% of the technical score.
    momentum = float(np.clip((one_hour + 0.04) / 0.08, 0, 1))
    session_component = float(np.clip((session_return + 0.06) / 0.12, 0, 1))
    volume_component = float(np.clip((volume_ratio - 0.7) / 1.8, 0, 1))
    vwap_component = float(np.clip((vwap_distance + 0.03) / 0.06, 0, 1))
    score = 100 * (0.35 * momentum + 0.25 * session_component + 0.20 * volume_component + 0.20 * vwap_component)
    return {
        "intraday_score": round(score, 2),
        "intraday_return_1h": one_hour,
        "intraday_return_session": session_return,
        "intraday_volume_ratio": volume_ratio,
        "intraday_vwap_distance": vwap_distance,
    }


def scan(limit: int = 1000, top_n: int = 25) -> pd.DataFrame:
    universe = load_top_us_stocks(limit)
    company_map = universe.set_index("ticker")["company_name"].to_dict()
    tickers = universe["ticker"].tolist()

    live_start = (datetime.now(timezone.utc) - timedelta(days=LIVE_HISTORY_DAYS)).strftime("%Y-%m-%d")
    benchmarks = download_benchmarks(live_start)
    spy = benchmarks.get("SPY")
    benchmark_close = spy["Close"] if spy is not None and "Close" in spy else None
    market = download_ohlcv(tickers, live_start)
    intraday = download_intraday(tickers, period="10d", interval="15m")
    intraday_benchmarks = download_intraday_benchmarks(period="10d", interval="15m")
    fundamentals = download_fundamentals(tickers)

    rows = []
    for ticker, prices in market.items():
        if prices.empty or "Close" not in prices.columns:
            continue
        features = add_indicators(prices, benchmark_close)
        row = features.iloc[-1].copy()
        intraday_data = intraday.get(ticker)
        live = _intraday_confirmation(intraday_data, intraday_benchmarks.get("SPY"))
        current_price = live.get("current_price")
        if intraday_data is not None and not intraday_data.empty and "Close" in intraday_data.columns:
            current_price = float(pd.to_numeric(intraday_data["Close"], errors="coerce").dropna().iloc[-1])
        if current_price is not None and pd.notna(current_price):
            row["Close"] = current_price

        avg_dollar_volume = (features["Close"] * features["Volume"]).rolling(20).mean().iloc[-1]
        if row.get("Close", 0) < MIN_PRICE or (pd.notna(avg_dollar_volume) and avg_dollar_volume < MIN_AVG_DOLLAR_VOLUME):
            continue
        scores = score_row(row, REBOUND_WEIGHTS, QUALITY_WEIGHTS, CYCLICAL_WEIGHTS)
        f = fundamentals.get(ticker, {})
        daily_technical = scores.get("technical_opportunity_score")
        live_score = live.get("intraday_score")
        if live_score is not None and pd.notna(daily_technical):
            technical_score = 0.85 * float(daily_technical) + 0.15 * float(live_score)
        else:
            technical_score = daily_technical
        trader_similarity = scores.get("trader_similarity_score")
        fundamental_score = f.get("fundamental_score")
        combined_score = _combined_score(trader_similarity, technical_score, fundamental_score)
        if combined_score is None:
            continue
        signal = _signal_label(combined_score, fundamental_score)
        result = {
            "ticker": ticker,
            "company_name": company_map.get(ticker, ticker),
            "price": float(current_price if current_price is not None else row["Close"]),
            "avg_dollar_volume_20d": float(avg_dollar_volume) if pd.notna(avg_dollar_volume) else None,
            "technical_score": round(float(technical_score), 1) if pd.notna(technical_score) else None,
            "daily_technical_score": round(float(daily_technical), 1) if pd.notna(daily_technical) else None,
            "intraday_score": round(float(live_score), 1) if live_score is not None and pd.notna(live_score) else None,
            "intraday_return_1h": live.get("intraday_return_1h"),
            "intraday_return_session": live.get("intraday_return_session"),
            "intraday_volume_ratio": live.get("intraday_volume_ratio"),
            "intraday_vwap_distance": live.get("intraday_vwap_distance"),
            "trader_similarity_score": round(float(trader_similarity), 1) if pd.notna(trader_similarity) else None,
            "fundamental_score": round(float(fundamental_score), 1) if pd.notna(fundamental_score) else None,
            "fundamental_completeness": f.get("fundamental_completeness"),
            "overall_score": round(float(combined_score), 1),
            "signal": signal,
            "alert_tier": _alert_tier(float(combined_score), signal),
        }
        result.update({k: float(v) if isinstance(v, (int, float)) else v for k, v in scores.items() if k not in {"overall_score", "trader_similarity_score", "technical_opportunity_score"}})
        result.update({k: float(row[k]) if pd.notna(row[k]) else None for k in FEATURE_COLUMNS if k in row})
        result.update({k: f.get(k) for k in FUNDAMENTAL_COLUMNS})
        rows.append(result)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(["overall_score", "trader_similarity_score", "reversal_trigger"], ascending=[False, False, False]).head(top_n).reset_index(drop=True)


if __name__ == "__main__":
    print(scan().to_string(index=False))
