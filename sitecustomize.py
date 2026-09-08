"""Optional runtime hook for the MarketIntel scanner.

Python imports sitecustomize automatically when it is on sys.path. We keep the
hook tiny and only activate it when OANOR_API_KEY is present, so normal tests
and local tooling are unchanged when the key is absent.
"""

import os

if os.getenv("OANOR_API_KEY"):
    try:
        import analyst
        from oanor_fallback import enrich_missing_targets

        _original_download_analyst_data = analyst.download_analyst_data

        def _download_analyst_data_with_oanor(tickers):
            data = _original_download_analyst_data(tickers)
            return enrich_missing_targets(data)

        analyst.download_analyst_data = _download_analyst_data_with_oanor
    except Exception:
        # Never let the optional fallback prevent the scanner from running.
        pass
