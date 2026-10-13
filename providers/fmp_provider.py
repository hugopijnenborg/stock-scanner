from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import requests

# De oude /api/v3/ endpoints geven "Legacy Endpoint" (403). FMP gebruikt nu /stable/.
BASE_URL = "https://financialmodelingprep.com/stable"


class FMPError(RuntimeError):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class FMPProvider:
    """Dunne client voor Financial Modeling Prep (/stable/ API).

    Elke methode geeft {"source", "endpoint", "retrieved_at", "data"} terug.
    Een ontbrekend endpoint of ontbrekend abonnement geeft FMPError met de
    HTTP-status; er wordt nooit stilletjes een lege waarde teruggegeven.
    """

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
            # Key nooit in foutmelding laten lekken.
            raise FMPError(f"FMP {response.status_code} op {endpoint}: {response.text[:200]}", response.status_code)
        payload = response.json()
        if isinstance(payload, dict) and payload.get("Error Message"):
            raise FMPError(f"FMP {endpoint}: {str(payload['Error Message'])[:200]}")
        return {"source": "fmp", "endpoint": endpoint, "retrieved_at": _now_iso(), "data": payload}

    # --- bedrijf & koers
    def profile(self, symbol: str):
        return self.get("profile", symbol=symbol)

    def quote(self, symbol: str):
        return self.get("quote", symbol=symbol)

    def stock_peers(self, symbol: str):
        return self.get("stock-peers", symbol=symbol)

    # --- financials
    def income_statement(self, symbol: str, period: str = "quarter", limit: int = 8):
        return self.get("income-statement", symbol=symbol, period=period, limit=limit)

    def balance_sheet(self, symbol: str, period: str = "quarter", limit: int = 8):
        return self.get("balance-sheet-statement", symbol=symbol, period=period, limit=limit)

    def cash_flow(self, symbol: str, period: str = "quarter", limit: int = 8):
        return self.get("cash-flow-statement", symbol=symbol, period=period, limit=limit)

    def financial_growth(self, symbol: str, period: str = "quarter", limit: int = 8):
        return self.get("financial-growth", symbol=symbol, period=period, limit=limit)

    def key_metrics_ttm(self, symbol: str):
        return self.get("key-metrics-ttm", symbol=symbol)

    def ratios_ttm(self, symbol: str):
        return self.get("ratios-ttm", symbol=symbol)

    def enterprise_values(self, symbol: str, period: str = "quarter", limit: int = 8):
        return self.get("enterprise-values", symbol=symbol, period=period, limit=limit)

    # --- verwachtingen & analisten
    def analyst_estimates(self, symbol: str, period: str = "annual", limit: int = 10):
        return self.get("analyst-estimates", symbol=symbol, period=period, page=0, limit=limit)

    def price_target_summary(self, symbol: str):
        return self.get("price-target-summary", symbol=symbol)

    def price_target_consensus(self, symbol: str):
        return self.get("price-target-consensus", symbol=symbol)

    def price_target_news(self, symbol: str, limit: int = 50):
        return self.get("price-target-news", symbol=symbol, page=0, limit=limit)

    def grades(self, symbol: str, limit: int = 100):
        return self.get("grades", symbol=symbol, limit=limit)

    def grades_historical(self, symbol: str, limit: int = 24):
        return self.get("grades-historical", symbol=symbol, limit=limit)

    def grades_consensus(self, symbol: str):
        return self.get("grades-consensus", symbol=symbol)

    def ratings_snapshot(self, symbol: str):
        return self.get("ratings-snapshot", symbol=symbol)

    # --- earnings
    def earnings(self, symbol: str, limit: int = 12):
        return self.get("earnings", symbol=symbol, limit=limit)

    def earnings_calendar(self, date_from: str, date_to: str):
        return self.get("earnings-calendar", **{"from": date_from, "to": date_to})

    # --- sector
    def sector_pe_snapshot(self, date: str):
        return self.get("sector-pe-snapshot", date=date)
