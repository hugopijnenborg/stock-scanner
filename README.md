# Stock Scanner

Dashboard (Next.js, Vercel) voor het dip-model 6.0.

- **Scan en regels:** draaien in n8n (workflow "Stock Scanner - Live scan"), resultaten in Supabase.
- **Dashboard:** leest alleen uit Supabase via `app/api/*`.
- **Pagina's:** Scanner, Portfolio, Alert history, Performance, Model validation.
- **archief/:** trades van de Discord-trader waarop het model oorspronkelijk is gebaseerd.

Het oude Python-systeem staat in de git-geschiedenis (commit voor de opruiming).
