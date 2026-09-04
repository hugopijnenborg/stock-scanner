from __future__ import annotations

from datetime import datetime, timedelta, timezone
import numpy as np
import pandas as pd

from config import ALERT_THRESHOLD, MIN_AVG_DOLLAR_VOLUME, MIN_PRICE, WATCH_THRESHOLD, REBOUND_WEIGHTS, QUALITY_WEIGHTS, CYCLICAL_WEIGHTS
from data import download_benchmarks, download_ohlcv, download_intraday, download_intraday_benchmarks, download_sector_benchmarks, SECTOR_ETFS
from fundamentals import download_fundamentals
from analyst import download_analyst_data
from indicators import add_indicators
from model import score_row
from universe import load_top_us_stocks

FEATURE_COLUMNS = ["rsi_7", "rsi_14", "rsi_21", "macd", "macd_signal", "macd_histogram", "macd_histogram_change", "atr_pct", "bollinger_pct", "bollinger_width", "return_1d", "return_3d", "return_5d", "return_10d", "return_20d", "distance_sma20", "distance_sma50", "distance_sma200", "distance_1m_high", "distance_3m_high", "distance_6m_high", "distance_52w_high", "distance_support_20d", "distance_support_60d", "distance_support_120d", "volume_ratio", "volume_ratio_5d", "volatility_20d", "z_score", "close_location", "relative_strength_5d", "relative_strength_20d", "sector_relative_strength_20d"]
FUNDAMENTAL_COLUMNS = ["revenue", "revenue_growth", "eps", "eps_growth", "net_margin", "gross_margin", "fcf", "fcf_growth", "fcf_margin", "roe", "debt_equity", "cash", "pe", "forward_pe", "peg", "fundamental_score", "fundamental_completeness", "sector", "sector_median_pe", "sector_median_forward_pe", "sector_median_peg", "pe_vs_sector", "forward_pe_vs_sector", "peg_vs_sector"]
ANALYST_COLUMNS = ["analyst_recommendation", "analyst_consensus_score", "analyst_strong_buy", "analyst_buy", "analyst_hold", "analyst_sell", "analyst_strong_sell", "analyst_count", "analyst_target_current", "analyst_target_mean", "analyst_target_median", "analyst_target_low", "analyst_target_high", "analyst_target_upside", "analyst_changes_30d", "analyst_bullish_changes_30d", "analyst_bearish_changes_30d", "analyst_target_changes_30d", "analyst_recent_changes", "analyst_completeness", "last_earnings_date", "last_earnings_surprise_pct", "next_earnings_date", "recent_news"]
LIVE_HISTORY_DAYS = 450


def _signal_label(score: float) -> str:
    return "ALERT" if score >= ALERT_THRESHOLD else "NO_SIGNAL"


def _analyst_score(row):
    """Analyst component: 60% rating consensus + 40% target upside."""
    consensus = row.get("analyst_consensus_score")
    mean_target = row.get("analyst_target_mean")
    price = row.get("price")
    parts = []
    if pd.notna(consensus):
        parts.append((float(consensus), 0.60))
    if pd.notna(mean_target) and pd.notna(price) and float(price) > 0:
        upside = float(mean_target) / float(price) - 1.0
        target_score = float(np.clip((upside + 0.10) / 0.60, 0.0, 1.0) * 100.0)
        parts.append((target_score, 0.40))
    if not parts:
        return None
    total = sum(weight for _, weight in parts)
    return sum(value * weight for value, weight in parts) / total


def _combined_score(trader_similarity, technical_score, analyst_score):
    parts = []
    for value, weight in ((trader_similarity, 0.50), (technical_score, 0.30), (analyst_score, 0.20)):
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


def _fmt_pct(v):
    return f"{float(v) * 100:+.1f}%"


