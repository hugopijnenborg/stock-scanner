import { NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

// Start een nieuwe scan via de n8n-webhook. Zet de volledige webhook-URL in de
// Vercel environment variable N8N_SCAN_WEBHOOK_URL.
export async function POST() {
  const hook = process.env.N8N_SCAN_WEBHOOK_URL;
  if (!hook) {
    return NextResponse.json({ error: 'N8N_SCAN_WEBHOOK_URL ontbreekt in de Vercel environment variables.' }, { status: 503 });
  }
  const response = await fetch(hook, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ source: 'dashboard' }),
    cache: 'no-store',
  });
  if (!response.ok) {
    console.error('n8n webhook failed:', response.status, await response.text());
    return NextResponse.json({ error: `De scan kon niet gestart worden (${response.status}).` }, { status: 502 });
  }
  return NextResponse.json({ ok: true, message: 'Scan gestart.' });
}
