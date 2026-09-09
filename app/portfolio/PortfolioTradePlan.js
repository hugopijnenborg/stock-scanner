'use client';

import { useEffect } from 'react';

const KEY = 'marketintel_portfolio';
let scanPromise = null;

const money = (value) => Number.isFinite(value) ? `$${value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : '—';
const pct = (value) => Number.isFinite(value) ? `${value >= 0 ? '+' : ''}${(value * 100).toFixed(1)}%` : '—';
const finite = (value) => Number.isFinite(Number(value)) ? Number(value) : null;

function readPortfolio() {
  try { return JSON.parse(localStorage.getItem(KEY) || '[]'); } catch { return []; }
}

function getPivots(history = []) {
  const rows = history.filter((x) => finite(x?.close) !== null);
  const lows = [];
  const highs = [];
  for (let i = 2; i < rows.length - 2; i += 1) {
    const p = Number(rows[i].close);
    const around = rows.slice(i - 2, i + 3).map((x) => Number(x.close));
    if (p === Math.min(...around) && p < around[0] && p < around[4]) lows.push(p);
    if (p === Math.max(...around) && p > around[0] && p > around[4]) highs.push(p);
  }
  return { lows: [...new Set(lows)], highs: [...new Set(highs)] };
}

function makePlan(position, r) {
  const price = finite(r?.price);
  if (!price) return null;

  const atrPct = Math.max(finite(r?.atr_pct) || 0, 0.03);
  const sma20Distance = finite(r?.distance_sma20);
  const sma50Distance = finite(r?.distance_sma50);
  const supportDistance = finite(r?.distance_support_20d);
  const pivots = getPivots(r?.history_6m || []);

  let support = supportDistance != null && supportDistance > 0 && supportDistance < 0.45
    ? price * (1 - supportDistance)
    : null;
  const pivotSupport = pivots.lows.filter((x) => x < price).sort((a, b) => b - a)[0] || null;
  if (!support || (pivotSupport && pivotSupport > support && pivotSupport < price)) support = pivotSupport || support;

  let sma20 = null;
  if (sma20Distance != null && sma20Distance > -0.9) sma20 = price / (1 + sma20Distance);
  let sma50 = null;
  if (sma50Distance != null && sma50Distance > -0.95) sma50 = price / (1 + sma50Distance);

  const resistancePivots = pivots.highs.filter((x) => x > price).sort((a, b) => a - b);
  const candidates = [resistancePivots[0], sma20, sma50].filter((x) => Number.isFinite(x) && x > price * 1.015);
  const firstTarget = candidates.length ? Math.min(...candidates) : null;

  const analystTarget = finite(r?.analyst_target_mean);
  const high52 = finite(r?.high_52w);
  let secondTarget = analystTarget && analystTarget > price ? analystTarget : null;
  if (!secondTarget && high52 && high52 > price) secondTarget = high52;
  if (secondTarget && firstTarget && secondTarget <= firstTarget * 1.03) secondTarget = high52 && high52 > firstTarget * 1.03 ? high52 : secondTarget;

  if (!firstTarget && secondTarget) {
    // Keep the plan useful even when no clean short-term resistance was found.
  }

  const supportLevel = support || price * (1 - atrPct);
  const stop = Math.max(0.01, supportLevel - price * atrPct * 0.5);
  const addPrice = Math.min(supportLevel * 1.01, price * 0.99);
  const target = firstTarget || secondTarget;
  const targetUpside = target ? target / price - 1 : null;
  const risk = price > stop ? 1 - stop / price : null;
  const rewardRisk = target && risk > 0 ? targetUpside / risk : null;

  let context = 'Technische structuur geeft geen duidelijke directe trigger.';
  if (support && price <= support * 1.04) context = 'Koers handelt dicht bij een technische steunzone.';
  else if (firstTarget && price >= firstTarget * 0.96) context = 'Koers nadert de eerste technische weerstand.';
  else if (sma20 && price > sma20) context = 'Koers ligt boven de 20-daagse trend.';
  else if (sma20) context = 'De 20-daagse trend ligt nog boven de huidige koers.';

  const action = String(r?.signal || '').toUpperCase() === 'ALERT' ? 'HOLD / MONITOR' : 'HOLD';
  if (Number(r?.overall_score) < 60) return { action: 'SELL / REDUCE', support, stop, addPrice, firstTarget, secondTarget, targetUpside, risk, rewardRisk, context: 'De actuele totaalscore is te zwak om het bestaande risico agressief aan te houden.' };

  return { action, support, stop, addPrice, firstTarget, secondTarget, targetUpside, risk, rewardRisk, context };
}

function fetchScan() {
  if (!scanPromise) {
    scanPromise = fetch(`/api/scan?ts=${Date.now()}`, { cache: 'no-store' }).then((r) => r.ok ? r.json() : null).catch(() => null);
  }
  return scanPromise;
}

function addRow(container, label, value, tone = '') {
  const row = document.createElement('div');
  row.className = 'tradePlanRow';
  row.innerHTML = `<span>${label}</span><b class="${tone}">${value}</b>`;
  container.appendChild(row);
}

function injectPlan(card, position, result) {
  if (!card || card.querySelector('[data-trade-plan]')) return;
  const plan = makePlan(position, result);
  if (!plan) return;

  const box = document.createElement('div');
  box.dataset.tradePlan = 'true';
  box.className = 'tradePlan';

  const title = document.createElement('div');
  title.className = 'tradePlanTitle';
  title.innerHTML = `<div><span>PERSONEEL TRADEPLAN</span><strong>${plan.action}</strong></div><small>LIVE</small>`;
  box.appendChild(title);

  const grid = document.createElement('div');
  grid.className = 'tradePlanGrid';
  addRow(grid, '1e koersdoel', money(plan.firstTarget));
  addRow(grid, '2e koersdoel', money(plan.secondTarget));
  addRow(grid, 'ADD bij', money(plan.addPrice), 'tradeAdd');
  addRow(grid, 'Risk / stop', money(plan.stop), 'tradeRisk');
  addRow(grid, 'Potentieel', pct(plan.targetUpside), plan.targetUpside > 0 ? 'tradePositive' : 'tradeRisk');
  addRow(grid, 'Risk / reward', plan.rewardRisk ? `${plan.rewardRisk.toFixed(1)}x` : '—');
  box.appendChild(grid);

  const note = document.createElement('div');
  note.className = 'tradePlanNote';
  note.textContent = plan.context;
  box.appendChild(note);

  const source = document.createElement('div');
  source.className = 'tradePlanSource';
  source.textContent = 'Gebaseerd op actuele koers, steun/weerstand, trend, volatiliteit en beschikbare koersdoelen.';
  box.appendChild(source);

  const alert = card.querySelector('.positionAlert');
  if (alert) alert.after(box); else card.appendChild(box);
}

async function enhance() {
  if (!window.location.pathname.startsWith('/portfolio')) return;
  const positions = readPortfolio();
  if (!positions.length) return;
  const data = await fetchScan();
  if (!data?.results) return;
  const map = Object.fromEntries(data.results.map((r) => [r.ticker, r]));
  document.querySelectorAll('.positionCard').forEach((card) => {
    const ticker = card.querySelector('.positionTicker')?.textContent?.trim()?.toUpperCase();
    if (!ticker) return;
    const position = positions.find((p) => p.ticker === ticker);
    if (position) injectPlan(card, position, map[ticker]);
  });
}

export default function PortfolioTradePlan() {
  useEffect(() => {
    enhance();
    const timer = setInterval(enhance, 3000);
    return () => clearInterval(timer);
  }, []);
  return null;
}