def _alert_summary(row):
    r1 = row.get("return_1d")
    r5 = row.get("return_5d")
    r10 = row.get("return_10d")
    earnings_date = row.get("last_earnings_date")
    earnings_surprise = row.get("last_earnings_surprise_pct")
    sentences = []
    recent_move = r5 if r5 is not None else r10
    if recent_move is not None and recent_move <= -0.06:
        sentences.append(f"Het aandeel is de afgelopen periode hard teruggevallen ({_fmt_pct(recent_move)}), terwijl de koers op korte termijn nog onder druk staat.")
    elif recent_move is not None and recent_move >= 0.06:
        sentences.append(f"Het aandeel heeft de afgelopen periode duidelijk momentum opgebouwd ({_fmt_pct(recent_move)}), waardoor de huidige beweging meer is dan een kleine dagfluctuatie.")
    elif r1 is not None and abs(r1) >= 0.025:
        sentences.append(f"De koers beweegt vandaag opvallend sterk ({_fmt_pct(r1)}).")
    earnings_recent = False
    if earnings_date:
        try:
            dt = pd.Timestamp(earnings_date)
            if dt.tzinfo is None:
                dt = dt.tz_localize("UTC")
            earnings_recent = (pd.Timestamp.now(tz="UTC") - dt).days <= 10
        except Exception:
            pass
    if earnings_recent and earnings_surprise is not None:
        direction = "positief" if earnings_surprise >= 0 else "negatief"
        sentences.append(f"De recente koersreactie volgt kort op de kwartaalcijfers, met een {direction} winstverrassing van {earnings_surprise:+.1f}%.")
    analyst = row.get("analyst_recommendation")
    upside = row.get("analyst_target_upside")
    target = row.get("analyst_target_mean")
    if analyst:
        if upside is not None and target is not None:
            sentences.append(f"Analistenconsensus: {analyst.replace('_', ' ').title()}, met een gemiddeld koersdoel van ${target:.2f} ({upside * 100:+.1f}% vanaf de koers waarop de analyst-data is gebaseerd).")
        else:
            sentences.append(f"Analistenconsensus: {analyst.replace('_', ' ').title()}.")
    rs = row.get("sector_relative_strength_20d")
    if rs is not None and rs > 0.03:
        sentences.append("Het aandeel houdt relatief goed stand tegenover de eigen sector.")
    if not sentences:
        sentences.append("De huidige technische situatie en overeenkomst met historische trader-setups vormen samen het actieve signaal.")
    return " ".join(sentences[:4])


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
    intraday = download_intraday(tickers, period="3d", interval="15m")
    intraday_benchmarks = download_intraday_benchmarks(period="3d", interval="15m")
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
        analyst_consensus = a.get("analyst_consensus_score")
        analyst_score = _analyst_score({**a, "price": current_price})
        combined_score = _combined_score(trader_similarity, technical_score, analyst_score)
        if combined_score is None:
            continue
        signal = _signal_label(combined_score)
        dip = scores.get("dip_score")
        # WATCH is an early warning for a stock that has had a hard
        # recent sell-off but has not yet reached the real BUY ALERT
        # threshold. It is intentionally independent of dip_score and
        # trader/technical minimums so every stock in the universe can qualify.
        recent_selloff = bool(
            (pd.notna(row.get("return_5d")) and float(row.get("return_5d")) <= -0.08)
            or (pd.notna(row.get("return_3d")) and float(row.get("return_3d")) <= -0.07)
            or (pd.notna(row.get("return_1d")) and float(row.get("return_1d")) <= -0.05)
        )
        watch_candidate = bool(
            signal != "ALERT"
            and combined_score >= WATCH_THRESHOLD
            and combined_score < ALERT_THRESHOLD
            and recent_selloff
        )
        setup_type = "watch" if watch_candidate else scores.get("setup_type")
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
            "fundamental_score": round(float(f.get("fundamental_score")), 1) if pd.notna(f.get("fundamental_score")) else None,
            "fundamental_completeness": f.get("fundamental_completeness"),
            "analyst_consensus_score": round(float(analyst_consensus), 1) if pd.notna(analyst_consensus) else None,
            "analyst_score": round(float(analyst_score), 1) if pd.notna(analyst_score) else None,
            "analyst_target_upside_live": ((float(a.get("analyst_target_mean")) / current_price) - 1.0) if pd.notna(a.get("analyst_target_mean")) and current_price > 0 else None,
            "market_regime_score": round(float(row.get("market_regime_score", 0.5)) * 100, 1),
            "sector": sector,
            "sector_relative_strength_20d": round(float(sector_rs), 4) if sector_rs is not None else None,
            "overall_score": round(float(combined_score), 1),
            "signal": signal,
            "alert_tier": "BUY ALERT" if signal == "ALERT" else "",
            "watch_candidate": watch_candidate,
            "dip_score": round(float(dip), 1) if pd.notna(dip) else None,
            "setup_type": setup_type,
        }
        result.update({k: float(v) if isinstance(v, (int, float)) else v for k, v in scores.items() if k not in {"overall_score", "trader_similarity_score", "technical_opportunity_score", "watch_candidate", "setup_type"}})
        result.update({k: float(row[k]) if pd.notna(row[k]) else None for k in FEATURE_COLUMNS if k in row})
        result.update({k: f.get(k) for k in FUNDAMENTAL_COLUMNS})
        result.update({k: a.get(k) for k in ANALYST_COLUMNS})
        result["alert_summary"] = _alert_summary(result) if signal == "ALERT" else None
        history = prices[["Close"]].dropna().tail(140).reset_index()
        result["history_6m"] = [{"date": str(x.date()) if hasattr(x, "date") else str(x), "close": float(y)} for x, y in zip(history.iloc[:, 0], history["Close"])]
        week_points = []
        if intraday_data is not None and not intraday_data.empty and "Close" in intraday_data.columns:
            d = intraday_data.dropna(subset=["Close"]).sort_index()
            if not d.empty:
                cutoff = d.index[-1] - pd.Timedelta(days=7)
                d = d[d.index >= cutoff]
                week_points = [{"date": x.isoformat() if hasattr(x, "isoformat") else str(x), "close": float(y)} for x, y in zip(d.index, d["Close"])]
        result["history_1w"] = week_points
        today_points = []
        if week_points:
            latest_day = str(week_points[-1]["date"])[:10]
            today_points = [p for p in week_points if str(p["date"])[:10] == latest_day]
        result["history_today"] = today_points
        rows.append(result)
    if not rows:
        return pd.DataFrame()
    # Return the full curated universe so WATCH candidates are not lost just because they fall outside the top N.
    return pd.DataFrame(rows).sort_values(["overall_score", "trader_similarity_score", "reversal_trigger"], ascending=[False, False, False]).reset_index(drop=True)


if __name__ == "__main__":
    print(scan().to_string(index=False))
