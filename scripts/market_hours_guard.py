from datetime import datetime, time
from zoneinfo import ZoneInfo

# User-requested scan window in Dutch local time.
# Scheduled scans start at 15:45 and run through 22:00 Europe/Amsterdam.
TZ = ZoneInfo('Europe/Amsterdam')
START = time(15, 45)
END = time(22, 0)

now = datetime.now(TZ)
allowed = now.weekday() < 5 and START <= now.time() <= END
print(f'Local time: {now:%Y-%m-%d %H:%M:%S %Z}')
print(f'Requested scan window: {START.strftime("%H:%M")}-{END.strftime("%H:%M")} Europe/Amsterdam')
if not allowed:
    print('Outside scan window. Stopping this scheduled run.')
    raise SystemExit(78)
print('Inside scan window. Starting market scan.')
