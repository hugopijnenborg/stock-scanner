(() => {
  const cache = { data: null, promise: null };
  const esc = s => String(s ?? '').replace(/[&<>\"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}[c]));
  const pct = v => v == null || !Number.isFinite(Number(v)) ? '—' : `${Number(v) >= 0 ? '+' : ''}${(Number(v) * 100).toFixed(1)}%`;
  const price = v => v == null || !Number.isFinite(Number(v)) ? '—' : `$${Number(v).toFixed(2)}`;
  const num = (v, d = 1) => v == null || !Number.isFinite(Number(v)) ? '—' : Number(v).toFixed(d);

  async function loadData() {
    if (cache.data?.results?.length) return cache.data;
    if (!cache.promise) cache.promise = fetch('/api/scan?alertdetail=' + Date.now(), { cache: 'no-store' })
      .then(r => r.ok ? r.json() : null)
      .then(d => d?.results ? (cache.data = d) : null)
      .catch(() => null);
    return cache.promise;
  }

  function tickerFromPanel(panel) {
    const el = panel.querySelector('.detailTicker');
    if (!el) return null;
    const m = el.textContent.trim().match(/^([A-Z0-9.\-]+)/);
    return m ? m[1] : null;
  }

  function recentEarnings(row) {
    if (!row.last_earnings_date) return null;
    const d = new Date(row.last_earnings_date);
    if (Number.isNaN(d.getTime())) return null;
    const days = Math.round((Date.now() - d.getTime()) / 86400000);
    return days >= 0 && days <= 14 ? days : null;
  }

  function upcomingEarnings(row) {
    if (!row.next_earnings_date) return null;
    const d = new Date(row.next_earnings_date);
    if (Number.isNaN(d.getTime())) return null;
    const days = Math.round((d.getTime() - Date.now()) / 86400000);
    return days >= 0 && days <= 90 ? days : null;
  }

  function buildAnalysis(row) {
    const p = Number(row.price);
    const r5 = Number(row.return_5d);
    const r10 = Number(row.return_10d);
    const r20 = Number(row.return_20d);
    const rsi = Number(row.rsi_14);
    const dd52 = Number(row.distance_52w_high);
    const sma20 = Number(row.distance_sma20);
    const sma50 = Number(row.distance_sma50);
    const volume = Number(row.volume_ratio);
    const trader = Number(row.trader_similarity_score);
    const technical = Number(row.technical_score);
    const fundamental = Number(row.fundamental_score);
    const meanTarget = Number(row.analyst_target_mean);
    const medianTarget = Number(row.analyst_target_median);
    const nextEarnings = upcomingEarnings(row);
    const lastEarnings = recentEarnings(row);
    const sections = [];

    const move = Number.isFinite(r10) ? r10 : r20;
    let overview = row.alert_summary || 'De scanner ziet een combinatie van een duidelijke koersdislocatie en een patroon dat sterk overeenkomt met eerdere trader-setups.';
    const overviewBits = [];
    if (Number.isFinite(dd52) && dd52 < -0.15) overviewBits.push(`${Math.abs(dd52 * 100).toFixed(1)}% onder de 52-weeks high`);
    if (Number.isFinite(rsi)) overviewBits.push(`RSI ${rsi.toFixed(1)}`);
    if (Number.isFinite(trader)) overviewBits.push(`trader match ${trader.toFixed(0)}/100`);
    if (overviewBits.length) overview += ` ${overviewBits.join(' · ')}.`;

    let technicalText = [];
    if (Number.isFinite(move) && move < -0.05) technicalText.push(`De koers is in de recente periode ${Math.abs(move * 100).toFixed(1)}% teruggevallen.`);
    if (Number.isFinite(r5) && r5 < -0.05 && Number.isFinite(r10) && r10 < -0.05) technicalText.push(`Ook over 5 dagen staat het aandeel ${Math.abs(r5 * 100).toFixed(1)}% lager.`);
    if (Number.isFinite(dd52) && dd52 < -0.15) technicalText.push(`Vanaf de 52-weeks high bedraagt de drawdown ${Math.abs(dd52 * 100).toFixed(1)}%.`);
    if (Number.isFinite(rsi)) technicalText.push(rsi < 30 ? `RSI ${rsi.toFixed(1)} staat duidelijk in oversold-territorium.` : rsi < 40 ? `RSI ${rsi.toFixed(1)} is laag en bevestigt de oversold-achtige setup.` : `RSI ${rsi.toFixed(1)} is niet extreem oversold, waardoor de technische setup minder puur op RSI leunt.`);
    if (Number.isFinite(sma20) && sma20 < -0.05) technicalText.push(`De koers ligt ${Math.abs(sma20 * 100).toFixed(1)}% onder de 20-daagse gemiddelde koers.`);
    if (Number.isFinite(sma50) && sma50 < -0.05) technicalText.push(`Ten opzichte van de 50-daagse gemiddelde koers staat het aandeel ${Math.abs(sma50 * 100).toFixed(1)}% lager.`);
    if (Number.isFinite(volume) && volume >= 1.5) technicalText.push(`Het volume ligt ongeveer ${volume.toFixed(1)}x boven het normale niveau, wat op verhoogde verkoopinteresse of capitulatie kan wijzen.`);
    if (!technicalText.length) technicalText.push('De technische score is gebaseerd op de combinatie van sell-off, RSI, dislocatie, volume, steun en reversal-signalen.');
    sections.push(['1. Technische setup', technicalText.join(' ')]);

    const patternBits = [];
    if (Number.isFinite(trader)) patternBits.push(`De trader-pattern match staat op ${trader.toFixed(0)}/100.`);
    if (Number.isFinite(technical)) patternBits.push(`De technische opportunity score staat op ${technical.toFixed(0)}/100.`);
    patternBits.push('De alert wordt geactiveerd door de combinatie van het geleerde trader-patroon en de technische setup, niet door fundamentals alleen.');
    sections.push(['2. Trader-patroon', patternBits.join(' ')]);

    const fundBits = [];
    if (Number.isFinite(row.revenue_growth)) fundBits.push(`omzetgroei ${pct(row.revenue_growth)}`);
    if (Number.isFinite(row.eps_growth)) fundBits.push(`EPS-groei ${pct(row.eps_growth)}`);
    if (Number.isFinite(row.net_margin)) fundBits.push(`nettomarge ${pct(row.net_margin)}`);
    if (Number.isFinite(row.fcf) && row.fcf > 0) fundBits.push('positieve vrije kasstroom');
    if (Number.isFinite(row.roe)) fundBits.push(`ROE ${pct(row.roe)}`);
    if (Number.isFinite(row.debt_equity)) fundBits.push(`debt/equity ${num(row.debt_equity, 2)}`);
    if (lastEarnings != null && Number.isFinite(Number(row.last_earnings_surprise_pct))) fundBits.push(`recente earnings surprise ${pct(Number(row.last_earnings_surprise_pct) / 100)}`);
    const fundText = fundBits.length ? `De fundamentals zijn aanvullende context voor de swing-setup: ${fundBits.slice(0, 6).join(' · ')}.` : 'Er is onvoldoende fundamentele data beschikbaar om hier een inhoudelijke conclusie aan te verbinden.';
    sections.push(['3. Fundamentals', fundText]);

    const counts = [
      ['Strong Buy', row.analyst_strong_buy], ['Buy', row.analyst_buy], ['Hold', row.analyst_hold],
      ['Sell', row.analyst_sell], ['Strong Sell', row.analyst_strong_sell]
    ].filter(x => Number(x[1]) > 0);
    const analystBits = [];
    if (row.analyst_recommendation) analystBits.push(`consensus ${row.analyst_recommendation}`);
    if (row.analyst_count) analystBits.push(`${row.analyst_count} beoordelingen`);
    if (Number.isFinite(meanTarget)) analystBits.push(`gemiddeld koersdoel ${price(meanTarget)}`);
    if (Number.isFinite(medianTarget)) analystBits.push(`mediaan ${price(medianTarget)}`);
    if (Number.isFinite(Number(row.analyst_target_upside))) analystBits.push(`${pct(row.analyst_target_upside)} upside naar het gemiddelde target`);
    if (Number(row.analyst_bullish_changes_30d) > Number(row.analyst_bearish_changes_30d)) analystBits.push(`meer positieve dan negatieve wijzigingen in 30D (${row.analyst_bullish_changes_30d} vs ${row.analyst_bearish_changes_30d})`);
    const analystText = analystBits.length ? `De beschikbare analisteninformatie ondersteunt de setup: ${analystBits.join(' · ')}.` : 'Er is momenteel geen bruikbare analistenconsensus of koersdoel beschikbaar voor dit aandeel.';
    sections.push(['4. Analisten', analystText]);

    const catalystBits = [];
    if (nextEarnings != null) catalystBits.push(`volgende kwartaalcijfers over ongeveer ${nextEarnings} dagen`);
    if (lastEarnings != null) catalystBits.push(`recente kwartaalcijfers (${lastEarnings} dagen geleden)`);
    const news = Array.isArray(row.recent_news) ? row.recent_news.filter(x => x?.title).slice(0, 2) : [];
    if (news.length) catalystBits.push(`recente marktinformatie: ${news.map(x => x.title).join(' | ')}`);
    sections.push(['5. Katalysator / timing', catalystBits.length ? catalystBits.join('. ') + '.' : 'Er is geen concrete nabije katalysator beschikbaar in de data. De alert is daarom primair een technische swing-setup.']);

    const targetBits = [];
    if (Number.isFinite(p)) {
      const target25 = p * 1.25;
      const target50 = p * 1.50;
      targetBits.push(`+25% vereist ongeveer ${price(target25)}`);
      targetBits.push(`+50% vereist ongeveer ${price(target50)}`);
      if (Number.isFinite(Number(row.high_52w))) {
        targetBits.push(`52-weeks high ligt op ${price(row.high_52w)}`);
      }
      if (Number.isFinite(meanTarget)) targetBits.push(`gemiddeld analistentarget ${price(meanTarget)}`);
    }
    sections.push(['6. Return-potential', targetBits.length ? targetBits.join('. ') + '.' : 'Geen betrouwbare targetdata beschikbaar om een concreet return-pad te onderbouwen.']);

    const riskBits = [];
    if (Number.isFinite(rsi) && rsi < 35) riskBits.push('de RSI kan lang oversold blijven terwijl de koers verder daalt');
    if (Number.isFinite(sma20) && sma20 < -0.05 && Number.isFinite(sma50) && sma50 < -0.05) riskBits.push('de korte en middellange trend staan nog onder druk');
    if (Number.isFinite(dd52) && dd52 < -0.30) riskBits.push('de drawdown vanaf de 52-weeks high is groot');
    if (!riskBits.length) riskBits.push('een oversold-score is geen garantie op een directe reversal');
    sections.push(['7. Belangrijkste risico', riskBits.join('. ') + '.']);

    return { overview, sections, counts };
  }

  function makeIntelligence(row, panel) {
    panel.querySelector('.enhancedAlertIntel')?.remove();
    const scoreSection = panel.querySelector('.detailScore');
    if (!scoreSection) return;
    const analysis = buildAnalysis(row);
    const el = document.createElement('section');
    el.className = 'enhancedAlertIntel';
    const target = Number(row.analyst_target_mean);
    const targetUpside = Number(row.analyst_target_upside);
    const analystAvailable = row.analyst_recommendation || Number.isFinite(target) || row.analyst_count;
    el.innerHTML = `
      <div class="intelSummary">
        <div class="intelEyebrow">WAAROM NU EEN ALERT?</div>
        <h3>${esc(row.ticker)}: BUY ALERT</h3>
        <div class="intelMeta">Score ${esc(num(row.overall_score, 0))}/100 · koers ${esc(price(row.price))} · trader match ${esc(num(row.trader_similarity_score, 0))}/100 · technical ${esc(num(row.technical_score, 0))}/100</div>
        <p>${esc(analysis.overview)}</p>
      </div>
      <div class="intelNarrative">
        ${analysis.sections.map(([title, text]) => `<article><h4>${esc(title)}</h4><p>${esc(text)}</p></article>`).join('')}
      </div>
      ${analystAvailable ? `<div class="intelAnalystSnapshot"><div><span>ANALISTENCONSENSUS</span><strong>${esc(row.analyst_recommendation || 'Beschikbaar')}</strong><small>${row.analyst_count ? `${esc(row.analyst_count)} beoordelingen` : 'Aantal beoordelingen niet beschikbaar'}</small></div><div><span>KOERSDOEL</span><strong>${esc(Number.isFinite(target) ? price(target) : '—')}</strong><small>${Number.isFinite(targetUpside) ? esc(pct(targetUpside) + ' vanaf huidige koers') : 'Geen upside berekend'}</small></div></div>` : ''}
    `;
    scoreSection.after(el);
  }

  async function enhance(panel) {
    if (!panel || panel.dataset.enhanced === '1') return;
    const ticker = tickerFromPanel(panel);
    if (!ticker) return;
    const data = await loadData();
    const row = data?.results?.find(x => x.ticker === ticker);
    if (!row) return;
    panel.dataset.enhanced = '1';
    // The old koersverloop component was consistently empty for alert details.
    // Remove it entirely instead of showing an empty placeholder.
    [...panel.querySelectorAll('.detailSection')].forEach(section => {
      const title = section.querySelector('h3')?.textContent?.trim();
      if (title === 'Koersverloop') section.remove();
    });
    makeIntelligence(row, panel);
  }

  const observer = new MutationObserver(() => document.querySelectorAll('.detailPanel').forEach(enhance));
  observer.observe(document.body, { childList: true, subtree: true });
  document.querySelectorAll('.detailPanel').forEach(enhance);
})();
