"""Earnings context: is the drawdown contradicted by the company's own results?

A stock down 30% since a quarter it beat is a different proposition from one
down 30% since a quarter it missed. That distinction is objective and already
downloaded on every scan, so it costs nothing to use.

It is deliberately a bounded adjustment rather than a fourth weighted
component. The data exists for roughly 140 of 230 tickers; a weighted
component would silently renormalise the other three for the ~90 without it,
which is the same defect that made the stated 30/35/35 weights untrue. As a
capped delta, missing data simply means no adjustment, and the adjustment can
never turn a mediocre setup into an alert on its own.

Headlines are not used. `recent_news` carries titles only, and scoring them
would need sentiment analysis on every ticker every scan -- noisy, and largely
redundant: headlines like "X Falls More Steeply Than Broader Market" restate
the drawdown the technical score already measures.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

MAX_ADJUSTMENT = 5.0

# Beating is the norm, not the exception: across the live universe the median
# surprise is +8.1% and only 19 of 139 companies missed. Large caps guide
# conservatively, so scoring any positive surprise as good would hand almost
# every ticker free points. Neutral therefore sits at the typical beat, and a
# +1% "beat" reads as the below-average result it is.
TYPICAL_SURPRISE = 0.08
STRONG_BEAT = 0.23   # roughly the 85th percentile
STRONG_MISS = -0.07  # roughly the 15th percentile

# Reported surprises include values like -640% and +466%, where a near-zero
# expected EPS makes the percentage meaningless. Clamp before scaling.
SURPRISE_FLOOR = -0.60
SURPRISE_CAP = 1.00

# The last report stays the market's reference point until the next one, so the
# signal holds for most of a quarter and then fades rather than expiring.
RECENT_EARNINGS_DAYS = 120

# Buying immediately before a report is a coin flip, not a setup.
EARNINGS_IMMINENT_DAYS = 7


def _parse(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _number(value: Any) -> float | None:
    try:
        if value is None:
            return None
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def earnings_adjustment(row: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
    """Return a bounded score delta plus the reasons behind it.

    Positive means the company's own results argue the sell-off is overdone.
    Negative means the results support it, or a report is about to land.
    """
    now = now or datetime.now(timezone.utc)
    reasons: list[str] = []
    delta = 0.0

    surprise = _number(row.get("last_earnings_surprise_pct"))
    last_date = _parse(row.get("last_earnings_date"))

    if surprise is not None:
        surprise = max(SURPRISE_FLOOR, min(SURPRISE_CAP, surprise))
        if surprise >= TYPICAL_SURPRISE:
            span = STRONG_BEAT - TYPICAL_SURPRISE
            strength = min(1.0, (surprise - TYPICAL_SURPRISE) / span) if span > 0 else 0.0
            direction = 1.0
            label = f"Earnings beat {surprise * 100:.1f}% (boven de gebruikelijke {TYPICAL_SURPRISE * 100:.0f}%)"
        else:
            span = TYPICAL_SURPRISE - STRONG_MISS
            strength = min(1.0, (TYPICAL_SURPRISE - surprise) / span) if span > 0 else 0.0
            direction = -1.0
            label = (
                f"Earnings miss {surprise * 100:.1f}%" if surprise < 0
                else f"Earnings beat {surprise * 100:.1f}% (onder de gebruikelijke {TYPICAL_SURPRISE * 100:.0f}%)"
            )

        # Fade the signal as the report ages out of relevance.
        recency = 1.0
        if last_date is not None:
            age_days = max(0.0, (now - last_date).total_seconds() / 86400.0)
            recency = max(0.0, 1.0 - age_days / RECENT_EARNINGS_DAYS)

        contribution = direction * strength * recency * MAX_ADJUSTMENT
        if abs(contribution) >= 0.1:
            delta += contribution
            reasons.append(label)

    next_date = _parse(row.get("next_earnings_date"))
    if next_date is not None:
        days_out = (next_date - now).total_seconds() / 86400.0
        if 0 <= days_out <= EARNINGS_IMMINENT_DAYS:
            delta -= MAX_ADJUSTMENT / 2
            reasons.append(f"Earnings over {days_out:.0f} dagen")

    delta = max(-MAX_ADJUSTMENT, min(MAX_ADJUSTMENT, delta))
    return {
        "earnings_adjustment": round(delta, 2),
        "earnings_context": reasons,
        "earnings_data_available": surprise is not None or next_date is not None,
    }
