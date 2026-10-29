// Opmaak en tekstopbouw voor de scannerpagina (Nederlands en Engels via t()). De regels zelf staan in het model, niet hier.
export const makeFmt = (lang) => {
  const loc = lang === 'en' ? 'en-GB' : 'nl-NL';
  const ok = (v) => v != null && Number.isFinite(Number(v));
  return {
    pct: (v, d = 1) => (ok(v) ? `${(Number(v) * 100).toFixed(d)}%` : '—'),
    signed: (v, d = 1) => (ok(v) ? `${Number(v) >= 0 ? '+' : '−'}${Math.abs(Number(v) * 100).toFixed(d)}%` : '—'),
    num: (v, d = 1) => (ok(v) ? Number(v).toFixed(d) : '—'),
    usd: (v, d = 2) => (ok(v) && Number(v) > 0 ? `$${Number(v).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d })}` : '—'),
    time: (v) => { if (!v) return '—'; const x = new Date(v); return Number.isNaN(x.getTime()) ? '—' : x.toLocaleTimeString(loc, { hour: '2-digit', minute: '2-digit' }); },
    date: (v) => { if (!v) return '—'; const x = new Date(v); return Number.isNaN(x.getTime()) ? String(v).slice(0, 10) : x.toLocaleDateString(loc); },
    int: (v) => Number(v).toLocaleString(loc),
  };
};

export function riskClass(r) {
  if (r.dip_speculative) return 'speculatief';
  const c = r.dip_context || {};
  const rg = c.revenue_growth != null && Math.abs(c.revenue_growth) < 5 ? c.revenue_growth : null;
  const fm = c.fcf_margin != null && Math.abs(c.fcf_margin) < 5 ? c.fcf_margin : null;
  if ((r.d52 != null && r.d52 < -0.37) || (rg != null && rg > 0.28)) return 'agressief';
  if (fm != null && fm > 0) return 'rustig';
  return 'gemengd';
}

export function earningsText(r, t) {
  const d = r.dip_context?.earnings_in_days;
  if (d == null) return '';
  return d <= 0 ? t('e_today') : d === 1 ? t('e_tomorrow') : t('e_days', { n: d });
}

export function missingList(r, t, f) {
  const a = [];
  if (r.dip != null && r.dip > 0.30) a.push(t('m_dip'));
  if (r.d52 != null && r.d52 > -0.15) a.push(t('m_52', { v: f.pct(r.d52, 0) }));
  if (r.dd30 != null && r.dd30 > -0.08) a.push(t('m_30', { v: f.pct(r.dd30, 0) }));
  return a;
}

export function whyNot(r, t, f, plek) {
  if (r.dip_signal) return '';
  if (r.dip_qualifies && !r.dip_excluded) {
    const k = plek.get(r.ticker);
    return k ? (k <= 15 ? t('w_rank_near', { k }) : t('w_rank', { k })) : t('w_outside');
  }
  if (r.dip_qualifies) {
    return { groei: t('w_growth'), speculatief: t('w_spec'), winst: t('w_cash'), sector: t('w_sector') }[r.dip_excluded] || '';
  }
  return missingList(r, t, f).join(', ');
}

export function shortfall(r) {
  let m = 0;
  if (r.dip != null) m = Math.max(m, (r.dip - 0.30) / 0.30);
  if (r.d52 != null) m = Math.max(m, (r.d52 + 0.15) / 0.15);
  if (r.dd30 != null) m = Math.max(m, (r.dd30 + 0.08) / 0.08);
  return m;
}

// Korte kenmerken voor in de lijst (alleen feiten, geen oordeel).
export function highlights(r, t, f) {
  const c = r.dip_context || {};
  const a = [];
  if (r.d52 != null) a.push(t('r_52', { v: f.pct(Math.abs(r.d52), 0) }));
  if (c.revenue_growth != null && Math.abs(c.revenue_growth) < 5) a.push(t('r_rev', { v: f.signed(c.revenue_growth, 0) }));
  return a.slice(0, 2).join(' · ');
}

export function supportList(r, t, f) {
  const c = r.dip_context || {};
  const a = [];
  if (r.d52 != null) a.push(t('s_d52', { v: f.pct(Math.abs(r.d52), 0) }));
  if (r.dd30 != null) a.push(t('s_d30', { v: f.pct(Math.abs(r.dd30), 0) }));
  if (c.rsi != null && c.rsi <= 35) a.push(t('s_rsi', { v: f.num(c.rsi, 0) }));
  if (c.revenue_growth != null && Math.abs(c.revenue_growth) < 5) a.push(t('s_rev', { v: f.signed(c.revenue_growth, 0) }));
  if (c.fcf_margin != null && c.fcf_margin > 0) a.push(t('s_fcf', { v: f.pct(c.fcf_margin, 0) }));
  if (c.pt_upside != null && c.pt_upside > 0) a.push(t('s_pt', { v: f.signed(c.pt_upside, 0), cons: c.grades_consensus ? t('s_pt_cons', { c: c.grades_consensus }) : '' }));
  if (c.analyst_up_30d > 0) a.push(t('s_up', { n: c.analyst_up_30d }));
  return a;
}

export function watchList(r, t, f) {
  const c = r.dip_context || {};
  const a = [];
  const atr = Number(r.atr_pct) > 0 ? Number(r.atr_pct) : null;
  const k = riskClass(r);
  if (r.earnings_warning) a.push(t('l_earn', { e: earningsText(r, t) }));
  if (r.return_5d != null && r.return_5d <= -0.05) a.push(t('l_fall', { v: f.signed(r.return_5d, 0) }));
  if (c.stock_specific) a.push(t('l_spec', { v: f.pct(c.rel30, 0) }));
  if (c.post_earnings) a.push(t('l_post', { n: c.days_since_earnings }));
  if (k === 'agressief' || k === 'speculatief') a.push(t('l_vol', { kind: k === 'speculatief' ? t('l_vol_spec') : t('l_vol_vol'), atr: atr != null ? t('l_vol_atr', { v: f.pct(atr, 1) }) : '' }));
  if (c.analyst_down_30d > 0) a.push(t('l_down', { n: c.analyst_down_30d }));
  if (c.pt_upside != null && c.pt_upside <= 0) a.push(t('l_above'));
  return a;
}
