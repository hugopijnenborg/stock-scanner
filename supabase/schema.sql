create extension if not exists pgcrypto;

create table if not exists stocks (
  ticker text primary key,
  company_name text,
  sector text,
  market_cap numeric,
  active boolean not null default true,
  updated_at timestamptz not null default now()
);

create table if not exists scans (
  id uuid primary key default gen_random_uuid(),
  scanned_at timestamptz not null default now(),
  universe_size integer not null,
  alert_count integer not null default 0,
  top_score numeric,
  model_version integer
);

create table if not exists alerts (
  id uuid primary key default gen_random_uuid(),
  scan_id uuid references scans(id) on delete cascade,
  ticker text not null references stocks(ticker),
  scanned_at timestamptz not null default now(),
  price numeric not null,
  setup_type text not null,
  overall_score numeric not null,
  trader_similarity_score numeric,
  technical_score numeric,
  reversal_trigger numeric,
  return_5d numeric,
  return_20d numeric,
  rsi_14 numeric,
  volume_ratio numeric,
  status text not null default 'open'
);

create table if not exists alert_outcomes (
  id uuid primary key default gen_random_uuid(),
  alert_id uuid not null references alerts(id) on delete cascade,
  measured_at timestamptz not null default now(),
  return_1d numeric,
  return_3d numeric,
  return_5d numeric,
  return_10d numeric,
  return_20d numeric,
  max_gain_20d numeric,
  max_drawdown_20d numeric
);

create table if not exists trader_entries (
  id uuid primary key default gen_random_uuid(),
  trade_date date not null,
  ticker text not null,
  price numeric not null,
  entry_type text,
  strategy text,
  reason text,
  source_confidence text
);

create index if not exists alerts_scanned_at_idx on alerts(scanned_at desc);
create index if not exists alerts_ticker_idx on alerts(ticker);
create index if not exists alert_outcomes_alert_id_idx on alert_outcomes(alert_id);

alter table stocks enable row level security;
alter table scans enable row level security;
alter table alerts enable row level security;
alter table alert_outcomes enable row level security;
alter table trader_entries enable row level security;

create policy "public read stocks" on stocks for select using (true);
create policy "public read scans" on scans for select using (true);
create policy "public read alerts" on alerts for select using (true);
create policy "public read outcomes" on alert_outcomes for select using (true);
create policy "public read trader entries" on trader_entries for select using (true);
