"""Guards the Market Scanner schedule.

GitHub Actions cron is always UTC and silently ignores a `timezone:` key, so a
cron written as if it were Dutch local time fires hours off. The crons here
cover the union of both Dutch offsets; scripts/market_hours_guard.py is
timezone aware and narrows that union to the exact 15:45-22:00 window.
"""

from __future__ import annotations

import re
from datetime import datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

REPO = Path(__file__).resolve().parents[1]
WORKFLOWS = REPO / ".github" / "workflows"
MARKET_SCAN = WORKFLOWS / "market_scan_local.yml"

AMSTERDAM = ZoneInfo("Europe/Amsterdam")
UTC = ZoneInfo("UTC")
WINDOW_START = time(15, 45)
WINDOW_END = time(22, 0)

# One weekday well inside summer time (CEST, UTC+2) and one well inside
# winter time (CET, UTC+1).
SUMMER_DAY = datetime(2026, 7, 15, tzinfo=AMSTERDAM).date()
WINTER_DAY = datetime(2026, 12, 15, tzinfo=AMSTERDAM).date()


def cron_lines(path: Path) -> list[str]:
    return re.findall(r"^\s*-\s*cron:\s*'([^']+)'", path.read_text(encoding="utf-8"), re.M)


def expand_field(field: str, lo: int, hi: int) -> set[int]:
    values: set[int] = set()
    for part in field.split(","):
        if part == "*":
            values.update(range(lo, hi + 1))
        elif "-" in part:
            start, end = part.split("-")
            values.update(range(int(start), int(end) + 1))
        else:
            values.add(int(part))
    return values


def utc_trigger_times(crons: list[str]) -> set[time]:
    """Every UTC time these weekday crons fire."""
    fires: set[time] = set()
    for expression in crons:
        minute, hour, dom, month, dow = expression.split()
        assert dom == "*" and month == "*", f"unexpected cron shape: {expression}"
        assert expand_field(dow, 0, 6) == {1, 2, 3, 4, 5}, f"{expression} is not weekdays-only"
        for h in sorted(expand_field(hour, 0, 23)):
            for m in sorted(expand_field(minute, 0, 59)):
                fires.add(time(h, m))
    return fires


def required_local_slots() -> list[time]:
    slots = []
    cursor = datetime.combine(SUMMER_DAY, WINDOW_START)
    end = datetime.combine(SUMMER_DAY, WINDOW_END)
    while cursor <= end:
        slots.append(cursor.time())
        cursor += timedelta(minutes=15)
    return slots


def guard_allows(moment: datetime) -> bool:
    """Same rule as scripts/market_hours_guard.py."""
    local = moment.astimezone(AMSTERDAM)
    return local.weekday() < 5 and WINDOW_START <= local.time() <= WINDOW_END


def test_no_workflow_uses_the_unsupported_timezone_key():
    for workflow in sorted(WORKFLOWS.glob("*.yml")):
        for line in workflow.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            assert not stripped.startswith("timezone:"), (
                f"{workflow.name} uses a `timezone:` key. GitHub Actions cron is "
                "always UTC and ignores it, so the workflow fires at the wrong hour."
            )


def test_scanner_covers_every_quarter_hour_in_the_dutch_window():
    fires = utc_trigger_times(cron_lines(MARKET_SCAN))
    required = required_local_slots()

    for day in (SUMMER_DAY, WINTER_DAY):
        allowed_local = sorted(
            moment.astimezone(AMSTERDAM).time()
            for moment in (
                datetime.combine(day, fire, tzinfo=UTC) for fire in fires
            )
            if guard_allows(moment)
        )
        assert allowed_local == required, (
            f"on {day} the scanner runs at {allowed_local} but should run at {required}"
        )


def test_first_scan_is_1545_and_last_scan_is_2200():
    required = required_local_slots()
    assert required[0] == time(15, 45)
    assert required[-1] == time(22, 0)
    assert len(required) == 26


def test_guard_rejects_moments_outside_the_window():
    assert not guard_allows(datetime(2026, 7, 15, 15, 30, tzinfo=AMSTERDAM))
    assert guard_allows(datetime(2026, 7, 15, 15, 45, tzinfo=AMSTERDAM))
    assert guard_allows(datetime(2026, 7, 15, 22, 0, tzinfo=AMSTERDAM))
    assert not guard_allows(datetime(2026, 7, 15, 22, 15, tzinfo=AMSTERDAM))
    assert not guard_allows(datetime(2026, 7, 18, 16, 0, tzinfo=AMSTERDAM))  # Saturday
