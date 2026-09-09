'use client';

import { useEffect } from 'react';

function finite(v) {
  return v != null && Number.isFinite(Number(v));
}

function average(rows, key) {
  const values = rows.map((r) => Number(r?.[key])).filter(Number.isFinite);
  return values.length ? values.reduce((a, b) => a + b, 0) / values.length : null;
}

function marketRegime(rows) {
  const valid = rows.filter((r) => finite(r?.distance_sma50) || finite(r?.return_20d));
  const breadth = valid.length
    ? valid.filter((r) => Number(r.distance_sma50) >= 0).length / valid.length
    : null;
  const avg20 = average(valid, 'return_20d');

  if (breadth == null || avg20 == null) {
    return { label: 'Niet beschikbaar', tone: 'neutral', detail: 'Onvoldoende marktdata' };
  }
  if (breadth >= 0.60 && avg20 >= 0.02) {
    return { label: 'Bullish', tone: 'bullish', detail: `${Math.round(breadth * 100)}% boven SMA50` };
  }
  if (breadth <= 0.40 && avg20 <= -0.02) {
    return { label: 'Risk-off', tone: 'riskoff', detail: `${Math.round(breadth * 100)}% boven SMA50` };
  }
  return { label: 'Neutraal', tone: 'neutral', detail: `${Math.round(breadth * 100)}% boven SMA50` };
}

export default function MarketRegimeCard() {
  useEffect(() => {
    let alive = true;
    let timer;

    const render = async () => {
      const heroStats = document.querySelector('.heroStats');
      if (!heroStats) {
        timer = setTimeout(render, 1000);
        return;
      }

      try {
        const response = await fetch('/api/scan?market-regime=' + Date.now(), { cache: 'no-store' });
        if (!response.ok || !alive) return;
        const body = await response.json();
        if (!alive) return;

        const regime = marketRegime(Array.isArray(body?.results) ? body.results : []);
        let card = heroStats.querySelector('.marketRegimeStat');
        if (!card) {
          card = document.createElement('div');
          card.className = 'marketRegimeStat';
          heroStats.appendChild(card);
        }

        card.className = `marketRegimeStat ${regime.tone}`;
        card.innerHTML = `<span>MARKTREGIME</span><strong>${regime.label}</strong><small>${regime.detail}</small>`;
      } catch (_) {}
    };

    render();
    const interval = setInterval(render, 60000);

    return () => {
      alive = false;
      clearInterval(interval);
      clearTimeout(timer);
    };
  }, []);

  return null;
}
