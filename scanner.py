from __future__ import annotations

from datetime import datetime, timedelta, timezone
import numpy as np
import pandas as pd

from config import ALERT_THRESHOLD, STRONG_ALERT_THRESHOLD, EXCEPTIONAL_ALERT_THRESHOLD, WATCH_THRESHOLD, MIN_AVG_DOLLAR_VOLUME, MIN_PRICE, REBOUND_WEIGHTS, QUALITY_WEIGHTS, CYCLICAL_WEIGHTS
from data import download_benchmarks, download_ohlcv, download_intraday, download_intraday_benchmarks, download_sector_benchmarks, SECTOR_ETFS
from fundamentals import download_fundamentals
from analyst import download_analyst_data
from indicators import add_indicators
from model import score_row
from universe import load_top_us_stocks

FEATURE_COLUMNS = ["rsi_7", "rsi_14", "rsi_21", "macd", "macd_signal", "macd_histogram", "macd_histogram_change", "atr_pct", "bollinger_pct", "bollinger_width", "return_1d", "return_3d", "return_5d", "return_10d", "return_20d", "distance_sma20", "distance_sma50", "distance_sma200", "distance_1m_high", "distance_3m_high", "distance_6m_high", "distance_52w_high", "distance_support_20d", "distance_support_60d", "distance_support_120d", "volume_ratio", "volume_ratio_5d", "volatility_20d", "z_score", "close_location", "relative_strength_5d", "relative_strength_20d", "sector_relative_strength_20d"]
FUNDAMENTAL_COLUMNS = ["revenue", "revenue_growth", "eps", "eps_growth", "net_margin", "gross_margin", "fcf", "fcf_growth", "fcf_margin", "roe", "debt_equity", "cash", "pe", "forward_pe", "peg", "fundamental_score", "fundamental_completeness", "sector", "sector_median_pe", "sector_median_forward_pe", "sector_median_peg", "pe_vs_sector", "forward_pe_vs_sector", "peg_vs_sector"]
ANALYST_COLUMNS = ["analyst_recommendation", "analyst_consensus_score", "analyst_strong_buy", "analyst_buy", "analyst_hold", "analyst_sell", "analyst_strong_sell", "analyst_count", "analyst_target_current", "analyst_target_mean", "analyst_target_median", "analyst_target_low", "analyst_target_high", "analyst_target_upside", "analyst_changes_30d", "analyst_bullish_changes_30d", "analyst_bearish_changes_30d", "analyst_target_changes_30d", "analyst_recent_changes", "analyst_completeness"]
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


def _combined_score(trader_similarity, technical_score, fundamental_score, analyst_score):
    # Live score: trader pattern 40%, technical setup 25%, fundamentals 25%, analyst confirmation 10%.
    # Missing inputs are renormalized rather than treated as zero.
    parts = []
    for value, weight in ((trader_similarity, 0.40), (technical_score, 0.25), (fundamental_score, 0.25), (analyst_score, 0.10)):
        if pd.notna(value):
            parts.append((float(value), weight))
    if not parts:
        return None
    total_weight = sum(weight for _, weight in parts)
    return sum(value * weight for value, weight in parts) / total_weight


