import { NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';
export const revalidate = 0;

const SOURCE = 'https://raw.githubusercontent.com/hugopijnenborg/stock-scanner/main/public/data/latest_scan.json';

export async function GET() {
  try {
    const response = await fetch(`${SOURCE}?t=${Date.now()}`, {
      cache: 'no-store',
      headers: { Accept: 'application/json' },
    });

    if (!response.ok) {
      return NextResponse.json(
        { error: `GitHub scan data returned HTTP ${response.status}` },
        { status: 502 }
      );
    }

    const text = await response.text();
    const cleaned = text
      .replace(/\bNaN\b/g, 'null')
      .replace(/\b-Infinity\b/g, 'null')
      .replace(/\bInfinity\b/g, 'null');

    const data = JSON.parse(cleaned);
    return NextResponse.json(data, {
      headers: { 'Cache-Control': 'no-store, max-age=0' },
    });
  } catch (error) {
    return NextResponse.json(
      { error: `Kan scan data niet laden: ${error instanceof Error ? error.message : 'onbekende fout'}` },
      { status: 500 }
    );
  }
}
