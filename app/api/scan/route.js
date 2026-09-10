import { NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';
export const revalidate = 0;

const SOURCE = 'https://raw.githubusercontent.com/hugopijnenborg/stock-scanner/main/public/data/latest_scan.json';
const COMMITS = 'https://api.github.com/repos/hugopijnenborg/stock-scanner/commits?path=public/data/latest_scan.json&per_page=1';

const WEIGHTS = {
  trader_similarity_score: 0.35,
  technical_score: 0.30,
  fundamental_score: 0.20,
  analyst_consensus_score: 0.15,
};
const ALERT_THRESHOLD = 70;
const WATCH_THRESHOLD = 55;

function numberOrNull(value) {
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

function calculateOverallScore(row) {
  const parts = [
    [numberOrNull(row.trader_similarity_score), WEIGHTS.trader_similarity_score],
    [numberOrNull(row.technical_score), WEIGHTS.technical_score],
    [numberOrNull(row.fundamental_score), WEIGHTS.fundamental_score],
    [numberOrNull(row.analyst_consensus_score), WEIGHTS.analyst_consensus_score],
  ].filter(([value]) => value !== null);

  if (!parts.length) return null;

  const weightSum = parts.reduce((sum, [, weight]) => sum + weight, 0);
  const weighted = parts.reduce((sum, [value, weight]) => sum + value * weight, 0) / weightSum;
  return Math.round(weighted * 10) / 10;
}

function normalizeResult(row) {
  const overall = calculateOverallScore(row);
  let signal = 'DATA_INCOMPLETE';
  if (overall !== null) {
    if (overall >= ALERT_THRESHOLD) signal = 'ALERT';
    else if (overall >= WATCH_THRESHOLD) signal = 'WATCH';
    else signal = 'NO_SIGNAL';
  }

  return {
    ...row,
    overall_score: overall,
    trader_score: numberOrNull(row.trader_similarity_score),
    technical_score: numberOrNull(row.technical_score),
    fundamental_score: numberOrNull(row.fundamental_score),
    analyst_score: numberOrNull(row.analyst_consensus_score),
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

    // Recalculate the production score from the four live components at read time.
    // This prevents an older persisted overall_score from surviving after the
    // scoring model changed to Trader 35%, Technical 30%, Fundamentals 20%, Analyst 15%.
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

    data.score_weights = { trader: 35, technical: 30, fundamental: 20, analyst: 15 };
    data.alert_threshold = ALERT_THRESHOLD;

    // generated_at from the scanner is the scan timestamp. Use the GitHub
    // commit as the refresh version because it changes only after the workflow
    // has actually published a new result file.
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