def _intraday_confirmation(intraday: pd.DataFrame, benchmark: pd.DataFrame | None = None) -> dict[str, float | None]:
    if intraday is None or intraday.empty or "Close" not in intraday.columns:
        return {"intraday_score": None, "intraday_return_1h": None, "intraday_return_session": None, "intraday_volume_ratio": None, "intraday_vwap_distance": None}
    d = intraday.dropna(subset=["Close"]).copy().sort_index()
    if len(d) < 8:
        return {"intraday_score": None, "intraday_return_1h": None, "intraday_return_session": None, "intraday_volume_ratio": None, "intraday_vwap_distance": None}
    close = pd.to_numeric(d["Close"], errors="coerce")
    volume = pd.to_numeric(d.get("Volume", pd.Series(index=d.index, dtype=float)), errors="coerce").fillna(0)
    last = float(close.iloc[-1])
    one_hour = float(close.iloc[-1] / close.iloc[-5] - 1) if close.iloc[-5] else 0.0
    latest_date = d.index[-1].date()
    session = d[d.index.date == latest_date]
    session_close = pd.to_numeric(session["Close"], errors="coerce").dropna()
    session_open = float(session["Open"].iloc[0]) if "Open" in session.columns and pd.notna(session["Open"].iloc[0]) else float(session_close.iloc[0])
    session_return = last / session_open - 1 if session_open else 0.0
    typical = (pd.to_numeric(session.get("High", session["Close"]), errors="coerce") + pd.to_numeric(session.get("Low", session["Close"]), errors="coerce") + pd.to_numeric(session["Close"], errors="coerce")) / 3
    session_volume = pd.to_numeric(session.get("Volume", pd.Series(index=session.index, dtype=float)), errors="coerce").fillna(0)
    vwap_den = float(session_volume.sum())
    vwap = float((typical * session_volume).sum() / vwap_den) if vwap_den > 0 else last
    vwap_distance = last / vwap - 1 if vwap else 0.0
    baseline = float(volume.iloc[-21:-1].mean()) if len(volume) > 21 else float(volume.iloc[:-1].mean())
    volume_ratio = float(volume.iloc[-1] / baseline) if baseline > 0 else 1.0
    momentum = float(np.clip((one_hour + 0.04) / 0.08, 0, 1))
    session_component = float(np.clip((session_return + 0.06) / 0.12, 0, 1))
    volume_component = float(np.clip((volume_ratio - 0.7) / 1.8, 0, 1))
    vwap_component = float(np.clip((vwap_distance + 0.03) / 0.06, 0, 1))
    score = 100 * (0.35 * momentum + 0.25 * session_component + 0.20 * volume_component + 0.20 * vwap_component)
    return {"intraday_score": round(score, 2), "intraday_return_1h": one_hour, "intraday_return_session": session_return, "intraday_volume_ratio": volume_ratio, "intraday_vwap_distance": vwap_distance}


def _sector_relative_strength(stock_prices: pd.DataFrame, sector_prices: pd.DataFrame | None) -> float | None:
    if sector_prices is None or sector_prices.empty or "Close" not in sector_prices.columns or "Close" not in stock_prices.columns:
        return None
    stock_close = pd.to_numeric(stock_prices["Close"], errors="coerce").dropna()
    sector_close = pd.to_numeric(sector_prices["Close"], errors="coerce").dropna()
    if len(stock_close) < 21 or len(sector_close) < 21:
        return None
    stock_return = float(stock_close.iloc[-1] / stock_close.iloc[-21] - 1)
    sector_return = float(sector_close.iloc[-1] / sector_close.iloc[-21] - 1)
    return stock_return - sector_return


def _alert_summary(row):
    drivers = []
    trader = row.get("trader_similarity_score")
    technical = row.get("technical_score")
    fundamental = row.get("fundamental_score")
    analyst = row.get("analyst_consensus_score")
    if trader is not None and trader >= 75:
        drivers.append(f"sterke match met het historische trader-patroon ({trader:.0f}/100)")
    if technical is not None and technical >= 75:
        drivers.append(f"technisch sterk momentum ({technical:.0f}/100)")
    rs = row.get("sector_relative_strength_20d")
    if rs is not None and rs > 0.03:
        drivers.append("presteert duidelijk beter dan de sector")
    if row.get("volume_ratio") is not None and row.get("volume_ratio") >= 1.5:
        drivers.append(f"verhoogd volume ({row['volume_ratio']:.1f}x)")
    if row.get("rsi_14") is not None and row.get("rsi_14") < 45:
        drivers.append(f"RSI blijft relatief laag ({row['rsi_14']:.0f})")
    if row.get("macd_histogram") is not None and row.get("macd_histogram") > 0:
        drivers.append("MACD bevestigt positieve momentumrichting")
    if fundamental is not None and fundamental >= 75:
        drivers.append(f"sterke financiële kwaliteit ({fundamental:.0f}/100)")
    upside = row.get("analyst_target_upside")
    if analyst is not None and analyst >= 65 and upside is not None and upside > 0.10:
        drivers.append(f"analisten zien gemiddeld {upside*100:.0f}% koerspotentieel")
    elif analyst is not None and analyst >= 65:
        drivers.append("analistenconsensus is overwegend positief")
    if not drivers:
        drivers.append("de gecombineerde score overschrijdt de alertdrempel")
    return "Deze alert ontstaat doordat " + ", ".join(drivers[:4]) + "."


