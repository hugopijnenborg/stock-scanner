import { NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';
export const revalidate = 0;

// De scan wordt berekend door de n8n-workflow "Live scan" en staat in Supabase
// (tabel scanner_scan_latest, 1 rij). Deze route leest die rij en rekent niets opnieuw uit.
// Handmatig uitgesloten aandelen: worden in de app niet getoond (de scan zelf weet hier niets van).
const EXCLUDED_TICKERS = ['KEYS'];
const ALERT_THRESHOLD = 80;
const WATCH_THRESHOLD = 65;

function numberOrNull(value) {
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

function normalizeResult(row) {
  const overall = numberOrNull(row.overall_score);
  return {
    ...row,
    overall_score: overall,
    technical_score: numberOrNull(row.technical_score),
    fundamental_score: numberOrNull(row.fundamental_score),
    signal: row.signal || 'DATA_INCOMPLETE',
  };
}


const NOISE = /purchased by|sold by|acquired by|bought by|position in|stake in|(cuts?|trims?|raises?|boosts?|lifts?|sells?|buys?|adds?|lowers?)\s+(its\s+)?(holdings|stake|position|shares)|holdings\s+(cut|lifted|raised|trimmed|boosted)|lead plaintiff|class action|securities (fraud|litigation)|law (firm|offices)|investors (who|should|that)|zacks|gf (score|value)|gurufocus|partner program/i;

async function attachCompanyInfo(data, url, key) {
  try {
    const tickers = [...new Set((data.results || []).filter((r) => r.dip_signal).map((r) => r.ticker))];
    if (!tickers.length) return;
    const list = tickers.map(encodeURIComponent).join(',');
    const headers = { apikey: key, Authorization: `Bearer ${key}` };
    const [nRes, aRes] = await Promise.all([
      fetch(`${url}/rest/v1/scanner_company_news?select=ticker,fetched_at,profile,news,press&ticker=in.(${list})`, { headers, cache: 'no-store' }),
      fetch(`${url}/rest/v1/scanner_alerts?select=ticker,alert_timestamp,alert_price&status=eq.PENDING&archived=eq.false&ticker=in.(${list})&order=alert_timestamp.desc`, { headers, cache: 'no-store' }),
    ]);
    const news = nRes.ok ? await nRes.json() : [];
    const alerts = aRes.ok ? await aRes.json() : [];
    const byNews = Object.fromEntries(news.map((x) => [x.ticker, x]));
    const byAlert = {};
    for (const a of alerts) if (!byAlert[a.ticker]) byAlert[a.ticker] = a;
    for (const r of data.results) {
      if (!r.dip_signal) continue;
      const n = byNews[r.ticker];
      if (n) {
        r.company_info = {
          fetched_at: n.fetched_at,
          profile: n.profile || null,
          news: (n.news || []).filter((x) => !NOISE.test(x.title || '')),
          press: (n.press || []).filter((x) => !NOISE.test(x.title || '')),
        };
      }
      const a = byAlert[r.ticker];
      if (a) r.alert_info = { since: a.alert_timestamp, price: numberOrNull(a.alert_price) };
    }
  } catch (e) { /* aanvullende info is optioneel */ }
}

export async function GET() {
  const url = (process.env.SUPABASE_URL || '').replace(/\/$/, '');
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY || '';
  if (!url || !key) {
    return NextResponse.json({ error: 'Supabase environment variables ontbreken.' }, { status: 500 });
  }

  try {
    const response = await fetch(`${url}/rest/v1/scanner_scan_latest?select=generated_at,payload&id=eq.1`, {
      headers: { apikey: key, Authorization: `Bearer ${key}` },
      cache: 'no-store',
    });
    if (!response.ok) {
      return NextResponse.json({ error: `Supabase gaf HTTP ${response.status}` }, { status: 502 });
    }
    const rows = await response.json();
    if (!rows.length) {
      return NextResponse.json({ error: 'Er is nog geen scan beschikbaar.' }, { status: 404 });
    }
    const data = rows[0].payload;
    data.generated_at = rows[0].generated_at;
    data.scan_generated_at = rows[0].generated_at;
    if (Array.isArray(data.results)) {
      data.results = data.results.map(normalizeResult);
      data.results.sort((a, b) => (numberOrNull(b.overall_score) ?? -1) - (numberOrNull(a.overall_score) ?? -1));
      data.alert_count = data.results.filter((row) => row.signal === 'ALERT').length;
      data.top_score = data.results.length ? data.results[0].overall_score : null;
    }
    if (Array.isArray(data.results)) data.results = data.results.filter((r) => !EXCLUDED_TICKERS.includes(r.ticker));
    await attachCompanyInfo(data, url, key);
    data.alert_threshold = data.alert_threshold ?? ALERT_THRESHOLD;
    data.watch_threshold = data.watch_threshold ?? WATCH_THRESHOLD;

    return NextResponse.json(data, { headers: { 'Cache-Control': 'no-store, max-age=0' } });
  } catch (error) {
    return NextResponse.json(
      { error: `Kan scan data niet laden: ${error instanceof Error ? error.message : 'onbekende fout'}` },
      { status: 500 }
    );
  }
}
