(() => {
  const cache = { data: null, promise: null };
  const fmtPct = v => v == null || !Number.isFinite(Number(v)) ? '—' : `${Number(v) >= 0 ? '+' : ''}${(Number(v) * 100).toFixed(1)}%`;
  const fmtPrice = v => v == null || !Number.isFinite(Number(v)) ? '—' : `$${Number(v).toFixed(2)}`;
  const esc = s => String(s ?? '').replace(/[&<>\"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}[c]));
  const ratingClass = r => /STRONG BUY|BUY/.test(r || '') ? 'bull' : /SELL/.test(r || '') ? 'bear' : 'neutral';

  async function loadData() {
    if (cache.data?.results?.length) return cache.data;
    if (!cache.promise) cache.promise = fetch('/api/scan?alertdetail='+Date.now(), { cache: 'no-store' })
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

  function makeChart(points, today, panel) {
    const old = panel.querySelector('.enhancedPriceChart');
    if (old) old.remove();
    const section = [...panel.querySelectorAll('.detailSection')].find(x => x.querySelector('h3')?.textContent.trim() === 'Koersverloop');
    if (!section) return;
    const ranges = { '6M': 180, '3M': 90, '1M': 30, '1W': 7 };
    let range = '6M';
    const wrap = document.createElement('div');
    wrap.className = 'enhancedPriceChart';
    wrap.innerHTML = `<div class="chartRangeBar"><div class="chartRangeButtons"><button data-range="6M" class="active">6M</button><button data-range="3M">3M</button><button data-range="1M">1M</button><button data-range="1W">1W</button><button data-range="1D">Vandaag</button></div></div><div class="enhancedChart"></div>`;
    section.querySelector('.chartWrap')?.remove();
    section.querySelector('.chartLabels')?.remove();
    section.insertBefore(wrap, section.querySelector('.chartStats'));
    const chart = wrap.querySelector('.enhancedChart');

    function draw() {
      const source = range === '1D' ? (today || []) : (points || []).filter(p => p && Number.isFinite(Number(p.close))).filter(p => {
        if (range === '6M') return true;
        const last = new Date(points[points.length - 1]?.date || Date.now());
        const d = new Date(p.date);
        return (last - d) / 86400000 <= ranges[range];
      });
      if (source.length < 2) { chart.innerHTML = '<div class="chartEmpty"><span>Niet genoeg koersdata beschikbaar.</span></div>'; return; }
      const vals = source.map(p => Number(p.close));
      const min = Math.min(...vals), max = Math.max(...vals), span = max - min || Math.max(1, max * .01);
      const w = 900, h = 290, px = 16, py = 18;
      const path = vals.map((v,i) => `${px + (i/(vals.length-1))*(w-px*2)},${h-py-((v-min)/span)*(h-py*2)}`).join(' ');
      const first = vals[0], last = vals[vals.length-1], change = last/first-1;
      chart.innerHTML = `<div class="chartHeadline"><div><span>${range === '1D' ? 'VANDAAG' : range}</span><strong>${fmtPrice(last)}</strong></div><b class="${change >= 0 ? 'positive' : 'negative'}">${fmtPct(change)}</b></div><svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" aria-label="Koersgrafiek"><polyline points="${path}" fill="none" stroke="currentColor" stroke-width="3" vector-effect="non-scaling-stroke"/></svg><div class="chartAxis"><span>${esc(source[0].date || '')}</span><span>${esc(source[source.length-1].date || '')}</span></div>`;
    }
    wrap.querySelectorAll('button').forEach(btn => btn.addEventListener('click', () => { range = btn.dataset.range; wrap.querySelectorAll('button').forEach(b => b.classList.toggle('active', b === btn)); draw(); }));
    draw();
  }

  function makeIntelligence(row, panel) {
    panel.querySelector('.enhancedAlertIntel')?.remove();
    const scoreSection = panel.querySelector('.detailScore');
    if (!scoreSection) return;
    const el = document.createElement('section');
    el.className = 'enhancedAlertIntel';
    const changes = Array.isArray(row.analyst_recent_changes) ? row.analyst_recent_changes.filter(x => x && (x.firm || x.action)).slice(0,4) : [];
    const target = row.analyst_target_mean;
    const targetUpside = row.analyst_target_upside;
    const recommendation = row.analyst_recommendation || '—';
    const counts = [
      ['Strong buy', row.analyst_strong_buy], ['Buy', row.analyst_buy], ['Hold', row.analyst_hold], ['Sell', row.analyst_sell], ['Strong sell', row.analyst_strong_sell]
    ].filter(x => Number(x[1]) > 0);
    el.innerHTML = `<div class="intelSummary"><div class="intelEyebrow">WAAROM NU EEN ALERT?</div><p>${esc(row.alert_summary || 'De gecombineerde scanner-score is boven de alertdrempel gekomen.')}</p></div><div class="intelGrid"><div class="intelBlock"><span>ANALISTENCONSENSUS</span><div class="ratingLine"><strong class="${ratingClass(recommendation)}">${esc(recommendation)}</strong><small>${row.analyst_count ? `${row.analyst_count} beoordelingen` : 'Geen consensusaantal'}</small></div><div class="ratingBars">${counts.map(([name,n]) => `<div><span>${name}</span><b>${n}</b></div>`).join('')}</div></div><div class="intelBlock"><span>KOERSDOEL</span><div class="targetMain"><strong>${fmtPrice(target)}</strong><b class="${targetUpside >= 0 ? 'positive' : 'negative'}">${fmtPct(targetUpside)}</b></div><small>Gemiddeld analyst target · range ${fmtPrice(row.analyst_target_low)} — ${fmtPrice(row.analyst_target_high)}</small><div class="targetMeta"></div></div></div><div class="intelBlock intelChanges"><span>RECENTE ANALISTENACTIES</span>${changes.length ? `<div class="changeList">${changes.map(c => `<div><b>${esc(c.firm || 'Analist')}</b><span>${esc(c.action || '')}</span><small>${esc(c.from_grade || '')}${c.from_grade && c.to_grade ? ' → ' : ''}${esc(c.to_grade || '')}</small></div>`).join('')}</div>` : '<small>Geen recente wijzigingen beschikbaar.</small>'}</div>`;
    el.querySelector('.targetMeta').textContent = `Mediaan ${fmtPrice(row.analyst_target_median)} · ${row.analyst_target_changes_30d || 0} targetwijzigingen in 30D`;
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
    makeIntelligence(row, panel);
    makeChart(row.history_6m, row.history_today, panel);
  }

  const observer = new MutationObserver(() => {
    document.querySelectorAll('.detailPanel').forEach(enhance);
  });
  observer.observe(document.body, { childList: true, subtree: true });
  document.querySelectorAll('.detailPanel').forEach(enhance);
})();
