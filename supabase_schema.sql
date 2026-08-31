create table if not exists public.alerts (
  id uuid primary key default gen_random_uuid(),
  ticker text not null,
  company_name text,
  alert_timestamp timestamptz not null,
  alert_price numeric,
  score numeric,
  trader_score numeric,
  technical_score numeric,
  fundamental_score numeric,
  price_1d numeric,
  price_5d numeric,
  price_10d numeric,
  price_20d numeric,
  return_1d numeric,
  return_5d numeric,
  return_10d numeric,
  return_20d numeric,
  max_gain numeric,
  max_drawdown numeric,
  hit_5pct boolean,
  hit_10pct boolean,
  hit_20pct boolean,
  hit_30pct boolean,
  status text not null default 'PENDING',
  created_at timestamptz not null default now()
);
create unique index if not exists alerts_ticker_timestamp_idx on public.alerts(ticker, alert_timestamp);
create index if not exists alerts_score_idx on public.alerts(score);
create index if not exists alerts_timestamp_idx on public.alerts(alert_timestamp desc);
