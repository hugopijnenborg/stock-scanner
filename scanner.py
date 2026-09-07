from __future__ import annotations

from datetime import datetime, timedelta, timezone
import numpy as np
import pandas as pd

from config import ALERT_THRESHOLD, WATCH_THRESHOLD, MIN_AVG_DOLLAR_VOLUME, MIN_PRICE, REBOUND_WEIGHTS, QUALITY_WEIGHTS, CYCLICAL_WEIGHTS
from data import download_benchmarks, download_ohlcv, download_intraday, download_intraday_benchmarks, download_sector_benchmarks, SECTOR_ETFS
from fundamentals import download_fundamentals
from analyst import download_analyst_data
from indicators import add_indicators
from model import score_row
from universe import load_top_us_stocks

FEATURE_COLUMNS = ["rsi_7", "rsi_14", "rsi_21", "macd", "macd_signal", "macd_histogram", "macd_histogram_change", "atr_pct", "bollinger_pct", "bollinger_width", "return_1d", "return_3d", "return_5d", "return_10d", "return_20d", "distance_sma20", "distance_sma50", "distance_sma200", "distance_1m_high", "distance_3m_high", "distance_6m_high", "distance_52w_high", "high_52w", "distance_support_20d", "distance_support_60d", "distance_support_120d", "volume_ratio", "volume_ratio_5d", "volatility_20d", "z_score", "close_location", "relative_strength_5d", "relative_strength_20d", "sector_relative_strength_20d"]
FUNDAMENTAL_COLUMNS = ["revenue", "revenue_growth", "eps", "eps_growth", "net_margin", "gross_margin", "fcf", "fcf_growth", "fcf_margin", "roe", "debt_equity", "cash", "pe", "forward_pe", "peg", "fundamental_score", "fundamental_completeness", "sector", "sector_median_pe", "sector_median_forward_pe", "sector_median_peg", "pe_vs_sector", "forward_pe_vs_sector", "peg_vs_sector"]
ANALYST_COLUMNS = ["analyst_recommendation", "analyst_consensus_score", "analyst_strong_buy", "analyst_buy", "analyst_hold", "analyst_sell", "analyst_strong_sell", "analyst_count", "analyst_target_current", "analyst_target_mean", "analyst_target_median", "analyst_target_low", "analyst_target_high", "analyst_target_upside", "analyst_changes_30d", "analyst_bullish_changes_30d", "analyst_bearish_changes_30d", "analyst_target_changes_30d", "analyst_recent_changes", "analyst_completeness", "last_earnings_date", "last_earnings_surprise_pct", "next_earnings_date", "recent_news"]
LIVE_HISTORY_DAYS = 450


def _signal_label(score) -> str:
    """Signal is driven only by the validated trader+technical score.

    Fundamentals/analyst data are not required and do not gate the signal:
    they were never out-of-sample tested (see walk_forward_validation.py),
    so they stay informational context rather than part of the trigger.
    """
    if score is None or pd.isna(score):
        return "DATA_INCOMPLETE"
    if score >= ALERT_THRESHOLD:
        return "ALERT"
    if score >= WATCH_THRESHOLD:
        return "WATCH"
    return "NO_SIGNAL"


