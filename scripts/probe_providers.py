from __future__ import annotations

import json
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from providers.finnhub_provider import FinnhubProvider
from providers.fmp_provider import FMPProvider


TICKERS = ["AAOI", "CRWV", "NVDA", "AMD", "MU", "SOFI", "PLTR", "GOOGL", "NKE", "WDC"]
OUT = Path(__file__).resolve().parents[1] / "data" / "provider_probe.json"


def _unix_days_ago(days: int) -> int:
    return int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp())


def _call(label: str, fn):
    try:
        payload = fn()
        data = payload.get("data")
        return {"status": "ok", "has_data": bool(data), "error": None}
    except Exception as exc:
        return {"status": "error", "has_data": False, "error": str(exc)[:300]}


def main() -> None:
    finnhub = FinnhubProvider()
    fmp = FMPProvider()
    report: dict = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tickers": TICKERS,
        "finnhub": {},
        "fmp": {},
    }

    start = _unix_days_ago(365 * 5)
    end = int(datetime.now(timezone.utc).timestamp())

    for ticker in TICKERS:
        print(f"\n{ticker} - Finnhub")
        report["finnhub"][ticker] = {}
        calls = {
            "profile": lambda t=ticker: finnhub.profile(t),
            "quote": lambda t=ticker: finnhub.quote(t),
            "metrics": lambda t=ticker: finnhub.metrics(t),
            "financials_reported": lambda t=ticker: finnhub.financials_reported(t),
            "earnings": lambda t=ticker: finnhub.earnings(t),
            "earnings_surprises": lambda t=ticker: finnhub.earnings_surprises(t),
            "eps_estimate": lambda t=ticker: finnhub.eps_estimate(t),
            "revenue_estimate": lambda t=ticker: finnhub.revenue_estimate(t),
            "ebitda_estimate": lambda t=ticker: finnhub.ebitda_estimate(t),
            "recommendations": lambda t=ticker: finnhub.recommendations(t),
            "price_target": lambda t=ticker: finnhub.price_target(t),
            "upgrades_downgrades": lambda t=ticker: finnhub.upgrades_downgrades(t),
            "peers": lambda t=ticker: finnhub.peers(t),
            "candles": lambda t=ticker: finnhub.candles(t, start, end),
        }
        for label, fn in calls.items():
            report["finnhub"][ticker][label] = _call(label, fn)
            time.sleep(1.05)  # stay close to Finnhub's free-tier request rate

    for ticker in TICKERS:
        print(f"\n{ticker} - FMP")
        report["fmp"][ticker] = {}
        calls = {
            "profile": lambda t=ticker: fmp.profile(t),
            "quote": lambda t=ticker: fmp.quote(t),
            "income_statement": lambda t=ticker: fmp.income_statement(t),
            "balance_sheet": lambda t=ticker: fmp.balance_sheet(t),
            "cash_flow": lambda t=ticker: fmp.cash_flow(t),
            "ratios": lambda t=ticker: fmp.ratios(t),
            "key_metrics": lambda t=ticker: fmp.key_metrics(t),
            "enterprise_values": lambda t=ticker: fmp.enterprise_values(t),
            "analyst_estimates": lambda t=ticker: fmp.analyst_estimates(t),
            "grades": lambda t=ticker: fmp.grades(t),
            "grades_historical": lambda t=ticker: fmp.grades_historical(t),
            "price_target_consensus": lambda t=ticker: fmp.price_target_consensus(t),
            "price_target": lambda t=ticker: fmp.price_target(t),
            "earnings_surprises": lambda t=ticker: fmp.earnings_surprises(t),
            "historical_price": lambda t=ticker: fmp.historical_price(t),
        }
        for label, fn in calls.items():
            report["fmp"][ticker][label] = _call(label, fn)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nSaved provider probe to {OUT}")


if __name__ == "__main__":
    main()
