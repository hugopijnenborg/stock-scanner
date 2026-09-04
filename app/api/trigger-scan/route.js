import { NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

const OWNER = 'hugopijnenborg';
const REPO = 'stock-scanner';
const WORKFLOW = 'market_scan.yml';
const BRANCH = 'main';

export async function POST() {
  const token = process.env.GITHUB_TOKEN;

  if (!token) {
    return NextResponse.json(
      { error: 'GITHUB_TOKEN ontbreekt in de Vercel environment variables.' },
      { status: 503 }
    );
  }

  const response = await fetch(
    `https://api.github.com/repos/${OWNER}/${REPO}/actions/workflows/${WORKFLOW}/dispatches`,
    {
      method: 'POST',
      headers: {
        Accept: 'application/vnd.github+json',
        Authorization: `Bearer ${token}`,
        'X-GitHub-Api-Version': '2022-11-28',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ ref: BRANCH }),
      cache: 'no-store',
    }
  );

  if (!response.ok) {
    const detail = await response.text();
    console.error('GitHub workflow dispatch failed:', response.status, detail);
    return NextResponse.json(
      { error: `GitHub kon de scan niet starten (${response.status}).` },
      { status: 502 }
    );
  }

  return NextResponse.json({ ok: true, message: 'Scan gestart.' });
}
