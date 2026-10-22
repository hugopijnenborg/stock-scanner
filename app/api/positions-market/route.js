import { NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';
export const revalidate = 0;

// Lichte variant van /api/scan: alleen de scanrijen van de gevraagde tickers (voor de meldingen bij posities).
export async function GET(request) {
  const url = (process.env.SUPABASE_URL || '').replace(/\/$/, '');
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY || '';
  if (!url || !key) return NextResponse.json({ error: 'Supabase environment variables ontbreken.' }, { status: 500 });
  const wanted = new Set(
    String(new URL(request.url).searchParams.get('tickers') || '')
      .split(',').map((x) => x.trim().toUpperCase()).filter((x) => /^[A-Z0-9.\-]{1,10}$/.test(x)).slice(0, 80)
  );
  try {
    const res = await fetch(`${url}/rest/v1/scanner_scan_latest?select=generated_at,payload&id=eq.1`, {
      headers: { apikey: key, Authorization: `Bearer ${key}` }, cache: 'no-store',
    });
    if (!res.ok) return NextResponse.json({ error: `Supabase gaf HTTP ${res.status}` }, { status: 502 });
    const rows = await res.json();
    if (!rows.length) return NextResponse.json({ error: 'Er is nog geen scan beschikbaar.' }, { status: 404 });
    const results = (rows[0].payload?.results || []).filter((r) => wanted.has(r.ticker));
    return NextResponse.json({ generated_at: rows[0].generated_at, results }, { headers: { 'Cache-Control': 'no-store, max-age=0' } });
  } catch (e) {
    return NextResponse.json({ error: `Kan koersen niet laden: ${e instanceof Error ? e.message : 'onbekende fout'}` }, { status: 500 });
  }
}
