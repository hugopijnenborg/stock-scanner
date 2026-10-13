import { NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';
export const revalidate = 0;

// De scan wordt berekend door de n8n-workflow "Live scan" en staat in Supabase
// (tabel scanner_scan_latest, 1 rij). Deze route leest die rij en rekent niets opnieuw uit.
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