def _context_score(fundamental_score, analyst_score):
    """Informational-only blend of fundamentals + analyst data.

    Shown in the dashboard as extra context on an alert, never used to
    decide ALERT/WATCH/NO_SIGNAL.
    """
    parts = [(float(v), w) for v, w in ((fundamental_score, 0.70), (analyst_score, 0.30)) if pd.notna(v)]
    if not parts:
        return None
    total_weight = sum(w for _, w in parts)
    return sum(v * w for v, w in parts) / total_weight


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
    """Explain the current market situation: technical move, whether
    fundamentals justify the selloff, and what analysts are doing right now
    (direction of revisions, not just the static consensus level)."""
    price = row.get("price")
    r1 = row.get("return_1d")
    r5 = row.get("return_5d")
    r10 = row.get("return_10d")
    r20 = row.get("return_20d")
    high_52w = row.get("distance_52w_high")
    volume_ratio = row.get("volume_ratio")
    news = row.get("recent_news") or []
    earnings_date = row.get("last_earnings_date")
    earnings_surprise = row.get("last_earnings_surprise_pct")
    next_earnings = row.get("next_earnings_date")
    news_text = " ".join(str(x.get("title", "")) for x in news if isinstance(x, dict)).lower()

    sections = []

    # --- 1. Technical situation: what actually happened, with numbers ---
    headline = None
    recent_move = r5 if r5 is not None else r10
    if recent_move is not None and recent_move <= -0.06:
        headline = f"Het aandeel is de afgelopen periode {abs(recent_move) * 100:.1f}% gedaald"
        if r1 is not None and abs(r1) >= 0.04:
            headline += f", waarvan {abs(r1) * 100:.1f}% vandaag alleen al"
    elif recent_move is not None and recent_move >= 0.06:
        headline = f"Het aandeel heeft de afgelopen periode {_fmt_pct(recent_move)} momentum opgebouwd"
    elif r1 is not None and abs(r1) >= 0.025:
        headline = f"De koers beweegt vandaag opvallend sterk ({_fmt_pct(r1)})"
    extra_bits = []
    if high_52w is not None and high_52w <= -0.20:
        extra_bits.append(f"staat {abs(high_52w) * 100:.1f}% onder de 52-weken high")
    if volume_ratio is not None and volume_ratio >= 1.8:
        extra_bits.append(f"handelsvolume ligt circa {volume_ratio:.1f}x boven het 20-daags gemiddelde")
    if headline:
        sections.append(headline + ((", " + " en ".join(extra_bits)) if extra_bits else "") + ".")
    elif extra_bits:
        sections.append(("De koers " + " en ".join(extra_bits) + ".").capitalize())

    # --- 2. Does this look like a capitulation on a fine business, or a
    # justified selloff? Earnings surprise + growth/margin trend as evidence.
    earnings_recent = False
    if earnings_date:
        try:
            dt = pd.Timestamp(earnings_date)
            if dt.tzinfo is None:
                dt = dt.tz_localize("UTC")
            earnings_recent = (pd.Timestamp.now(tz="UTC") - dt).days <= 10
        except Exception:
            pass
    fund_bits = []
    if earnings_recent and earnings_surprise is not None:
        direction = "boven" if earnings_surprise >= 0 else "onder"
        fund_bits.append(f"De cijfers kwamen recent {abs(earnings_surprise):.1f}% {direction} verwachting uit")
    revenue_growth = row.get("revenue_growth")
    fcf = row.get("fcf")
    margin = row.get("net_margin")
    if revenue_growth is not None and revenue_growth > 0.05:
        fund_bits.append(f"omzet groeit met {_fmt_pct(revenue_growth)}")
    if fcf is not None and fcf > 0:
        fund_bits.append("vrije kasstroom is positief")
    if margin is not None and margin > 0.08:
        fund_bits.append(f"nettomarge ligt rond {margin * 100:.1f}%")
    if fund_bits:
        justified = earnings_recent and earnings_surprise is not None and earnings_surprise < -5
        lead = "De cijfers lijken de koersdaling te bevestigen: " if justified else "De koersdaling lijkt niet gedreven door verslechterende fundamentals: "
        sections.append(lead + ", ".join(fund_bits[:3]) + ".")
    elif earnings_recent and ("earnings" in news_text or "quarter" in news_text or "results" in news_text):
        sections.append("De recente koersreactie valt samen met de publicatie van de kwartaalcijfers.")

    # --- 3. Analyst direction: are targets moving with or against the price? ---
    analyst = row.get("analyst_recommendation")
    upside = row.get("analyst_target_upside")
    target = row.get("analyst_target_mean")
    bullish_30d = row.get("analyst_bullish_changes_30d") or 0
    bearish_30d = row.get("analyst_bearish_changes_30d") or 0
    target_changes_30d = row.get("analyst_target_changes_30d") or 0
    analyst_bits = []
    if analyst and target is not None and upside is not None:
        analyst_bits.append(f"consensus {analyst.replace('_', ' ').title()}, gemiddeld koersdoel ${target:.2f} ({upside * 100:+.1f}% vanaf de huidige koers)")
    if target_changes_30d > 0:
        if bullish_30d > bearish_30d:
            analyst_bits.append(f"targets zijn de afgelopen 30 dagen vaker verhoogd dan verlaagd ({bullish_30d} vs {bearish_30d})")
        elif bearish_30d > bullish_30d:
            analyst_bits.append(f"targets zijn de afgelopen 30 dagen vaker verlaagd dan verhoogd ({bearish_30d} vs {bullish_30d})")
    if analyst_bits:
        # The key divergence signal: price down, targets not falling (or rising).
        divergent = recent_move is not None and recent_move <= -0.06 and bullish_30d >= bearish_30d and target_changes_30d > 0
        lead = "Analisten bevestigen dit beeld: " if divergent else "Analisten: "
        sections.append(lead + "; ".join(analyst_bits) + ".")

    if next_earnings:
        try:
            dt = pd.Timestamp(next_earnings)
            if dt.tzinfo is None:
                dt = dt.tz_localize("UTC")
            days_out = (dt - pd.Timestamp.now(tz="UTC")).days
            if 0 <= days_out <= 45:
                sections.append(f"Eerstvolgende kwartaalcijfers over ongeveer {days_out} dagen, een concrete katalysator binnen de horizon van deze alert.")
        except Exception:
            pass

    if not sections:
        sections.append("De huidige koersbeweging en onderliggende bedrijfsdata komen samen op een niveau waarop de scanner een kansrijke setup ziet.")
    return " ".join(sections)


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
        # technical_score (daily+intraday blend) is shown for live confirmation
        # context, but the signal itself is driven by scores["overall_score"]
        # (70% trader + 30% daily technical) — the exact formula tested in
        # walk_forward_validation.py / market_validation.py. Intraday data
        # isn't available for historical backtests, so it stays informational.
        technical_score = 0.85 * float(daily_technical) + 0.15 * float(live_score) if live_score is not None and pd.notna(daily_technical) else daily_technical
        trader_similarity = scores.get("trader_similarity_score")
        validated_score = scores.get("overall_score")
        fundamental_score = f.get("fundamental_score")
        analyst_score = a.get("analyst_consensus_score")
        context_score = _context_score(fundamental_score, analyst_score)
        if validated_score is None or pd.isna(validated_score):
            continue
        signal = _signal_label(validated_score)
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
            "context_score": round(float(context_score), 1) if context_score is not None else None,
            "market_regime_score": round(float(row.get("market_regime_score", 0.5)) * 100, 1),
            "sector": sector,
            "sector_relative_strength_20d": round(float(sector_rs), 4) if sector_rs is not None else None,
            "overall_score": round(float(validated_score), 1),
            "signal": signal,
        }
        result.update({k: float(v) if isinstance(v, (int, float)) else v for k, v in scores.items() if k not in {"overall_score", "trader_similarity_score", "technical_opportunity_score"}})
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
    return pd.DataFrame(rows).sort_values(["overall_score", "trader_similarity_score", "reversal_trigger"], ascending=[False, False, False]).head(top_n).reset_index(drop=True)


if __name__ == "__main__":
    print(scan().to_string(index=False))
