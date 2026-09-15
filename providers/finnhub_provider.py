from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import requests


BASE_URL = "https://finnhub.io/api/v1"


class FinnhubError(RuntimeError):
    pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any) -> Any:
    if isinstance(value, float) and value != value:
        return None
    return value


class FinnhubProvider:
    """Thin Finnhub client. Raw responses are kept intact for reproducibility."""

    def __init__(self, api_key: str | None = None, timeout: int = 30):
        self.api_key = api_key or os.getenv("FINNHUB_API_KEY")
        if not self.api_key:
            raise FinnhubError("FINNHUB_API_KEY is not configured")
        self.timeout = timeout
        self.session = requests.Session()

    def get(self, endpoint: str, **params: Any) -> dict[str, Any]:
        params["token"] = self.api_key
        url = f"{BASE_URL}/{endpoint.lstrip('/')}"
        response = self.session.get(url, params=params, timeout=self.timeout)
        if response.status_code != 200:
            raise FinnhubError(f"Finnhub {response.status_code}: {response.text[:300]}")
        payload = response.json()
        return {
            "source": "finnhub",
            "endpoint": endpoint,
            "retrieved_at": _now_iso(),
            "data": payload,
        }

    def quote(self, symbol: str) -> dict[str, Any]:
        return self.get("quote", symbol=symbol)

    def candles(self, symbol: str, start: int, end: int, resolution: str = "D") -> dict[str, Any]:
        return self.get("stock/candle", symbol=symbol, resolution=resolution, _from=start, to=end)

    def profile(self, symbol: str) -> dict[str, Any]:
        return self.get("stock/profile2", symbol=symbol)

    def metrics(self, symbol: str, metric: str = "all") -> dict[str, Any]:
        return self.get("stock/metric", symbol=symbol, metric=metric)

    def financials_reported(self, symbol: str, freq: str = "annual") -> dict[str, Any]:
        return self.get("stock/financials-reported", symbol=symbol, freq=freq)

    def earnings(self, symbol: str) -> dict[str, Any]:
        return self.get("stock/earnings", symbol=symbol)

    def earnings_surprises(self, symbol: str) -> dict[str, Any]:
        return self.get("stock/earnings-surprises", symbol=symbol)

    def eps_estimate(self, symbol: str) -> dict[str, Any]:
        return self.get("stock/eps-estimate", symbol=symbol)

    def revenue_estimate(self, symbol: str) -> dict[str, Any]:
        return self.get("stock/revenue-estimate", symbol=symbol)

    def ebitda_estimate(self, symbol: str) -> dict[str, Any]:
        return self.get("stock/ebitda-estimate", symbol=symbol)

    def recommendations(self, symbol: str) -> dict[str, Any]:
        return self.get("stock/recommendation", symbol=symbol)

    def price_target(self, symbol: str) -> dict[str, Any]:
        return self.get("stock/price-target", symbol=symbol)

    def upgrades_downgrades(self, symbol: str, start: str | None = None, end: str | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {"symbol": symbol}
        if start:
            params["from"] = start
        if end:
            params["to"] = end
        return self.get("stock/upgrade-downgrade", **params)

    def peers(self, symbol: str) -> dict[str, Any]:
        return self.get("stock/peers", symbol=symbol)

    def news(self, symbol: str, start: str, end: str) -> dict[str, Any]:
        return self.get("company-news", symbol=symbol, _from=start, to=end)

    def snapshot(self, symbol: str, candle_start: int, candle_end: int) -> dict[str, Any]:
        """Collect the minimum raw Finnhub package for one ticker."""
        calls = {
            "profile": self.profile(symbol),
            "quote": self.quote(symbol),
            "metrics": self.metrics(symbol),
            "financials_reported": self.financials_reported(symbol),
            "earnings": self.earnings(symbol),
            "earnings_surprises": self.earnings_surprises(symbol),
            "eps_estimate": self.eps_estimate(symbol),
            "revenue_estimate": self.revenue_estimate(symbol),
            "ebitda_estimate": self.ebitda_estimate(symbol),
            "recommendations": self.recommendations(symbol),
            "price_target": self.price_target(symbol),
            "upgrades_downgrades": self.upgrades_downgrades(symbol),
            "peers": self.peers(symbol),
            "candles": self.candles(symbol, candle_start, candle_end),
        }
        return {"ticker": symbol, "retrieved_at": _now_iso(), "data": calls}
