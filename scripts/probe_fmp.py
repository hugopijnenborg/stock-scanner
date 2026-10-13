"""Test welke FMP /stable/ endpoints jouw abonnement echt geeft.

Schrijft data/fmp_probe.json: per endpoint de status, het aantal records en
de veldnamen van het eerste record. Daarmee koppelen we de velden aan het
model zonder te gokken.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from providers.fmp_provider import FMPProvider  # noqa: E402

TICKERS = ["AAOI", "CRWV", "NVDA", "AMD", "MU", "SOFI", "PLTR", "GOOGL", "NKE", "WDC"]
OUT = Path(__file__).resolve().parents[1] / "data" / "fmp_probe.json"


def _check(fn):
    try:
        payload = fn()["data"]
    except Exception as exc:  # noqa: BLE001
        status = getattr(exc, "status", None)
        return {"ok": False, "status": status, "error": str(exc)[:200]}
    records = payload if isinstance(payload, list) else [payload]
    first = records[0] if records and isinstance(records[0], dict) else {}
    return {
        "ok": bool(records),
        "status": 200,
        "records": len(records),
        "fields": sorted(first.keys()),
        "sample": {k: first[k] for k in list(first)[:40]},
    }


def main() -> None:
    fmp = FMPProvider()
    today = date.today()
    report = {"generated_at": datetime.now(timezone.utc).isoformat(), "tickers": TICKERS, "results": {}}

    for ticker in TICKERS:
        calls = {
            "profile": lambda t=ticker: fmp.profile(t),
            "quote": lambda t=ticker: fmp.quote(t),
            "stock_peers": lambda t=ticker: fmp.stock_peers(t),
            "income_statement_q": lambda t=ticker: fmp.income_statement(t),
            "balance_sheet_q": lambda t=ticker: fmp.balance_sheet(t),
            "cash_flow_q": lambda t=ticker: fmp.cash_flow(t),
            "financial_growth_q": lambda t=ticker: fmp.financial_growth(t),
            "key_metrics_ttm": lambda t=ticker: fmp.key_metrics_ttm(t),
            "ratios_ttm": lambda t=ticker: fmp.ratios_ttm(t),
            "enterprise_values": lambda t=ticker: fmp.enterprise_values(t),
            "analyst_estimates_annual": lambda t=ticker: fmp.analyst_estimates(t, "annual"),
            "analyst_estimates_quarter": lambda t=ticker: fmp.analyst_estimates(t, "quarter"),
            "price_target_summary": lambda t=ticker: fmp.price_target_summary(t),
            "price_target_consensus": lambda t=ticker: fmp.price_target_consensus(t),
            "price_target_news": lambda t=ticker: fmp.price_target_news(t),
            "grades": lambda t=ticker: fmp.grades(t),
            "grades_historical": lambda t=ticker: fmp.grades_historical(t),
            "grades_consensus": lambda t=ticker: fmp.grades_consensus(t),
            "ratings_snapshot": lambda t=ticker: fmp.ratings_snapshot(t),
            "earnings": lambda t=ticker: fmp.earnings(t),
        }
        report["results"][ticker] = {}
        for label, fn in calls.items():
            report["results"][ticker][label] = _check(fn)
            time.sleep(0.1)  # Premium = 750 calls/min, ruim binnen de limiet
        print(ticker, "klaar")

    report["results"]["_market"] = {
        "earnings_calendar": _check(lambda: fmp.earnings_calendar(str(today), str(today + timedelta(days=14)))),
        "sector_pe_snapshot": _check(lambda: fmp.sector_pe_snapshot(str(today - timedelta(days=1)))),
    }

    # Samenvatting: per endpoint hoeveel van de 10 tickers data gaven.
    summary = {}
    for ticker in TICKERS:
        for label, res in report["results"][ticker].items():
            entry = summary.setdefault(label, {"ok": 0, "status_codes": set()})
            entry["ok"] += 1 if res["ok"] else 0
            entry["status_codes"].add(res["status"])
    report["summary"] = {k: {"ok_van_10": v["ok"], "status_codes": sorted(map(str, v["status_codes"]))} for k, v in summary.items()}

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print("\nSAMENVATTING (hoeveel van de 10 tickers gaven data):")
    for label, info in report["summary"].items():
        print(f"  {label:28s} {info['ok_van_10']}/10  status {info['status_codes']}")


if __name__ == "__main__":
    main()
