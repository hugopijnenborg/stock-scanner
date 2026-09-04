from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Keep the existing dashboard layout intact. Only separate the initial page-load
# state from the scan-in-progress state so the manual scan button is not tied to
# data loading.
page = ROOT / "app" / "page.js"
s = page.read_text(encoding="utf-8")
replacements = [
    (
        "import { useEffect, useMemo, useState } from 'react';",
        "import { useEffect, useMemo, useRef, useState } from 'react';",
    ),
    (
        "const [data, setData] = useState(null), [loading, setLoading] = useState(true), [error, setError] = useState(''), [query, setQuery] = useState(''), [showAll, setShowAll] = useState(false), [selected, setSelected] = useState(null), [scanMessage, setScanMessage] = useState('');",
        "const [data, setData] = useState(null), [loading, setLoading] = useState(true), [scanning, setScanning] = useState(false), [error, setError] = useState(''), [query, setQuery] = useState(''), [showAll, setShowAll] = useState(false), [selected, setSelected] = useState(null), [scanMessage, setScanMessage] = useState('');",
    ),
    (
        "  async function startScan() {\n    if (loading) return;\n    const previous = data?.generated_at || '';\n    setLoading(true); setError(''); setScanMessage('Scan wordt gestart...');",
        "  async function startScan() {\n    if (scanning) return;\n    const previous = data?.generated_at || '';\n    setScanning(true); setError(''); setScanMessage('Scan wordt gestart...');",
    ),
    (
        "    finally { setLoading(false); }\n  }\n\n  useEffect(() => { load(); }, []);",
        "    finally { setScanning(false); }\n  }\n\n  useEffect(() => { load(); }, []);",
    ),
    (
        "<button className=\"refresh primary\" onClick={startScan} disabled={loading}><RefreshCw size={15} /> {loading ? (scanMessage ? 'Scannen...' : 'Laden...') : 'Nieuwe scan'}</button>",
        "<button className=\"refresh primary\" onClick={startScan} disabled={loading || scanning}><RefreshCw size={15} /> {scanning ? 'Scannen...' : loading ? 'Laden...' : 'Nieuwe scan'}</button>",
    ),
]
for old, new in replacements:
    if old not in s:
        raise SystemExit(f"Expected page.js text not found: {old[:80]}")
    s = s.replace(old, new, 1)
page.write_text(s, encoding="utf-8")

# The live confirmation only needs a few recent sessions. Three days still gives
# enough 15-minute bars for the 21-bar intraday volume baseline while cutting a
# large amount of unnecessary history from every scan.
scanner = ROOT / "scanner.py"
s = scanner.read_text(encoding="utf-8")
old = 'intraday = download_intraday(tickers, period="10d", interval="15m")'
new = 'intraday = download_intraday(tickers, period="3d", interval="15m")'
if old not in s:
    raise SystemExit("Expected scanner intraday line not found")
s = s.replace(old, new, 1)
old = 'intraday_benchmarks = download_intraday_benchmarks(period="10d", interval="15m")'
new = 'intraday_benchmarks = download_intraday_benchmarks(period="3d", interval="15m")'
if old not in s:
    raise SystemExit("Expected benchmark intraday line not found")
s = s.replace(old, new, 1)
scanner.write_text(s, encoding="utf-8")

print("Applied manual scan state fix and 3-day intraday optimization.")
