# Provider setup

The scanner now uses two external providers during the data-completeness phase:

- Finnhub: primary source
- Financial Modeling Prep (FMP): secondary source for missing/secondary coverage

## Environment variables

Set these locally or in the deployment environment. Never commit the keys.

```text
FINNHUB_API_KEY=...
FMP_API_KEY=...
```

A template is available in `.env.example`.

## First test

The first probe intentionally tests only the 10-stock validation set:

AAOI, CRWV, NVDA, AMD, MU, SOFI, PLTR, GOOGL, NKE, WDC

Run:

```bash
python scripts/probe_providers.py
```

The result is written to `data/provider_probe.json` and reports whether each required provider endpoint is available for each ticker.

## Important

This probe does not change the production scoring model. It is only a data-source validation step.

Do not treat a missing provider field as zero. A missing field remains missing until the metric is either derived from valid raw data or supplied by the secondary provider.
