import { NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

export async function GET() {
  const url = (process.env.SUPABASE_URL || '').replace(/\/$/, '');
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY || '';
  if (!url || !key) {
    return NextResponse.json({ error: 'Supabase environment variables ontbreken.' }, { status: 500 });
  }

  const response = await fetch(
    `${url}/rest/v1/stock_scanner_alerts?select=*&ticker=neq.FLNC&order=alert_timestamp.desc&limit=1000`,
    {
      headers: {
        apikey: key,
        Authorization: `Bearer ${key}`,
      },
      cache: 'no-store',
    }
  );

  if (!response.ok) {
    const text = await response.text();
    return NextResponse.json({ error: `Supabase fout: ${text}` }, { status: response.status });
  }

  const rows = await response.json();
  return NextResponse.json({ alerts: rows });
}
