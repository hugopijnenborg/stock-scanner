import { NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';
export const revalidate = 0;

const SOURCE = 'https://raw.githubusercontent.com/hugopijnenborg/stock-scanner/main/public/data/latest_scan.json';
const COMMITS = 'https://api.github.com/repos/hugopijnenborg/stock-scanner/commits?path=public/data/latest_scan.json&per_page=1';

const WEIGHTS = {
  trader: 0.30,
  technical: 0.35,
  fundamental: 0.35,
};
const ALERT_THRESHOLD = 80;
const WATCH_THRESHOLD = 65;
const TRADER_RELAXATION = 0.45;
const TECHNICAL_RELAXATION = 0.40;

function numberOrNull(value) {
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

function relaxScore(value, relaxation) {
  if (value === null) return null;
  const clamped = Math.max(0, Math.min(100, value));
  return clamped + (100 - clamped) * relaxation;
}

function calculateOverallScore(row) {
  const traderRaw = numberOrNull(row.trader_similarity_score);
  const technicalRaw = numberOrNull(row.technical_score);
  const fundamental = numberOrNull(row.fundamental_score);

  const trader = relaxScore(traderRaw, TRADER_RELAXATION);
  const technical = relaxScore(technicalRaw, TECHNICAL_RELAXATION);
  const parts = [
    [trader, WEIGHTS.trader],
    [technical, WEIGHTS.technical],
    [fundamental, WEIGHTS.fundamental],
  ].filter(([value]) => value !== null);

  if (!parts.length) return null;

  const weightSum = parts.reduce((sum, [, weight]) => sum + weight, 0);
  const weighted = parts.reduce((sum, [value, weight]) => sum + value * weight, 0) / weightSum;
  return Math.round(weighted * 10) / 10;
}

function normalizeResult(row) {
  const overall = calculateOverallScore(row);
  const traderRaw = numberOrNull(row.trader_similarity_score);
  const technicalRaw = numberOrNull(row.technical_score);
  const fundamental = numberOrNull(row.fundamental_score);
  const trader = relaxScore(traderRaw, TRADER_RELAXATION);
  const technical = relaxScore(technicalRaw, TECHNICAL_RELAXATION);

  let signal = 'DATA_INCOMPLETE';
  if (overall !== null) {
    if (overall >= ALERT_THRESHOLD) signal = 'ALERT';
    else if (overall >= WATCH_THRESHOLD) signal = 'WATCH';
    else signal = 'NO_SIGNAL';
  }

  return {
    ...row,
    overall_score: overall,
    trader_score: trader === null ? null : Math.round(trader * 10) / 10,
    technical_score: technical === null ? null : Math.round(technical * 10) / 10,
    fundamental_score: fundamental,
    trader_similarity_score: trader === null ? null : Math.round(trader * 10) / 10,
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

    data.score_weights = { trader: 30, technical: 35, fundamental: 35 };
    data.alert_threshold = ALERT_THRESHOLD;

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
