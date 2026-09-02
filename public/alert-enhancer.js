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

  function makeChart(points6m, points1w, today, panel) {
    const old = panel.querySelector('.enhancedPriceChart');
    if (old) old.remove();
    const section = [...panel.querySelectorAll('.detailSection')].find(x => x.querySelector('h3')?.textContent.trim() === 'Koersverloop');
    if (!section) return;
    let range = '6M';
    const wrap = document.createElement('div');
    wrap.className = 'enhancedPriceChart';
    wrap.innerHTML = `<div class="chartRangeBar"><div class="chartRangeButtons"><button data-range="6M" class="active">6M</button><button data-range="3M">3M</button><button data-range="1M">1M</button><button data-range="1W">1W</button><button data-range="1D">Vandaag</button></div></div><div class="enhancedChart"></div>`;
    section.querySelector('.chartWrap')?.remove();
    section.querySelector('.chartLabels')?.remove();
    section.insertBefore(wrap, section.querySelector('.chartStats'));
    const chart = wrap.querySelector('.enhancedChart');

    function dailySlice(days) {
      const src = (points6m || []).filter(p => p && Number.isFinite(Number(p.close)));
      if (days >= 180) return src;
      if (!src.length) return [];
      const last = new Date(src[src.length - 1].date);
      return src.filter(p => (last - new Date(p.date)) / 86400000 <= days);
    }

    function labelForDate(v, intraday) {
      const d = new Date(v);
      if (intraday) return d.toLocaleDateString('nl-NL', { day: '2-digit', month: 'short' }) + ' ' + d.toLocaleTimeString('nl-NL', { hour: '2-digit', minute: '2-digit' });
      return d.toLocaleDateString('nl-NL', { day: '2-digit', month: 'short' });
    }

    function draw() {
      let source = range === '1D' ? (today || []) : range === '1W' ? (points1w || []) : dailySlice(range === '6M' ? 180 : range === '3M' ? 90 : 30);
      source = source.filter(p => p && Number.isFinite(Number(p.close)));
      if (source.length < 2) { chart.innerHTML = '<div class="chartEmpty"><span>Niet genoeg koersdata beschikbaar.</span></div>'; return; }
      const vals = source.map(p => Number(p.close));
      const min = Math.min(...vals), max = Math.max(...vals), span = max - min || Math.max(1, max * .01);
      const w = 960, h = 320, px = 18, py = 24;
      const coords = vals.map((v,i) => [px + (i/(vals.length-1))*(w-px*2), h-py-((v-min)/span)*(h-py*2)]);
      const path = coords.map(p => p.join(',')).join(' ');
      const first = vals[0], last = vals[vals.length-1], change = last/first-1;
      const intraday = range === '1W' || range === '1D';
      const step = Math.max(1, Math.floor((source.length - 1) / 4));
      const axis = [0, step, step*2, step*3, source.length-1].filter((v,i,a) => v < source.length && a.indexOf(v) === i);
      chart.innerHTML = `<div class="chartHeadline"><div><span>${range === '1D' ? 'VANDAAG' : range}</span><strong>${fmtPrice(last)}</strong></div><b class="${change >= 0 ? 'positive' : 'negative'}">${fmtPct(change)}</b></div><div class="chartCanvas"><svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" aria-label="Koersgrafiek"><polyline points="${path}" fill="none" stroke="currentColor" stroke-width="3" vector-effect="non-scaling-stroke"/>${coords.map((p,i) => `<circle class="chartPoint" cx="${p[0]}" cy="${p[1]}" r="${source.length > 80 ? 2.5 : 4}" data-index="${i}"/>`).join('')}</svg><div class="chartTooltip" hidden></div></div><div class="chartAxis">${axis.map(i => `<span>${esc(labelForDate(source[i].date, intraday))}</span>`).join('')}</div>`;
      const tooltip = chart.querySelector('.chartTooltip');
      chart.querySelectorAll('.chartPoint').forEach(point => point.addEventListener('mouseenter', () => {
        const i = Number(point.dataset.index), p = source[i];
        tooltip.hidden = false;
        tooltip.innerHTML = `<strong>${fmtPrice(p.close)}</strong><span>${esc(labelForDate(p.date, intraday))}</span>`;
        tooltip.style.left = `${Math.min(92, Math.max(8, coords[i][0] / w * 100))}%`;
        tooltip.style.top = `${Math.max(5, coords[i][1] / h * 100 - 10)}%`;
      }));
      chart.querySelector('.chartCanvas').addEventListener('mouseleave', () => { tooltip.hidden = true; });
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
    const median = row.analyst_target_median;
    const targetUpside = row.analyst_target_upside;
    const recommendation = row.analyst_recommendation || '—';
    const counts = [['Strong buy', row.analyst_strong_buy], ['Buy', row.analyst_buy], ['Hold', row.analyst_hold], ['Sell', row.analyst_sell], ['Strong sell', row.analyst_strong_sell]].filter(x => Number(x[1]) > 0);
    const spread = target && median ? Math.abs(target / median - 1) : null;
    const targetNote = spread != null && spread <= 0.10 ? `Gemiddeld ${fmtPrice(target)} · mediaan ${fmtPrice(median)}` : `Gemiddeld ${fmtPrice(target)} · mediaan ${fmtPrice(median)} · analisten lopen hier relatief uiteen`;
    el.innerHTML = `<div class="intelSummary"><div class="intelEyebrow">WAAROM NU EEN ALERT?</div><p>${esc(row.alert_summary || 'De scanner ziet een actuele koerssituatie die afwijkt van het normale patroon en tegelijk door meerdere onafhankelijke signalen wordt ondersteund.')}</p></div><div class="intelGrid"><div class="intelBlock"><span>ANALISTENCONSENSUS</span><div class="ratingLine"><strong class="${ratingClass(recommendation)}">${esc(recommendation)}</strong><small>${row.analyst_count ? `${row.analyst_count} beoordelingen` : 'Geen consensusaantal'}</small></div><div class="ratingBars">${counts.map(([name,n]) => `<div><span>${name}</span><b>${n}</b></div>`).join('')}</div></div><div class="intelBlock"><span>KOERSDOEL</span><div class="targetMain"><strong>${fmtPrice(target)}</strong><b class="${targetUpside >= 0 ? 'positive' : 'negative'}">${fmtPct(targetUpside)}</b></div><small>${esc(targetNote)}</small><div class="targetMeta"></div></div></div><div class="intelBlock intelChanges"><span>RECENTE ANALISTENACTIES</span>${changes.length ? `<div class="changeList">${changes.map(c => `<div><b>${esc(c.firm || 'Analist')}</b><span>${esc(c.action || '')}</span><small>${esc(c.from_grade || '')}${c.from_grade && c.to_grade ? ' → ' : ''}${esc(c.to_grade || '')}</small></div>`).join('')}</div>` : '<small>Geen recente wijzigingen beschikbaar.</small>'}</div>`;
    el.querySelector('.targetMeta').textContent = `${row.analyst_target_changes_30d || 0} targetwijzigingen in 30D`;
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
    makeChart(row.history_6m, row.history_1w, row.history_today, panel);
  }

  const observer = new MutationObserver(() => document.querySelectorAll('.detailPanel').forEach(enhance));
  observer.observe(document.body, { childList: true, subtree: true });
  document.querySelectorAll('.detailPanel').forEach(enhance);
})();
