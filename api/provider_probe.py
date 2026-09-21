from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler

import requests

TICKERS = ["AAOI", "CRWV", "NVDA", "AMD", "MU", "SOFI", "PLTR", "GOOGL", "NKE", "WDC"]
FINNHUB_BASE = "https://finnhub.io/api/v1"
FMP_BASE = "https://financialmodelingprep.com/api/v3"

FINNHUB_ENDPOINTS = {
    "quote": ("quote", {"symbol": None}),
    "metrics": ("stock/metric", {"symbol": None, "metric": "all"}),
    "financials_reported": ("stock/financials-reported", {"symbol": None, "freq": "annual"}),
    "earnings": ("stock/earnings", {"symbol": None}),
    "earnings_surprises": ("stock/earnings-surprises", {"symbol": None}),
    "eps_estimate": ("stock/eps-estimate", {"symbol": None}),
    "revenue_estimate": ("stock/revenue-estimate", {"symbol": None}),
    "ebitda_estimate": ("stock/ebitda-estimate", {"symbol": None}),
    "recommendations": ("stock/recommendation", {"symbol": None}),
    "price_target": ("stock/price-target", {"symbol": None}),
    "upgrades_downgrades": ("stock/upgrade-downgrade", {"symbol": None}),
    "peers": ("stock/peers", {"symbol": None}),
}

FMP_ENDPOINTS = {
    "quote": ("quote/", {}),
    "income_statement": ("income-statement/", {"period": "annual", "limit": 20}),
    "balance_sheet": ("balance-sheet-statement/", {"period": "annual", "limit": 20}),
    "cash_flow": ("cash-flow-statement/", {"period": "annual", "limit": 20}),
    "ratios": ("ratios/", {"limit": 20}),
    "key_metrics": ("key-metrics/", {"limit": 20}),
    "enterprise_values": ("enterprise-values/", {"limit": 20}),
    "analyst_estimates": ("analyst-estimates/", {"limit": 20}),
    "grades": ("grades/", {"limit": 100}),
    "grades_historical": ("grades-historical/", {"limit": 100}),
    "price_target_consensus": ("price-target-consensus/", {}),
    "price_target": ("price-target/", {"limit": 100}),
    "earnings_surprises": ("earnings-surprises/", {"limit": 20}),
    "historical_price": ("historical-price-full/", {"timeseries": 5000}),
}


def _request(url: str, params: dict, timeout: int = 20) -> dict:
    started = time.monotonic()
    try:
        r = requests.get(url, params=params, timeout=timeout)
        elapsed_ms = round((time.monotonic() - started) * 1000)
        try:
            payload = r.json()
        except Exception:
            payload = r.text[:500]
        return {
            "http_status": r.status_code,
            "ok": r.status_code == 200,
            "elapsed_ms": elapsed_ms,
            "has_data": bool(payload) and not (isinstance(payload, list) and len(payload) == 0),
            "payload_type": type(payload).__name__,
            "sample_keys": list(payload[0].keys())[:20] if isinstance(payload, list) and payload and isinstance(payload[0], dict) else (list(payload.keys())[:20] if isinstance(payload, dict) else []),
            "sample_count": len(payload) if isinstance(payload, (list, dict)) else None,
            "error_hint": (payload.get("Error Message") or payload.get("error") or payload.get("message")) if isinstance(payload, dict) else None,
        }
    except Exception as exc:
        return {"http_status": None, "ok": False, "elapsed_ms": round((time.monotonic() - started) * 1000), "has_data": False, "payload_type": None, "sample_keys": [], "sample_count": None, "error_hint": str(exc)[:200]}


def _finnhub(symbol: str) -> dict:
    key = os.getenv("FINNHUB_API_KEY")
    if not key:
        return {name: {"ok": False, "error_hint": "FINNHUB_API_KEY not configured"} for name in FINNHUB_ENDPOINTS}
    out = {}
    for name, (endpoint, params) in FINNHUB_ENDPOINTS.items():
        p = dict(params)
        for k, v in list(p.items()):
            if v is None:
                p[k] = symbol
        p["token"] = key
        out[name] = _request(f"{FINNHUB_BASE}/{endpoint}", p)
    return out


def _fmp(symbol: str) -> dict:
    key = os.getenv("FMP_API_KEY")
    if not key:
        return {name: {"ok": False, "error_hint": "FMP_API_KEY not configured"} for name in FMP_ENDPOINTS}
    out = {}
    for name, (prefix, params) in FMP_ENDPOINTS.items():
        p = dict(params)
        p["apikey"] = key
        out[name] = _request(f"{FMP_BASE}/{prefix}{symbol}", p)
    return out


def run_probe() -> dict:
    results = {}
    for ticker in TICKERS:
        results[ticker] = {"finnhub": _finnhub(ticker), "fmp": _fmp(ticker)}
    return {"generated_at": datetime.now(timezone.utc).isoformat(), "tickers": TICKERS, "results": results}


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.split("?", 1)[0] != "/api/provider_probe":
            self.send_response(404)
            self.end_headers()
            return
        report = run_probe()
        body = json.dumps(report, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)
