# Stock Scanner

Market scanner based on the curated stock universe, technical setups, trader-pattern similarity and fundamental company data.

The dashboard is intended for research and paper testing. Fundamental data is included in the scan output and is used as a separate scoring layer. Historical backtesting remains the next validation step before treating scores as predictive.

Analyst integrations are configured through Vercel environment variables and are refreshed through the scanner cache.

<!-- production redeploy sync: keep deployment on main aligned with the existing production code -->
