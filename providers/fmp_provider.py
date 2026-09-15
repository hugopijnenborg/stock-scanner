from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import requests


BASE_URL = "https://financialmodelingprep.com/api/v3"


class FMPError(RuntimeError):
    pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class FMPProvider:
    """Thin Financial Modeling Prep client used only for secondary coverage."""

    def __init__(self, api_key: str | None = None, timeout: int = 30):
        self.api_key = api_key or os.getenv("FMP_API_KEY")
        if not self.api_key:
            raise FMPError("FMP_API_KEY is not configured")
        self.timeout = timeout
        self.session = requests.Session()

    def get(self, endpoint: str, **params: Any) -> dict[str, Any]:
        params["apikey"] = self.api_key
        url = f"{BASE_URL}/{endpoint.lstrip('/')}"
        response = self.session.get(url, params=params, timeout=self.timeout)
        if response.status_code != 200:
            raise FMPError(f"FMP {response.status_code}: {response.text[:300]}")
        payload = response.json()
        return {
            "source": "fmp",
            "endpoint": endpoint,
            "retrieved_at": _now_iso(),
            "data": payload,
        }

    def profile(self, symbol: str) -> dict[str, Any]:
        return self.get("profile/" + symbol)

    def quote(self, symbol: str) -> dict[str, Any]:
        return self.get("quote/" + symbol)

    def income_statement(self, symbol: str, period: str = "annual", limit: int = 20) -> dict[str, Any]:
        return self.get("income-statement/" + symbol, period=period, limit=limit)

    def balance_sheet(self, symbol: str, period: str = "annual", limit: int = 20) -> dict[str, Any]:
        return self.get("balance-sheet-statement/" + symbol, period=period, limit=limit)

    def cash_flow(self, symbol: str, period: str = "annual", limit: int = 20) -> dict[str, Any]:
        return self.get("cash-flow-statement/" + symbol, period=period, limit=limit)

    def ratios(self, symbol: str, limit: int = 20) -> dict[str, Any]:
        return self.get("ratios/" + symbol, limit=limit)

    def key_metrics(self, symbol: str, limit: int = 20) -> dict[str, Any]:
        return self.get("key-metrics/" + symbol, limit=limit)

    def enterprise_values(self, symbol: str, limit: int = 20) -> dict[str, Any]:
        return self.get("enterprise-values/" + symbol, limit=limit)

    def analyst_estimates(self, symbol: str, limit: int = 20) -> dict[str, Any]:
        return self.get("analyst-estimates/" + symbol, limit=limit)

    def grades(self, symbol: str, limit: int = 100) -> dict[str, Any]:
        return self.get("grades/" + symbol, limit=limit)

    def grades_historical(self, symbol: str, limit: int = 100) -> dict[str, Any]:
        return self.get("grades-historical/" + symbol, limit=limit)

    def price_target_consensus(self, symbol: str) -> dict[str, Any]:
        return self.get("price-target-consensus/" + symbol)

    def price_target(self, symbol: str, limit: int = 100) -> dict[str, Any]:
        return self.get("price-target/" + symbol, limit=limit)

    def earnings_surprises(self, symbol: str, limit: int = 20) -> dict[str, Any]:
        return self.get("earnings-surprises/" + symbol, limit=limit)

    def historical_price(self, symbol: str, limit: int = 5000) -> dict[str, Any]:
        return self.get("historical-price-full/" + symbol, timeseries=limit)

    def snapshot(self, symbol: str) -> dict[str, Any]:
        """Collect the secondary FMP package. Missing endpoints remain explicit failures."""
        calls = {
            "profile": self.profile(symbol),
            "quote": self.quote(symbol),
            "income_statement": self.income_statement(symbol),
            "balance_sheet": self.balance_sheet(symbol),
            "cash_flow": self.cash_flow(symbol),
            "ratios": self.ratios(symbol),
            "key_metrics": self.key_metrics(symbol),
            "enterprise_values": self.enterprise_values(symbol),
            "analyst_estimates": self.analyst_estimates(symbol),
            "grades": self.grades(symbol),
            "grades_historical": self.grades_historical(symbol),
            "price_target_consensus": self.price_target_consensus(symbol),
            "price_target": self.price_target(symbol),
            "earnings_surprises": self.earnings_surprises(symbol),
            "historical_price": self.historical_price(symbol),
        }
        return {"ticker": symbol, "retrieved_at": _now_iso(), "data": calls}
