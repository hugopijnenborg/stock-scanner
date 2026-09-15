import { NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';
export const revalidate = 0;

const SOURCE = 'https://raw.githubusercontent.com/hugopijnenborg/stock-scanner/main/public/data/latest_scan.json';
const COMMITS = 'https://api.github.com/repos/hugopijnenborg/stock-scanner/commits?path=public/data/latest_scan.json&per_page=1';

// The score is calculated once, in score_engine.py, and published inside
// latest_scan.json. This route must never recalculate it: the published
// trader/technical scores are already calibrated, so scoring them again here
// would apply the relaxation twice and promote sub-80 rows to BUY ALERT.
const SCORE_WEIGHTS = { trader: 30, technical: 35, fundamental: 35 };
const ALERT_THRESHOLD = 80;
const WATCH_THRESHOLD = 65;

function numberOrNull(value) {
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

function signalFor(overall) {
  if (overall === null) return 'DATA_INCOMPLETE';
  if (overall >= ALERT_THRESHOLD) return 'ALERT';
  if (overall >= WATCH_THRESHOLD) return 'WATCH';
  return 'NO_SIGNAL';
}

function normalizeResult(row) {
  const overall = numberOrNull(row.overall_score);
  // Only fall back to deriving the signal when the published scan predates the
  // signal field. Never re-derive the score itself.
  const signal = row.signal || signalFor(overall);

  return {
    ...row,
    overall_score: overall,
    trader_score: numberOrNull(row.trader_score ?? row.trader_similarity_score),
    technical_score: numberOrNull(row.technical_score),
    fundamental_score: numberOrNull(row.fundamental_score),
    trader_similarity_score: numberOrNull(row.trader_similarity_score ?? row.trader_score),
    signal,
  };
}

export async function GET() {
  try {
    const [dataResponse, commitResponse] = await Promise.all([
      fetch(`${SOURCE}?t=${Date.now()}`, {
        cache: 'no-store',
        headers: { Accept: 'application/json' },
      }),
      fetch(`${COMMITS}&t=${Date.now()}`, {
        cache: 'no-store',
        headers: { Accept: 'application/vnd.github+json' },
      }),
    ]);

    if (!dataResponse.ok) {
      return NextResponse.json(
        { error: `GitHub scan data returned HTTP ${dataResponse.status}` },
        { status: 502 }
      );
    }

    const text = await dataResponse.text();
    const cleaned = text
      .replace(/\bNaN\b/g, 'null')
      .replace(/\b-Infinity\b/g, 'null')
      .replace(/\bInfinity\b/g, 'null');

    const data = JSON.parse(cleaned);
    const originalGeneratedAt = data.generated_at;

    if (Array.isArray(data.results)) {
      data.results = data.results.map(normalizeResult);
      data.results.sort((a, b) => {
        const scoreA = numberOrNull(a.overall_score);
        const scoreB = numberOrNull(b.overall_score);
        return (scoreB ?? -1) - (scoreA ?? -1);
      });
      data.alert_count = data.results.filter((row) => row.signal === 'ALERT').length;
      data.top_score = data.results.length ? data.results[0].overall_score : null;
    }

    data.score_weights = data.score_weights || SCORE_WEIGHTS;
    data.alert_threshold = data.alert_threshold ?? ALERT_THRESHOLD;

    if (commitResponse.ok) {
      const commits = await commitResponse.json();
      const latestCommitDate = commits?.[0]?.commit?.committer?.date || commits?.[0]?.commit?.author?.date;
      const latestCommitSha = commits?.[0]?.sha;
      if (latestCommitDate) data.generated_at = latestCommitDate;
      if (originalGeneratedAt) data.scan_generated_at = originalGeneratedAt;
      if (latestCommitSha) data.scan_version = latestCommitSha;
    }

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
