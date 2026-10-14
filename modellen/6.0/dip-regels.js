// Dip-regels (model 6.0): koop-alerts volgens de geteste dip-regels, daarna strenge selectie tot maximaal 5 BUY-alerts.
const isNa = (v) => v === null || v === undefined || (typeof v === 'number' && !Number.isFinite(v));
const MODEL_VERSION = '6.0-dip';
const MAX_BUY = 5, STICKY_BONUS = 0.01, MIN_GROWTH = 0.10;
const SPEC = { dipMax: 0.05, minUpside: 0.25 };
const EXCLUDED_SECTORS = { 'Real Estate': true };
const RULES = { dipMax: 0.30, dd30Max: -0.08, d52Max: -0.15, aggressiveD52: -0.30, aggressiveGrowth: 0.25, minBars: 300, win: 250, minGrowth: MIN_GROWTH, positiveFcf: true, speculative: SPEC };

function ewmFull(arr, alpha) {
  const o = new Array(arr.length); let p = null;
  for (let i = 0; i < arr.length; i++) {
    const x = arr[i];
    if (isNa(x)) { o[i] = p === null ? NaN : p; continue; }
    p = p === null ? x : (1 - alpha) * p + alpha * x; o[i] = p;
  }
  return o;
}
function dipNow(closes) {
  const c = closes.map(Number), n = c.length;
  if (n < RULES.minBars) return null;
  const g = [NaN], ls = [NaN];
  for (let i = 1; i < n; i++) { const d = c[i] - c[i - 1]; g.push(Math.max(d, 0)); ls.push(-Math.min(d, 0)); }
  const ag = ewmFull(g, 1 / 14), al = ewmFull(ls, 1 / 14);
  const rsi = c.map((_, i) => (i < 14 || al[i] === 0) ? NaN : 100 - 100 / (1 + ag[i] / al[i]));
  const z20 = new Array(n).fill(NaN), s50 = new Array(n).fill(NaN), dd30 = new Array(n).fill(NaN);
  for (let i = 0; i < n; i++) {
    if (i >= 19) { let m = 0; for (let k = i - 19; k <= i; k++) m += c[k]; m /= 20; let v = 0; for (let k = i - 19; k <= i; k++) v += (c[k] - m) * (c[k] - m); const sd = Math.sqrt(v / 19); z20[i] = sd > 0 ? (c[i] - m) / sd : NaN; }
    if (i >= 49) { let m = 0; for (let k = i - 49; k <= i; k++) m += c[k]; s50[i] = c[i] / (m / 50) - 1; }
    if (i >= 29) { let mx = -Infinity; for (let k = i - 29; k <= i; k++) if (c[k] > mx) mx = c[k]; dd30[i] = c[i] / mx - 1; }
  }
  const i = n - 1;
  const pct = (arr) => { let cnt = 0, tot = 0; for (let k = i - RULES.win; k < i; k++) { const x = arr[k]; if (isNa(x)) continue; tot++; if (x <= arr[i]) cnt++; } return tot >= 200 && !isNa(arr[i]) ? cnt / tot : NaN; };
  const p = [pct(z20), pct(rsi), pct(s50), pct(dd30)];
  if (p.some(isNa)) return null;
  let mx52 = -Infinity; for (let k = Math.max(0, n - 252); k < n; k++) if (c[k] > mx52) mx52 = c[k];
  return { dip: p.reduce((a, b) => a + b, 0) / 4, dd30: dd30[i], d52: c[i] / mx52 - 1, rsi: rsi[i], z20: z20[i] };
}

