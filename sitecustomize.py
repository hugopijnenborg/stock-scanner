"""Runtime hooks for MarketIntel.

The scanner keeps its existing data collection pipeline. This hook adds the
new opportunity decision layer after the existing scan and also makes the
Oanor fallback available to the function imported by scanner.py itself.
"""

import os

try:
    import analyst
    from oanor_fallback import enrich_missing_targets

    _original_download_analyst_data = analyst.download_analyst_data

    def _download_analyst_data_with_oanor(tickers):
        data = _original_download_analyst_data(tickers)
        if os.getenv("OANOR_API_KEY"):
            return enrich_missing_targets(data)
        return data

    analyst.download_analyst_data = _download_analyst_data_with_oanor

    # scanner.py imported the function directly, so patch that reference too.
    try:
        import scanner
        scanner.download_analyst_data = _download_analyst_data_with_oanor
    except Exception:
        pass
except Exception:
    # Analyst fallback is optional. Never block the scanner when it is broken.
    pass

try:
    import scanner as _scanner
    from opportunity_engine import apply_opportunity_engine

    _original_scan = _scanner.scan

    def _scan_with_opportunity_engine(limit=1000, top_n=1000):
        frame = _original_scan(limit, top_n)
        return apply_opportunity_engine(frame)

    _scanner.scan = _scan_with_opportunity_engine
except Exception:
    # Keep the old scanner available if the new decision layer has a problem.
    pass
