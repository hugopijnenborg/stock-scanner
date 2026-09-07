-- Actual production table used by scripts/save_alerts_supabase.py,
-- scripts/evaluate_alerts.py and app/api/history/route.js.
--
-- The previous supabase_schema.sql (public.alerts) and supabase/schema.sql
-- (stocks/scans/alerts/alert_outcomes) did NOT match what the code writes
-- to or reads from Supabase. Neither was referenced anywhere. This file
-- replaces both with the schema that reflects reality, so it can actually
-- be used to recreate the table from scratch.

create extension if not exists pgcrypto;

create table if not exists public.stock_scanner_alerts (
  id uuid primary key default gen_random_uuid(),

  -- identity
  ticker text not null,
  company_name text,

  -- entry (set once, never overwritten after creation)
  alert_timestamp timestamptz not null,
  entry_timestamp timestamptz not null,
  alert_price numeric not null,
  initial_score numeric,

  -- live-updated while the alert is active (60-day cooldown window)
  score numeric,
  peak_score numeric,
  peak_score_at timestamptz,

  -- score components at alert time (context only, see model.py score_row)
  trader_score numeric,
  technical_score numeric,
  fundamental_score numeric,

  -- lifecycle
  status text not null default 'PENDING', -- PENDING | WIN | LOSS
  evaluated_at timestamptz,

  -- forward performance, filled in by scripts/evaluate_alerts.py
  price_1d numeric, return_1d numeric, price_1d_at timestamptz,
  price_5d numeric, return_5d numeric, price_5d_at timestamptz,
  price_10d numeric, return_10d numeric, price_10d_at timestamptz,
  price_20d numeric, return_20d numeric, price_20d_at timestamptz,
  price_30d numeric, return_30d numeric, price_30d_at timestamptz,
  price_60d numeric, return_60d numeric, price_60d_at timestamptz,

  max_gain numeric,
  max_drawdown numeric,
  max_gain_60d numeric,
  max_drawdown_60d numeric,

  hit_5pct boolean,
  hit_10pct boolean,
  hit_20pct boolean,
  hit_30pct boolean,

  created_at timestamptz not null default now()
);

create index if not exists stock_scanner_alerts_ticker_idx on public.stock_scanner_alerts (ticker);
create index if not exists stock_scanner_alerts_status_idx on public.stock_scanner_alerts (status);
create index if not exists stock_scanner_alerts_alert_timestamp_idx on public.stock_scanner_alerts (alert_timestamp desc);

-- One row is one trade event: created when a ticker first alerts, then
-- peak_score is updated on repeat 80+ scans within a 60-day cooldown
-- (see scripts/save_alerts_supabase.py). evaluate_alerts.py fills the
-- forward-return columns and flips status from PENDING once return_60d
-- is known.