const sc = $input.first().json;
const rowsIn = $('Haal data uit Supabase').all().map((x) => x.json);
const cache = {}, daily = {};
let prevSel = [];
for (const r of rowsIn) {
  if (r.bars) cache[r.symbol] = r;
  else if (r.as_of && r.ticker) { if (!daily[r.ticker] || r.as_of > daily[r.ticker].as_of) daily[r.ticker] = r; }
  else if (Object.prototype.hasOwnProperty.call(r, 'buy_selection')) prevSel = Array.isArray(r.buy_selection) ? r.buy_selection : [];
}
const generatedAt = sc.generated_at;
const nowMs = Date.parse(generatedAt);
const byTicker = {};
for (const r of sc.payload.results) byTicker[r.ticker] = r;
const qual = [];
let evaluated = 0, noData = 0;
for (const res of sc.results) {
  const t = res.ticker, row = byTicker[t], c = cache[t];
  if (!row || !c || !c.bars) { noData++; continue; }
  const closes = c.bars.c.slice();
  if (c.last_date === res.last_bar) closes[closes.length - 1] = res.price; else closes.push(res.price);
  const d = dipNow(closes);
  if (!d) { noData++; row.dip = null; row.dip_signal = false; continue; }
  evaluated++;
  const ok = d.dip <= RULES.dipMax && d.dd30 <= RULES.dd30Max && d.d52 <= RULES.d52Max;
  row.dip = +d.dip.toFixed(3); row.dd30 = +d.dd30.toFixed(4); row.d52 = +d.d52.toFixed(4); row.dip_signal = false; row.dip_qualifies = ok;
  row.dip_short = +Math.max(0, (d.dip - RULES.dipMax) / RULES.dipMax, (d.d52 - RULES.d52Max) / -RULES.d52Max, (d.dd30 - RULES.dd30Max) / -RULES.dd30Max).toFixed(3);
  if (!ok) continue;
  const fund = res.fund || {}, an = res.an || {}, dl = daily[t] || {};
  const rgRaw = isNa(fund.revenue_growth) ? null : fund.revenue_growth;
  const fmRaw = isNa(fund.fcf_margin) ? null : fund.fcf_margin;
  const rg = rgRaw === null || Math.abs(rgRaw) >= 5 ? null : rgRaw;
  const fm = fmRaw === null || Math.abs(fmRaw) >= 5 ? null : fmRaw;
  const cls = (d.d52 < -0.37 || (rg !== null && rg > 0.28)) ? 'agressief' : (fm !== null && fm > 0) ? 'rustig' : 'gemengd';
  const profile = (d.d52 <= RULES.aggressiveD52 || (rg !== null && rg > RULES.aggressiveGrowth)) ? 'agressief' : 'rustig';
  const pt = Number(dl.pt_consensus);
  const upside = pt > 0 ? pt / res.price - 1 : null;
  const consBuy = /buy/i.test(String(dl.grades_consensus || ''));
  const nextE = an.next_earnings_date || null;
  const eDays = nextE ? Math.round((Date.parse(String(nextE).slice(0, 10) + 'T00:00:00Z') - nowMs) / 86400000) : null;
  row.dip_profile = profile;
  row.dip_class = cls;
  // Cijfers binnen 7 dagen: alleen een waarschuwing op de kaart, geen reden om uit te sluiten.
  row.earnings_warning = eDays !== null && eDays >= -1 && eDays <= 7;
  // Uitsluiting: vastgoed/dividend, omzetgroei onder 10% (of onbekend), onbekende vrije kasstroom.
  // Negatieve vrije kasstroom = speculatief: alleen toegestaan bij een veel diepere dip, analisten Buy en minstens 25% koersdoel-upside.
  const spec = fmRaw !== null && fmRaw <= 0;
  row.dip_speculative = spec;
  row.dip_excluded = EXCLUDED_SECTORS[res.sector] ? 'sector' : (rgRaw === null || rgRaw < MIN_GROWTH) ? 'groei' : fmRaw === null ? 'winst' : (spec && !(d.dip <= SPEC.dipMax && consBuy && upside !== null && upside >= SPEC.minUpside)) ? 'speculatief' : null;
  row.dip_context = {
    pt_upside: upside === null ? null : +upside.toFixed(3),
    grades_consensus: dl.grades_consensus || null,
    analyst_up_30d: an.analyst_bullish_changes_30d ?? null, analyst_down_30d: an.analyst_bearish_changes_30d ?? null,
    pt_change_3m: an.target_change === null || an.target_change === undefined ? null : +an.target_change.toFixed(3),
    next_earnings: nextE, earnings_in_days: eDays,
    revenue_growth: rgRaw, gross_margin: isNa(fund.gross_margin) ? null : fund.gross_margin, fcf_margin: fmRaw,
    sector: res.sector || null, rsi: +d.rsi.toFixed(1)
  };
  qual.push(row);
}
// Selectie: omzetgroei minimaal 10%, positieve vrije kasstroom (of speculatief met extra eisen), geen vastgoed.
// Rangschikking op diepte van de dip (diepste eerst), geen limiet per sector, maximaal 5 in totaal.
// Elke scan wordt opnieuw gerangschikt; aandelen die al in de lijst staan krijgen een kleine bonus (0,01) tegen onnodig wisselen.
const eligible = qual.filter((r) => !r.dip_excluded);
const prevSince = {};
for (const p of prevSel) if (p && p.t && p.since) prevSince[p.t] = p.since;
const key = (r) => r.dip - (prevSince[r.ticker] ? STICKY_BONUS : 0);
const ranked = eligible.slice().sort((a, b) => key(a) - key(b));
const selected = ranked.slice(0, MAX_BUY), sinceBy = {};
for (const r of selected) sinceBy[r.ticker] = prevSince[r.ticker] || generatedAt;
const selSet = {};
selected.forEach((r, i) => { selSet[r.ticker] = true; r.dip_signal = true; r.dip_rank = i + 1; });
const nextUp = {};
ranked.filter((r) => !selSet[r.ticker]).slice(0, 5).forEach((r) => { nextUp[r.ticker] = true; });
for (const r of sc.payload.results) {
  if (selSet[r.ticker]) r.signal = 'ALERT';
  else if (nextUp[r.ticker] || (!r.dip_qualifies && r.dip_short !== undefined && r.dip_short <= 0.25)) r.signal = 'WATCH';
  else r.signal = 'NO_SIGNAL';
}
const sigBy = {}; for (const r of sc.payload.results) sigBy[r.ticker] = r.signal;
const logRows = sc.logRows.map((l) => ({ ...l, signal: sigBy[l.ticker] || l.signal }));
const breadthPct = evaluated ? qual.length / evaluated : 0;
const alertCandidates = selected.map((r) => {
  const score = +(100 * (1 - r.dip)).toFixed(1);
  return {
    ticker: r.ticker, company_name: r.company_name, alert_timestamp: generatedAt, entry_timestamp: generatedAt,
    alert_price: r.price, score, initial_score: score, peak_score: score, peak_score_at: generatedAt,
    technical_score: score, fundamental_score: null, model_version: MODEL_VERSION, status: 'PENDING',
    confidence: null, risk_reward: null, stop_level: null, target_level: +(r.price * 1.10).toFixed(2),
  };
});
const payload = { ...sc.payload, model_version: MODEL_VERSION, alert_count: selected.length, dip_rules: RULES, alert_threshold: null,
  buy_selection: selected.map((r) => ({ t: r.ticker, since: sinceBy[r.ticker] })),
  dip_breadth: { count: qual.length, selected: selected.length, evaluated, pct: +breadthPct.toFixed(3), market_wide: breadthPct >= 0.10, top_n: MAX_BUY } };
return [{ json: { ...sc, payload, logRows, alertCandidates, model_version: MODEL_VERSION,
  dip_summary: { geevalueerd: evaluated, geen_data: noData, voldoet: qual.length, signalen: selected.map((r) => ({ t: r.ticker, rang: r.dip_rank, ew: r.earnings_warning, prijs: r.price, dip: r.dip, dd30: r.dd30, d52: r.d52, klasse: r.dip_class, ctx: r.dip_context })) } } }];