def scan(limit: int = 1000, top_n: int = 25) -> pd.DataFrame:
    universe = load_top_us_stocks(limit)
    company_map = universe.set_index("ticker")["company_name"].to_dict()
    tickers = universe["ticker"].tolist()
    live_start = (datetime.now(timezone.utc) - timedelta(days=LIVE_HISTORY_DAYS)).strftime("%Y-%m-%d")
    benchmarks = download_benchmarks(live_start)
    spy = benchmarks.get("SPY")
    benchmark_close = spy["Close"] if spy is not None and "Close" in spy else None
    market = download_ohlcv(tickers, live_start)
    sector_benchmarks = download_sector_benchmarks(live_start)
    intraday = download_intraday(tickers, period="10d", interval="15m")
    intraday_benchmarks = download_intraday_benchmarks(period="10d", interval="15m")
    fundamentals = download_fundamentals(tickers)
    analyst_data = download_analyst_data(tickers)

    rows = []
    for ticker, prices in market.items():
        if prices.empty or "Close" not in prices.columns:
            continue
        features = add_indicators(prices, benchmark_close)
        row = features.iloc[-1].copy()
        f = fundamentals.get(ticker, {})
        a = analyst_data.get(ticker, {})
        sector = f.get("sector")
        sector_etf = SECTOR_ETFS.get(sector)
        sector_rs = _sector_relative_strength(prices, sector_benchmarks.get(sector_etf)) if sector_etf else None
        row["sector_relative_strength_20d"] = sector_rs
        intraday_data = intraday.get(ticker)
        live = _intraday_confirmation(intraday_data, intraday_benchmarks.get("SPY"))
        current_price = None
        if intraday_data is not None and not intraday_data.empty and "Close" in intraday_data.columns:
            live_close = pd.to_numeric(intraday_data["Close"], errors="coerce").dropna()
            if not live_close.empty:
                current_price = float(live_close.iloc[-1])
                row["Close"] = current_price
        if current_price is None:
            current_price = float(row["Close"])

        avg_dollar_volume = (features["Close"] * features["Volume"]).rolling(20).mean().iloc[-1]
        if row.get("Close", 0) < MIN_PRICE or (pd.notna(avg_dollar_volume) and avg_dollar_volume < MIN_AVG_DOLLAR_VOLUME):
            continue
        scores = score_row(row, REBOUND_WEIGHTS, QUALITY_WEIGHTS, CYCLICAL_WEIGHTS)
        daily_technical = scores.get("technical_opportunity_score")
        live_score = live.get("intraday_score")
        technical_score = 0.85 * float(daily_technical) + 0.15 * float(live_score) if live_score is not None and pd.notna(daily_technical) else daily_technical
        trader_similarity = scores.get("trader_similarity_score")
        fundamental_score = f.get("fundamental_score")
        analyst_score = a.get("analyst_consensus_score")
        combined_score = _combined_score(trader_similarity, technical_score, fundamental_score, analyst_score)
        if combined_score is None:
            continue
        signal = _signal_label(combined_score, fundamental_score)
        result = {
            "ticker": ticker,
            "company_name": company_map.get(ticker, ticker),
            "price": current_price,
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
            "analyst_consensus_score": round(float(analyst_score), 1) if pd.notna(analyst_score) else None,
            "market_regime_score": round(float(row.get("market_regime_score", 0.5)) * 100, 1),
            "sector": sector,
            "sector_relative_strength_20d": round(float(sector_rs), 4) if sector_rs is not None else None,
            "overall_score": round(float(combined_score), 1),
            "signal": signal,
            "alert_tier": _alert_tier(float(combined_score), signal),
        }
        result.update({k: float(v) if isinstance(v, (int, float)) else v for k, v in scores.items() if k not in {"overall_score", "trader_similarity_score", "technical_opportunity_score"}})
        result.update({k: float(row[k]) if pd.notna(row[k]) else None for k in FEATURE_COLUMNS if k in row})
        result.update({k: f.get(k) for k in FUNDAMENTAL_COLUMNS})
        result.update({k: a.get(k) for k in ANALYST_COLUMNS})
        result["alert_summary"] = _alert_summary(result) if signal == "ALERT" else None
        history = prices[["Close"]].dropna().tail(140).reset_index()
        result["history_6m"] = [{"date": str(x.date()) if hasattr(x, "date") else str(x), "close": float(y)} for x, y in zip(history.iloc[:, 0], history["Close"])]
        today_points = []
        if intraday_data is not None and not intraday_data.empty and "Close" in intraday_data.columns:
            d = intraday_data.dropna(subset=["Close"]).sort_index()
            if not d.empty:
                latest_date = d.index[-1].date()
                d = d[d.index.date == latest_date].tail(32)
                today_points = [{"date": x.isoformat() if hasattr(x, "isoformat") else str(x), "close": float(y)} for x, y in zip(d.index, d["Close"])]
        result["history_today"] = today_points
        rows.append(result)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(["overall_score", "trader_similarity_score", "reversal_trigger"], ascending=[False, False, False]).head(top_n).reset_index(drop=True)


if __name__ == "__main__":
    print(scan().to_string(index=False))
