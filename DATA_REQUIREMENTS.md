# Data requirements for scoring model v1.0

The scanner must never silently score a stock with fabricated or unverified inputs.

## Primary data policy

- Market/OHLCV: one primary historical market feed. Technical, momentum, volume, market/sector and risk metrics are derived locally from the same normalized price history.
- Fundamentals: point-in-time/as-reported source. Store both `period_end` and `available_from`.
- Earnings estimates/revisions: historical estimate source. Store the observation timestamp and the estimate/revision date.
- Analyst ratings/targets/revisions: historical analyst source. Store observation timestamp and event timestamp.
- SEC/company filings may be retained as a validation source for fundamentals, but not mixed into a metric silently.

## Completeness rule

A stock is eligible for the new score only when every applicable metric has a valid value and every external point-in-time metric has an `available_from` timestamp at or before the score date.

`missing`, `invalid`, and `point_in_time_unverified` are hard blockers. We do not replace them with zero, median, neutral, or a value from today's snapshot.

## Derived vs external metrics

### Derived from normalized OHLCV

Price action, momentum, volume, market/sector and risk metrics can be calculated deterministically. This includes SMA100, trend structure, support/resistance, consolidation, gaps, candle structure, OBV, accumulation/distribution, money flow, downside volatility, maximum drawdown and beta once the underlying history is present.

### External point-in-time metrics

Fundamentals, valuation inputs that depend on reported financials, earnings estimates/revisions, guidance, analyst consensus, targets and analyst revisions require dated observations.

## Required storage metadata

Every external observation must carry:

- ticker
- metric
- value
- source
- observed_at
- available_from
- period_end where applicable
- source_version or retrieval identifier where available

This prevents today's data from leaking into historical validation.

## Operational rule

The scanner should fail closed for the new model: if the completeness audit is not 100%, no overall score or alert is produced for that ticker. The audit must report the exact missing metrics and source category.
