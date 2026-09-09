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
  const breadth = valid.length ? valid.filter((r) => Number(r.distance_sma50) >= 0).length / valid.length : null;
  const avg20 = average(valid, 'return_20d');

  if (breadth == null || avg20 == null) return { label: 'Niet beschikbaar', tone: 'neutral', detail: 'Onvoldoende marktdata' };
  if (breadth >= 0.60 && avg20 >= 0.02) return { label: 'Bullish', tone: 'bullish', detail: `${Math.round(breadth * 100)}% boven SMA50` };
  if (breadth <= 0.40 && avg20 <= -0.02) return { label: 'Risk-off', tone: 'riskoff', detail: `${Math.round(breadth * 100)}% boven SMA50` };
  return { label: 'Neutraal', tone: 'neutral', detail: `${Math.round(breadth * 100)}% boven SMA50` };
}

function qualityForStock(r) {
  const scoreFields = [r?.trader_similarity_score, r?.technical_score, r?.fundamental_score, r?.analyst_consensus_score];
  const scoreComplete = scoreFields.filter(finite).length;
  const technicalFields = ['rsi_14', 'return_1d', 'return_3d', 'return_5d', 'return_20d', 'volume_ratio', 'distance_sma20', 'distance_sma50', 'macd_histogram', 'relative_strength_20d'];
  const fundamentalFields = ['revenue_growth', 'eps_growth', 'net_margin', 'fcf', 'roe', 'debt_equity', 'pe', 'forward_pe', 'peg'];
  const analystFields = ['analyst_recommendation', 'analyst_count', 'analyst_target_mean', 'analyst_target_upside'];
  const completeness = (fields) => fields.filter((key) => finite(r?.[key]) || (typeof r?.[key] === 'string' && r[key].trim())).length / fields.length;
  const technical = completeness(technicalFields);
  const fundamentals = completeness(fundamentalFields);
  const analyst = completeness(analystFields);
  const quality = Math.round((scoreComplete / 4) * 40 + technical * 25 + fundamentals * 25 + analyst * 10);
  return { quality, scoreComplete, technical, fundamentals, analyst };
}

function ensureMarketCard(rows) {
  const heroStats = document.querySelector('.heroStats');
  if (!heroStats) return;
  const regime = marketRegime(rows);
  let card = heroStats.querySelector('.marketRegimeStat');
  if (!card) {
    card = document.createElement('div');
    card.className = `marketRegimeStat ${regime.tone}`;
    heroStats.appendChild(card);
  }
  const html = `<span>MARKTREGIME</span><strong>${regime.label}</strong><small>${regime.detail}</small>`;
  if (card.innerHTML !== html || card.className !== `marketRegimeStat ${regime.tone}`) {
    card.className = `marketRegimeStat ${regime.tone}`;
    card.innerHTML = html;
  }
}

function ensureDataQuality(rows) {
  const modal = document.querySelector('.detailPanel.detailPanelOpportunity');
  if (!modal) return;
  const title = modal.querySelector('.detailTop h2');
  const ticker = title?.textContent?.split(':')[0]?.trim();
  if (!ticker) return;
  const stock = rows.find((r) => String(r?.ticker || '').toUpperCase() === ticker.toUpperCase());
  if (!stock) return;

  const quality = qualityForStock(stock);
  const html = `
    <div class="dataQualityCard">
      <div class="dataQualityHead"><div><span class="sectionEyebrow">DATA QUALITY</span><strong>${quality.quality}/100</strong></div><span class="dataQualityBadge ${quality.quality >= 85 ? 'good' : quality.quality >= 65 ? 'medium' : 'low'}">${quality.quality >= 85 ? 'HOOG' : quality.quality >= 65 ? 'GEMIDDELD' : 'LAAG'}</span></div>
      <div class="dataQualityGrid">
        <div><span>Scoredata</span><b>${quality.scoreComplete}/4 compleet</b></div>
        <div><span>Technisch</span><b>${Math.round(quality.technical * 100)}% compleet</b></div>
        <div><span>Fundamentals</span><b>${Math.round(quality.fundamentals * 100)}% compleet</b></div>
        <div><span>Analisten</span><b>${Math.round(quality.analyst * 100)}% compleet</b></div>
      </div>
      <p>Data Quality meet de volledigheid van de gegevens die voor deze analyse beschikbaar zijn. Het verandert de totaalscore niet.</p>
    </div>`;

  const existing = modal.querySelector('.dataQualityCard');
  if (existing) {
    if (existing.outerHTML !== html) existing.outerHTML = html;
    return;
  }

  const cards = modal.querySelector('.detailCards');
  if (cards && !modal.querySelector('.dataQualityCard')) cards.insertAdjacentHTML('afterend', html);
}

export default function MarketContextBridge() {
  useEffect(() => {
    let alive = true;
    let rows = [];

    const load = async () => {
      try {
        const response = await fetch('/api/scan?context=' + Date.now(), { cache: 'no-store' });
        if (!response.ok) return;
        const body = await response.json();
        if (!alive) return;
        rows = Array.isArray(body?.results) ? body.results : [];
        ensureMarketCard(rows);
        ensureDataQuality(rows);
      } catch (_) {}
    };

    load();
    const interval = setInterval(load, 60000);

    const observer = new MutationObserver(() => {
      if (!alive) return;
      ensureMarketCard(rows);
      ensureDataQuality(rows);
    });
    observer.observe(document.body, { childList: true, subtree: true });

    return () => {
      alive = false;
      clearInterval(interval);
      observer.disconnect();
    };
  }, []);

  return null;
}
