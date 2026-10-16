const M = (() => { const module = { exports: {} };
const isNa = (v) => v === null || v === undefined || (typeof v === 'number' && !Number.isFinite(v));
const clip = (x, lo, hi) => Math.min(hi, Math.max(lo, x));
const NAN = NaN;
function pctChange(arr, n) {
  return arr.map((v, i) => (i >= n && !isNa(v) && !isNa(arr[i - n]) ? v / arr[i - n] - 1 : NAN));
}
function rollingMean(arr, w, minPeriods) {
  const mp = minPeriods === undefined ? w : minPeriods;
  return arr.map((_, i) => {
    const s = arr.slice(Math.max(0, i - w + 1), i + 1).filter((x) => !isNa(x));
    return s.length >= mp && s.length > 0 ? s.reduce((a, b) => a + b, 0) / s.length : NAN;
  });
}
function rollingStd(arr, w) {
  return arr.map((_, i) => {
    if (i < w - 1) return NAN;
    const s = arr.slice(i - w + 1, i + 1);
    if (s.some(isNa)) return NAN;
    const m = s.reduce((a, b) => a + b, 0) / w;
    return Math.sqrt(s.reduce((a, b) => a + (b - m) * (b - m), 0) / (w - 1));
  });
}
function rollingMax(arr, w, minPeriods) {
  return arr.map((_, i) => {
    const s = arr.slice(Math.max(0, i - w + 1), i + 1).filter((x) => !isNa(x));
    return s.length >= minPeriods && s.length > 0 ? Math.max(...s) : NAN;
  });
}
function rollingMin(arr, w, minPeriods) {
  return arr.map((_, i) => {
    const s = arr.slice(Math.max(0, i - w + 1), i + 1).filter((x) => !isNa(x));
    return s.length >= minPeriods && s.length > 0 ? Math.min(...s) : NAN;
  });
}
function ewm(arr, alpha, minPeriods) {
  const out = new Array(arr.length).fill(NAN);
  let prev = null;
  let count = 0;
  for (let i = 0; i < arr.length; i++) {
    const x = arr[i];
    if (isNa(x)) { if (prev !== null) out[i] = count >= minPeriods ? prev : NAN; continue; }
    prev = prev === null ? x : (1 - alpha) * prev + alpha * x;
    count += 1;
    out[i] = count >= minPeriods ? prev : NAN;
  }
  return out;
}
function rsi(close, period) {
  const gain = [NAN], loss = [NAN];
  for (let i = 1; i < close.length; i++) {
    const d = close[i] - close[i - 1];
    gain.push(isNa(d) ? NAN : Math.max(d, 0));
    loss.push(isNa(d) ? NAN : -Math.min(d, 0));
  }
  const ag = ewm(gain, 1 / period, period);
  const al = ewm(loss, 1 / period, period);
  return close.map((_, i) => {
    if (isNa(ag[i]) || isNa(al[i]) || al[i] === 0) return NAN;
    const rs = ag[i] / al[i];
    return 100 - 100 / (1 + rs);
  });
}
function lastIndicators(bars) {
  const close = bars.c.map(Number), high = bars.h.map(Number), low = bars.l.map(Number), vol = bars.v.map(Number);
  const n = close.length;
  const last = (a) => a[n - 1];
  const out = {};
  out.Close = last(close);
  out.return_5d = last(pctChange(close, 5));
  out.return_7d = last(pctChange(close, 7));
  out.return_14d = last(pctChange(close, 14));
  out.return_20d = last(pctChange(close, 20));
  out.return_30d = last(pctChange(close, 30));
  const sma20 = rollingMean(close, 20);
  const std20 = rollingStd(close, 20);
  out.sma_20 = last(sma20);
  out.z_score = (out.Close - out.sma_20) / (last(std20) === 0 ? NAN : last(std20));
  out.rsi_14 = last(rsi(close, 14));
  const tr = close.map((_, i) => {
    const hl = high[i] - low[i];
    if (i === 0) return hl;
    return Math.max(hl, Math.abs(high[i] - close[i - 1]), Math.abs(low[i] - close[i - 1]));
  });
  const atr = last(ewm(tr, 1 / 14, 14));
  out.atr_pct = atr / out.Close;
  out.volume_ratio = vol[n - 1] / last(rollingMean(vol, 20));
  for (const [w, label] of [[21, '1m'], [63, '3m'], [126, '6m'], [252, '52w']]) {
    const hi = last(rollingMax(close, w, Math.min(w, 20)));
    out['high_' + label] = hi;
    out['distance_' + label + '_high'] = out.Close / hi - 1;
  }
  for (const [w, label] of [[20, '20d'], [60, '60d'], [120, '120d']]) {
    const s = last(rollingMin(low, w, Math.min(w, 20)));
    out['support_' + label] = s;
    out['distance_support_' + label] = out.Close / s - 1;
  }
  return out;
}
function sectorRelativeStrength(stockClose, sectorClose) {
  const a = (stockClose || []).filter((x) => !isNa(x));
  const b = (sectorClose || []).filter((x) => !isNa(x));
  if (a.length < 21 || b.length < 21) return null;
  return (a[a.length - 1] / a[a.length - 21] - 1) - (b[b.length - 1] / b[b.length - 21] - 1);
}
function bearRegime(spyClose) {
  const c = (spyClose || []).filter((x) => !isNa(x));
  if (c.length < 200) return false;
  const sma = c.slice(-200).reduce((a, b) => a + b, 0) / 200;
  return c[c.length - 1] < sma;
}
const clamp = (x, lo = 0, hi = 1) => (isNa(x) ? 0 : clip(x, lo, hi));
const lowIsGood = (v, start, extreme) => (isNa(v) ? 0 : clamp((start - v) / (start - extreme)));
const highIsGood = (v, start, extreme) => (isNa(v) ? 0 : clamp((v - start) / (extreme - start)));
function neutralCenteredLow(value, start, extreme) {
  if (isNa(value)) return 0.5;
  const span = Math.abs(start - extreme);
  if (span === 0) return 0.5;
  if (value <= extreme) return 1.0;
  if (value >= start + span) return 0.0;
  if (value < start) return 0.5 + 0.5 * (start - value) / span;
  return 0.5 - 0.5 * (value - start) / span;
}
function technicalSupportComponent(r) {
  const vals = [r.distance_support_20d, r.distance_support_60d, r.distance_support_120d].filter((x) => !isNa(x));
  if (!vals.length) return 0.5;
  return vals.reduce((a, x) => a + neutralCenteredLow(x, 0.10, 0.0), 0) / vals.length;
}
function weightedScore(components, weights) {
  const usable = Object.entries(weights).filter(([k]) => k in components && !isNa(components[k]));
  const total = usable.reduce((a, [, w]) => a + w, 0);
  if (total <= 0) return 0;
  return 100 * usable.reduce((a, [k, w]) => a + components[k] * w, 0) / total;
}
function scoreRange(value, zeroPoint, fullPoint) {
  if (isNa(value)) return null;
  const v = Number(value);
  if (fullPoint > zeroPoint) {
    if (v <= zeroPoint) return 0.0;
    if (v >= fullPoint) return 100.0;
    return 100.0 * (v - zeroPoint) / (fullPoint - zeroPoint);
  }
  if (v >= zeroPoint) return 0.0;
  if (v <= fullPoint) return 100.0;
  return 100.0 * (zeroPoint - v) / (zeroPoint - fullPoint);
}
function weightedOrNone(components, weights) {
  const usable = Object.entries(weights).filter(([k]) => components[k] !== null && components[k] !== undefined);
  const totalWeight = Object.values(weights).reduce((a, b) => a + b, 0);
  if (!usable.length || totalWeight <= 0) return [null, 0.0];
  const used = usable.reduce((a, [, w]) => a + w, 0);
  return [usable.reduce((a, [k, w]) => a + components[k] * w, 0) / used, used / totalWeight];
}
function drawdownLeg(value, fullPoint) {
  if (isNa(value)) return null;
  if (value >= 0) return 0.0;
  return clip(value / fullPoint, 0, 1) * 100;
}
function dislocationScore(r) {
  let legs = [drawdownLeg(r.return_7d, -0.11), drawdownLeg(r.return_14d, -0.15), drawdownLeg(r.return_30d, -0.20)].filter((x) => x !== null);
  let drawdown = null;
  if (legs.length) {
    const strongest = Math.max(...legs);
    const others = legs.filter((v) => v !== strongest);
    const mean = others.length ? others.reduce((a, b) => a + b, 0) / others.length : strongest;
    drawdown = 0.70 * strongest + 0.30 * mean;
  }
  const high52 = drawdownLeg(r.distance_52w_high, -0.35);
  const [score] = weightedOrNone({ drawdown, high52 }, { drawdown: 0.65, high52: 0.35 });
  return score !== null ? score : 0.0;
}
function confirmationScore(r) {
  const components = {
    rsi_14: lowIsGood(r.rsi_14, 55, 30),
    z_score: lowIsGood(r.z_score, -0.3, -2.0),
    volume_ratio: highIsGood(r.volume_ratio, 1.0, 2.5),
    support: technicalSupportComponent(r),
    sector_strength: highIsGood(r.sector_relative_strength_20d, 0.0, 0.20),
  };
  return weightedScore(components, { rsi_14: 0.33, z_score: 0.27, volume_ratio: 0.18, support: 0.18, sector_strength: 0.09 });
}
function newTechnicalScore(r) {
  const multiplier = 0.70 + (confirmationScore(r) / 100.0) * 0.45;
  return clip(dislocationScore(r) * multiplier, 0, 100);
}
function fundamentalsScoreV2(f) {
  if (!f || !Object.keys(f).length) return [null, 0.0];
  const components = {
    revenue_growth: scoreRange(f.revenue_growth, -0.05, 0.30),
    eps_growth: scoreRange(f.eps_growth, -0.10, 0.30),
    fcf_margin: scoreRange(f.fcf_margin, -0.05, 0.20),
    net_margin: scoreRange(f.net_margin, 0.0, 0.25),
    gross_margin: scoreRange(f.gross_margin, 0.20, 0.60),
    roe: scoreRange(f.roe, 0.0, 0.30),
    debt_equity: scoreRange(f.debt_equity, 2.0, 0.25),
  };
  return weightedOrNone(components, { revenue_growth: 0.20, eps_growth: 0.20, fcf_margin: 0.20, net_margin: 0.15, gross_margin: 0.10, roe: 0.10, debt_equity: 0.05 });
}
function valuationScoreV2(f) {
  if (!f || !Object.keys(f).length) return [null, 0.0];
  const eps = f.eps;
  if (!isNa(eps) && eps <= 0) {
    const s = scoreRange(f.ev_sales, 12.0, 2.0);
    return [s, s !== null ? 1.0 : 0.0];
  }
  let peScore;
  if (!isNa(f.pe_vs_sector)) {
    peScore = scoreRange(f.pe_vs_sector, 1.75, 0.75);
  } else {
    const fwd = !isNa(f.forward_pe) ? f.forward_pe : f.pe;
    peScore = scoreRange(fwd, 45.0, 12.0);
  }
  const pegScore = scoreRange(f.peg, 3.0, 1.0);
  return weightedOrNone({ pe: peScore, peg: pegScore }, { pe: 0.60, peg: 0.40 });
}
function analystDirectionScore(a) {
  if (!a || !Object.keys(a).length) return [null, 0.0];
  const bull = a.analyst_bullish_changes_30d, bear = a.analyst_bearish_changes_30d;
  if (isNa(bull) && isNa(bear)) return [null, 0.0];
  const net = (bull || 0) - (bear || 0);
  return [scoreRange(net, -3, 3), (!bull && !bear) ? 0.5 : 1.0];
}
function analystDirectionScoreV2(a) {
  if (!a || !Object.keys(a).length) return [null, 0.0];
  const grades = !isNa(a.grade_net_weighted) && a.grade_events_90d > 0 ? scoreRange(a.grade_net_weighted, -3, 3) : null;
  const targets = !isNa(a.target_change) ? scoreRange(a.target_change, -0.10, 0.10) : null;
  return weightedOrNone({ grades, targets }, { grades: 0.60, targets: 0.40 });
}
function earningsAdjustment(a, nowMs) {
  if (!a || !Object.keys(a).length) return 0.0;
  const now = nowMs === undefined ? Date.now() : nowMs;
  let adj = 0.0;
  const surprise = a.last_earnings_surprise_pct;
  if (!isNa(surprise)) {
    const s = clip(Number(surprise), -60, 100);
    let magnitude;
    if (s <= -7) magnitude = -5.0;
    else if (s >= 23) magnitude = 5.0;
    else if (s <= 8) magnitude = -5.0 * (8 - s) / 15.0;
    else magnitude = 5.0 * (s - 8) / 15.0;
    let decay = 1.0;
    if (a.last_earnings_date) {
      const t = Date.parse(String(a.last_earnings_date).length <= 10 ? a.last_earnings_date + 'T00:00:00Z' : a.last_earnings_date);
      if (Number.isFinite(t)) decay = clip(1.0 - Math.floor((now - t) / 86400000) / 120.0, 0, 1);
    }
    adj += magnitude * decay;
  }
  if (a.next_earnings_date) {
    const t = Date.parse(String(a.next_earnings_date).length <= 10 ? a.next_earnings_date + 'T00:00:00Z' : a.next_earnings_date);
    if (Number.isFinite(t)) {
      const daysOut = Math.floor((t - now) / 86400000);
      if (daysOut >= 0 && daysOut <= 7) adj -= 2.5;
    }
  }
  return clip(adj, -5.0, 5.0);
}
function confidenceScore(components, completeness, weights) {
  let wc = 0, tw = 0;
  for (const [k, w] of Object.entries(weights)) { wc += w * (completeness[k] || 0); tw += w; }
  wc = tw ? wc / tw : 0;
  const avail = Object.entries(components).filter(([, v]) => v !== null && v !== undefined);
  let agreement;
  if (avail.length < 2) agreement = 0.6;
  else {
    const wsum = avail.reduce((a, [k]) => a + (weights[k] || 0), 0);
    if (wsum <= 0) agreement = 0.6;
    else {
      const mean = avail.reduce((a, [k, v]) => a + (weights[k] || 0) * v, 0) / wsum;
      const variance = avail.reduce((a, [k, v]) => a + (weights[k] || 0) * (v - mean) ** 2, 0) / wsum;
      agreement = clip(1.0 - Math.sqrt(variance) / 40.0, 0.3, 1.0);
    }
  }
  return clip(wc * agreement * 100.0, 0.0, 100.0);
}
const pyRound = (x, d) => Number(x.toFixed(d));
function riskReward(r, opts) {
  const price = r.Close;
  if (isNa(price)) return { stop: null, target: null, risk_reward: null };
  const atrStop = !isNa(r.atr_pct) ? price - 1.5 * r.atr_pct * price : null;
  const sup = [r.support_20d, r.support_60d].filter((x) => !isNa(x));
  const supportStop = sup.length ? Math.max(...sup) : null;
  const cands = [atrStop, supportStop].filter((x) => x !== null);
  let stop = cands.length ? Math.max(...cands) : null;
  if (opts && opts.minStopAtr && !isNa(r.atr_pct)) {
    const floorStop = price - opts.minStopAtr * r.atr_pct * price;
    stop = stop === null ? floorStop : Math.min(stop, floorStop);
  }
  const res = [r.high_1m, r.high_3m].filter((x) => !isNa(x) && x > price);
  const target = res.length ? Math.max(...res) : null;
  if (stop === null || target === null || stop >= price) {
    return { stop: stop !== null ? pyRound(stop, 2) : null, target: target !== null ? pyRound(target, 2) : null, risk_reward: null };
  }
  return { stop: pyRound(stop, 2), target: pyRound(target, 2), risk_reward: pyRound((target - price) / (price - stop), 2) };
}
function assembleNewScore(row, fundamentals, analyst, bear, nowMs, opts) {
  opts = opts || {};
  const technical = newTechnicalScore(row);
  const [fundScore, fundC] = fundamentalsScoreV2(fundamentals);
  const [valScore, valC] = valuationScoreV2(fundamentals);
  const [anScore, anC] = opts.analystV2 ? analystDirectionScoreV2(analyst) : analystDirectionScore(analyst);
  const earningsAdj = earningsAdjustment(analyst, nowMs);
  const components = { technical, fundamentals: fundScore, valuation: valScore, analyst: anScore };
  const weights = { technical: 0.55, fundamentals: 0.30, valuation: 0.10, analyst: 0.05 };
  let [overall] = weightedOrNone(components, weights);
  if (overall === null) overall = technical;
  overall = clip(overall + earningsAdj, 0, 100);
  const regimeMultiplier = bear ? 0.8 : 1.0;
  overall = pyRound(overall * regimeMultiplier, 1);
  const confidence = confidenceScore(components, { technical: 1.0, fundamentals: fundC, valuation: valC, analyst: anC }, weights);
  const rr = riskReward(row, opts);
  const fcf = fundamentals ? fundamentals.fcf : null;
  const de = fundamentals ? fundamentals.debt_equity : null;
  const gate = !isNa(fcf) && fcf < 0 && !isNa(de) && de > 1.5;
  const r1 = (x) => (x === null ? null : pyRound(x, 1));
  return {
    technical_score_v2: pyRound(technical, 1),
    fundamentals_score_v2: r1(fundScore),
    valuation_score_v2: r1(valScore),
    analyst_direction_score: r1(anScore),
    earnings_adjustment: pyRound(earningsAdj, 1),
    overall_score_v2: overall,
    confidence: pyRound(confidence, 1),
    risk_reward: rr.risk_reward, stop_level: rr.stop, target_level: rr.target,
    gate_excluded: gate, regime_multiplier: regimeMultiplier,
  };
}
function extraIndicators(bars, spy) {
  const close = bars.c.map(Number);
  const n = close.length;
  const last = (a) => a[n - 1];
  const out = {};
  out.return_1d = last(pctChange(close, 1));
  out.return_3d = last(pctChange(close, 3));
  out.return_10d = last(pctChange(close, 10));
  for (const w of [20, 50, 200]) {
    const sma = last(rollingMean(close, w));
    out['distance_sma' + w] = close[n - 1] / sma - 1;
  }
  const emaSeries = (arr, span) => ewm(arr, 2 / (span + 1), 1);
  const e12 = emaSeries(close, 12), e26 = emaSeries(close, 26);
  const macd = e12.map((v, i) => v - e26[i]);
  const sig = emaSeries(macd, 9);
  const hist = macd.map((v, i) => v - sig[i]);
  out.macd = last(macd);
  out.macd_signal = last(sig);
  out.macd_histogram = last(hist);
  out.macd_histogram_change = n >= 2 ? hist[n - 1] - hist[n - 2] : NAN;
  out.rsi_7 = last(rsi(close, 7));
  out.rsi_21 = last(rsi(close, 21));
  const ret1 = pctChange(close, 1);
  const r20 = ret1.slice(-20);
  out.volatility_20d = r20.length === 20 && !r20.some(isNa)
    ? Math.sqrt(r20.reduce((a, x) => a + (x - r20.reduce((p, q) => p + q, 0) / 20) ** 2, 0) / 19) * Math.sqrt(252) : NAN;
  const sma20 = last(rollingMean(close, 20)), std20 = last(rollingStd(close, 20));
  const band = 4 * std20;
  out.bollinger_pct = band > 0 ? (close[n - 1] - (sma20 - 2 * std20)) / band : NAN;
  out.bollinger_width = band > 0 ? band / sma20 : NAN;
  const hiL = Number(bars.h[n - 1]), loL = Number(bars.l[n - 1]);
  out.close_location = hiL - loL > 0 ? (close[n - 1] - loL) / (hiL - loL) : NAN;
  const vol = bars.v.map(Number);
  out.volume_ratio_5d = vol[n - 1] / last(rollingMean(vol, 5));
  out.relative_strength_20d = NAN;
  out.relative_strength_5d = NAN;
  if (spy && spy.d && bars.d) {
    const m = new Map();
    spy.d.forEach((d, i) => m.set(d, Number(spy.c[i])));
    let prev = NAN;
    const b = bars.d.map((d) => { if (m.has(d)) prev = m.get(d); return prev; });
    const b20 = last(pctChange(b, 20)), b5 = last(pctChange(b, 5));
    out.relative_strength_20d = last(pctChange(close, 20)) - b20;
    out.relative_strength_5d = last(pctChange(close, 5)) - b5;
  }
  return out;
}
module.exports = { extraIndicators, lastIndicators, sectorRelativeStrength, bearRegime, assembleNewScore };
return module.exports; })();
const F = (() => { const module = { exports: {} };
const isNa = (v) => v === null || v === undefined || (typeof v === 'number' && !Number.isFinite(v));
const num = (v) => (isNa(v) || v === '' ? null : (Number.isFinite(Number(v)) ? Number(v) : null));
const DAY = 86400000;
const dayMs = (s) => Date.parse(String(s).slice(0, 10) + 'T00:00:00Z');
function prepareQuarters(rows, asOf) {
  const cutoff = asOf ? dayMs(asOf) : Infinity;
  const q = (rows || [])
    .filter((r) => r.period_end && (!r.filing_date ? true : dayMs(r.filing_date) <= cutoff) && dayMs(r.period_end) <= cutoff)
    .sort((a, b) => (a.period_end < b.period_end ? 1 : -1));
  const seen = new Set();
  return q.filter((r) => (seen.has(r.period_end) ? false : (seen.add(r.period_end), true)));
}
function ttm(q, field, offset) {
  const part = q.slice(offset, offset + 4);
  if (part.length < 4) return null;
  for (let i = 0; i < 3; i++) {
    const gap = (dayMs(part[i].period_end) - dayMs(part[i + 1].period_end)) / DAY;
    if (gap < 70 || gap > 115) return null;
  }
  let sum = 0;
  for (const r of part) {
    const v = num(r[field]);
    if (v === null) return null;
    sum += v;
  }
  return sum;
}
function growth(now, then) {
  if (now === null || then === null || then === 0) return null;
  return (now - then) / Math.abs(then);
}
function isFresh(q, asOf) {
  if (!q.length) return false;
  const ref = asOf ? dayMs(asOf) : Date.now();
  return (ref - dayMs(q[0].period_end)) / DAY <= 200;
}
function buildFundamentals(quarterRows, daily, price, sectorMedians, asOf, opts) {
  opts = opts || {};
  const q = prepareQuarters(quarterRows, asOf);
  const f = {};
  if (!q.length || !isFresh(q, asOf)) return f;
  const rev = ttm(q, 'revenue', 0), revPrev = ttm(q, 'revenue', 4);
  const ni = ttm(q, 'net_income', 0);
  const gp = ttm(q, 'gross_profit', 0);
  const fcf = ttm(q, 'fcf', 0);
  const eps = ttm(q, 'eps_diluted', 0), epsPrev = ttm(q, 'eps_diluted', 4);
  const equity = num(q[0].equity), debt = num(q[0].total_debt), cash = num(q[0].cash);
  f.revenue_growth = rev !== null && revPrev !== null && revPrev > 0 ? growth(rev, revPrev) : null;
  f.eps_growth = growth(eps, epsPrev);
  f.net_margin = rev !== null && rev > 0 && ni !== null ? ni / rev : null;
  f.gross_margin = rev !== null && rev > 0 && gp !== null ? gp / rev : null;
  f.fcf = fcf;
  f.fcf_margin = rev !== null && rev > 0 && fcf !== null ? fcf / rev : null;
  f.roe = ni !== null && equity !== null && equity > 0 ? ni / equity : null;
  f.debt_equity = debt !== null && equity !== null && equity > 0 ? debt / equity : null;
  f.negative_equity = equity !== null && equity <= 0;
  f.eps = eps;
  const d = daily || {};
  const pos = (v) => (num(v) !== null && num(v) > 0 ? num(v) : null);
  f.pe = pos(d.pe);
  f.peg = pos(d.peg);
  const estEps = pos(d.est_eps_cy);
  f.forward_pe = estEps !== null && price > 0 ? price / estEps : null;
  const mcap = pos(d.market_cap);
  if (mcap !== null && rev !== null && rev > 0) {
    const ev = mcap + (debt || 0) - (cash || 0);
    f.ev_sales = ev > 0 ? ev / rev : null;
  } else f.ev_sales = null;
  const med = d.sector && sectorMedians ? sectorMedians[d.sector] : null;
  f.pe_vs_sector = f.pe !== null && med ? f.pe / med : null;
  f.sector = d.sector || null;
  if (opts.financialsNoFcf && f.sector === 'Financial Services') { f.fcf = null; f.fcf_margin = null; f.fcf_excluded = true; }
  return f;
}
function computeSectorMedians(dailyRows) {
  const by = {};
  for (const r of dailyRows) {
    if (!r.sector) continue;
    (by[r.sector] = by[r.sector] || []).push(r);
  }
  const out = {};
  for (const [sector, rows] of Object.entries(by)) {
    if (rows.length < 4) continue;
    const v = rows.map((r) => num(r.pe)).filter((x) => x !== null && x > 0).sort((a, b) => a - b);
    if (!v.length) continue;
    const m = v.length % 2 ? v[(v.length - 1) / 2] : (v[v.length / 2 - 1] + v[v.length / 2]) / 2;
    out[sector] = m;
  }
  return out;
}
function buildAnalyst(gradeRows, daily, nowMs) {
  const a = {};
  const now = nowMs === undefined ? Date.now() : nowMs;
  const since = now - 30 * DAY;
  let bull = 0, bear = 0;
  for (const g of gradeRows || []) {
    if (!g.grade_date || dayMs(g.grade_date) < since) continue;
    const act = String(g.action || '').toLowerCase();
    if (act === 'upgrade' || act === 'init' || act === 'initiated' || act === 'initialize') bull += 1;
    else if (act === 'downgrade') bear += 1;
  }
  a.analyst_bullish_changes_30d = (gradeRows && gradeRows.length) ? bull : null;
  a.analyst_bearish_changes_30d = (gradeRows && gradeRows.length) ? bear : null;
  const d = daily || {};
  const act = num(d.last_eps_actual), est = num(d.last_eps_estimated);
  a.last_earnings_surprise_pct = act !== null && est !== null && est !== 0 ? ((act - est) / Math.abs(est)) * 100 : null;
  let net = 0, events = 0;
  for (const g of gradeRows || []) {
    if (!g.grade_date) continue;
    const age = (now - dayMs(g.grade_date)) / DAY;
    if (age < 0 || age > 90) continue;
    const act2 = String(g.action || '').toLowerCase();
    const w = 1 - age / 90;
    if (act2 === 'upgrade' || act2 === 'init' || act2 === 'initiated' || act2 === 'initialize') { net += w; events += 1; }
    else if (act2 === 'downgrade') { net -= w; events += 1; }
  }
  a.grade_net_weighted = (gradeRows && gradeRows.length) ? net : null;
  a.grade_events_90d = events;
  const c1 = num(d.pt_count_1m), c3 = num(d.pt_count_3m), p1 = num(d.pt_avg_1m), p3 = num(d.pt_avg_3m);
  let tc = null;
  if (c1 !== null && c3 !== null && p1 > 0 && p3 > 0 && c1 >= 2 && c3 - c1 >= 2) {
    const prior = (c3 * p3 - c1 * p1) / (c3 - c1);
    if (prior > 0) tc = p1 / prior - 1;
  }
  a.target_change = tc;
  a.last_earnings_date = d.last_earnings_date || null;
  a.next_earnings_date = d.next_earnings_date || null;
  return a;
}
module.exports = { prepareQuarters, ttm, growth, buildFundamentals, computeSectorMedians, buildAnalyst };
return module.exports; })();
const SECTOR_ETFS = { 'Communication Services': 'XLC', 'Consumer Cyclical': 'XLY', 'Consumer Defensive': 'XLP', 'Energy': 'XLE', 'Financial Services': 'XLF', 'Healthcare': 'XLV', 'Industrials': 'XLI', 'Basic Materials': 'XLB', 'Real Estate': 'XLRE', 'Technology': 'XLK', 'Utilities': 'XLU' };
const OPTS = { analystV2: true, minStopAtr: 1.0, financialsNoFcf: true };
const MODEL_VERSION = '5.1-fmp-ttm';
const ALERT_THRESHOLD = 80, WATCH_THRESHOLD = 65, MIN_PRICE = 5, MIN_AVG_DOLLAR_VOLUME = 5000000;
const EXCLUDED = new Set(['FLNC']);
const ctx = $('Quotes samenvoegen').first().json;
const nowMs = ctx.nowMs;
const quotes = ctx.quotes || {};
const generatedAt = new Date(nowMs).toISOString();
const nyFmt = new Intl.DateTimeFormat('en-CA', { timeZone: 'America/New_York', year: 'numeric', month: '2-digit', day: '2-digit' });
const nyTimeFmt = new Intl.DateTimeFormat('en-GB', { timeZone: 'America/New_York', hour: '2-digit', minute: '2-digit', hour12: false });
const nyDate = (ms) => nyFmt.format(new Date(ms));
const nyMinutesSinceOpen = (ms) => { const [h, m] = nyTimeFmt.format(new Date(ms)).split(':').map(Number); return h * 60 + m - 570; };
const CURVE = [[0, 0], [30, 0.12], [90, 0.27], [150, 0.38], [210, 0.48], [270, 0.58], [330, 0.71], [360, 0.80], [390, 1.0]];
function volFraction(min) {
  if (min <= 0) return 0;
  if (min >= 390) return 1;
  for (let i = 1; i < CURVE.length; i++) {
    if (min <= CURVE[i][0]) { const [x0, y0] = CURVE[i - 1], [x1, y1] = CURVE[i]; return y0 + (y1 - y0) * (min - x0) / (x1 - x0); }
  }
  return 1;
}
function patchBars(bars, lastDate, q) {
  if (!q || !(q.price > 0) || !q.ts) return { skip: 'geen live koers' };
  const n = bars.c.length;
  const qDate = nyDate(q.ts * 1000);
  if (qDate < lastDate) return { skip: 'live koers ouder dan historie' };
  const replace = qDate === lastDate;
  const baseClose = Number(replace ? bars.c[n - 2] : bars.c[n - 1]);
  if (q.prevClose > 0 && Math.abs(q.prevClose / baseClose - 1) > 0.005) return { skip: 'live koers past niet bij historie (split of dividend?)' };
  const frac = volFraction(nyMinutesSinceOpen(q.ts * 1000));
  const prevVol = Number(replace ? bars.v[n - 2] : bars.v[n - 1]);
  let vol = frac >= 0.12 && q.volume > 0 ? q.volume / frac : prevVol;
  if (q.volume > 0 && vol < q.volume) vol = q.volume;
  const open = q.open > 0 ? q.open : q.price;
  const high = Math.max(q.high > 0 ? q.high : q.price, q.price, open);
  const low = Math.min(q.low > 0 ? q.low : q.price, q.price, open);
  const out = {};
  for (const k of ['d', 'o', 'h', 'l', 'c', 'v']) out[k] = bars[k].slice(0, replace ? n - 1 : n);
  out.d.push(qDate); out.o.push(open); out.h.push(high); out.l.push(low); out.c.push(q.price); out.v.push(vol);
  return { bars: out, date: qDate };
}
function newSignal(overall, gate, rr) {
  if (overall === null || overall === undefined || !Number.isFinite(overall)) return 'DATA_INCOMPLETE';
  if (gate) return overall < WATCH_THRESHOLD ? 'NO_SIGNAL' : 'WATCH';
  const rrBlocked = rr !== null && rr !== undefined && rr < 2.0;
  if (overall >= ALERT_THRESHOLD) return rrBlocked ? 'WATCH' : 'ALERT';
  if (overall >= WATCH_THRESHOLD) return 'WATCH';
  return 'NO_SIGNAL';
}
const rows = $input.all().map((i) => i.json);
const quarterly = {}, grades = {}, daily = {}, cache = {}, names = {}, todayRuns = {};
const todayNY = nyDate(nowMs);
for (const r of rows) {
  if (r.bars) cache[r.symbol] = r;
  else if (r.period_end) (quarterly[r.ticker] = quarterly[r.ticker] || []).push(r);
  else if (r.grade_date) (grades[r.ticker] = grades[r.ticker] || []).push(r);
  else if (r.as_of) { if (!daily[r.ticker] || r.as_of > daily[r.ticker].as_of) daily[r.ticker] = r; }
  else if (r.company_name && r.ticker && !r.scan_generated_at) names[r.ticker] = r.company_name;
  else if (r.scan_generated_at && r.ticker) { if (nyDate(Date.parse(r.scan_generated_at)) === todayNY) (todayRuns[r.ticker] = todayRuns[r.ticker] || []).push({ date: r.scan_generated_at, close: Number(r.price) }); }
}
const dailyRows = Object.values(daily);
const sectorMedians = F.computeSectorMedians(dailyRows);
const patched = {};
function getPatched(sym) {
  if (patched[sym] !== undefined) return patched[sym];
  const c = cache[sym];
  if (!c || !c.bars) return (patched[sym] = null);
  const p = patchBars(c.bars, c.last_date, quotes[sym]);
  return (patched[sym] = p.bars ? p : null);
}
const spyP = getPatched('SPY');
if (!spyP) throw new Error('SPY-koers ontbreekt: kan marktregime niet bepalen');
const bear = M.bearRegime(spyP.bars.c);
const spyForRs = { d: spyP.bars.d, c: spyP.bars.c };
const results = [], payloadRows = [], logRows = [], excluded = [], skippedList = [];
for (const t of Object.keys(daily)) {
  if (EXCLUDED.has(t)) continue;
  const c = cache[t];
  if (!c || c.n_bars < 250) { skippedList.push(t + ': te weinig koershistorie' + (c ? ' (' + c.n_bars + ')' : '')); continue; }
  const p = getPatched(t);
  if (!p) {
    const why = patchBars(c.bars, c.last_date, quotes[t]).skip || 'geen live koers';
    skippedList.push(t + ': ' + why);
    continue;
  }
  const bars = p.bars;
  const n = bars.c.length;
  const price = bars.c[n - 1];
  const avgDollarVol = bars.c.slice(-20).reduce((a, x, i) => a + x * bars.v[n - 20 + i], 0) / 20;
  if (price < MIN_PRICE || avgDollarVol < MIN_AVG_DOLLAR_VOLUME) { excluded.push(t); continue; }
  const ind = M.lastIndicators(bars);
  const extra = M.extraIndicators(bars, spyForRs);
  const etf = SECTOR_ETFS[daily[t].sector];
  const etfP = etf ? getPatched(etf) : null;
  ind.sector_relative_strength_20d = etfP ? M.sectorRelativeStrength(bars.c, etfP.bars.c) : null;
  const fund = F.buildFundamentals(quarterly[t], daily[t], price, sectorMedians, undefined, OPTS);
  const an = F.buildAnalyst(grades[t], daily[t], nowMs);
  const s = M.assembleNewScore(ind, fund, an, bear, nowMs, OPTS);
  const overall = s.overall_score_v2;
  const signal = newSignal(overall, s.gate_excluded, s.risk_reward);
  const company = names[t] || t;
  results.push({ ticker: t, price, last_bar: p.date, sector: daily[t].sector, signal, ...s, ind, fund, an });
  const indOut = { ...ind }; delete indOut.Close;
  const hist = bars.d.slice(-140).map((d, i) => ({ date: d, close: bars.c[n - Math.min(140, n) + i] }));
  const today = (todayRuns[t] || []).sort((a, b) => (a.date < b.date ? -1 : 1));
  today.push({ date: generatedAt, close: price });
  payloadRows.push({
    ticker: t, company_name: company, price,
    avg_dollar_volume_20d: avgDollarVol,
    technical_score: s.technical_score_v2, fundamental_score: s.fundamentals_score_v2,
    overall_score: overall, signal,
    sector: daily[t].sector, bear_regime: bear,
    ...indOut, ...extra,
    revenue_growth: fund.revenue_growth ?? null, eps_growth: fund.eps_growth ?? null, net_margin: fund.net_margin ?? null,
    gross_margin: fund.gross_margin ?? null, fcf: fund.fcf ?? null, fcf_margin: fund.fcf_margin ?? null, roe: fund.roe ?? null,
    debt_equity: fund.debt_equity ?? null, pe: fund.pe ?? null, peg: fund.peg ?? null, forward_pe: fund.forward_pe ?? null,
    ev_sales: fund.ev_sales ?? null, pe_vs_sector: fund.pe_vs_sector ?? null, eps: fund.eps ?? null,
    last_earnings_date: an.last_earnings_date, last_earnings_surprise_pct: an.last_earnings_surprise_pct, next_earnings_date: an.next_earnings_date,
    analyst_bullish_changes_30d: an.analyst_bullish_changes_30d, analyst_bearish_changes_30d: an.analyst_bearish_changes_30d,
    ...s,
    model_version: MODEL_VERSION,
    alert_summary: null, recent_news: [], history_6m: hist, history_today: today, history_1w: [],
  });
  logRows.push({
    scan_generated_at: generatedAt, ticker: t, model_version: MODEL_VERSION, company_name: company, price,
    overall_score: overall, technical_score: s.technical_score_v2, fundamentals_score: s.fundamentals_score_v2,
    valuation_score: s.valuation_score_v2, analyst_score: s.analyst_direction_score, confidence: s.confidence,
    risk_reward: s.risk_reward, gate_excluded: s.gate_excluded, signal,
    rsi_14: ind.rsi_14, return_5d: ind.return_5d, return_20d: ind.return_20d,
    distance_52w_high: ind.distance_52w_high, distance_sma50: extra.distance_sma50, volume_ratio: ind.volume_ratio,
  });
}
const universe = Object.keys(daily).filter((t) => !EXCLUDED.has(t)).length;
const coverage = universe ? (results.length + excluded.length) / universe : 0;
if (coverage < 0.9 && (ctx.write_latest || ctx.write_log)) {
  throw new Error('Te weinig koersen/data: ' + Math.round(coverage * 100) + '% van het universum gescoord. Niets weggeschreven.');
}
payloadRows.sort((a, b) => (b.overall_score - a.overall_score) || ((b.confidence || 0) - (a.confidence || 0)));
const alertRows = payloadRows.filter((r) => r.signal === 'ALERT');
const payload = JSON.parse(JSON.stringify({
  generated_at: generatedAt, universe_size: universe, alert_count: alertRows.length,
  top_score: payloadRows.length ? payloadRows[0].overall_score : null,
  model_version: MODEL_VERSION, score_weights: { technical: 55, fundamentals: 30, valuation: 10, analyst: 5 },
  alert_threshold: ALERT_THRESHOLD, watch_threshold: WATCH_THRESHOLD,
  results: payloadRows,
}));
const alertCandidates = alertRows.map((r) => ({
  ticker: r.ticker, company_name: r.company_name, alert_timestamp: generatedAt, entry_timestamp: generatedAt,
  alert_price: r.price, score: r.overall_score, initial_score: r.overall_score, peak_score: r.overall_score, peak_score_at: generatedAt,
  technical_score: r.technical_score_v2, fundamental_score: r.fundamentals_score_v2, model_version: MODEL_VERSION, status: 'PENDING',
  confidence: r.confidence, risk_reward: r.risk_reward, stop_level: r.stop_level, target_level: r.target_level,
  technical_score_v2: r.technical_score_v2, fundamentals_score_v2: r.fundamentals_score_v2, valuation_score_v2: r.valuation_score_v2,
  analyst_direction_score: r.analyst_direction_score,
}));
return [{ json: {
  model_version: MODEL_VERSION, bear, sectorMedians, aantal: results.length, generated_at: generatedAt,
  trigger: ctx.trigger, write_latest: ctx.write_latest, write_log: ctx.write_log, market_open: ctx.open,
  coverage, uitgesloten_liquiditeit: excluded, overgeslagen: skippedList,
  payload, logRows: JSON.parse(JSON.stringify(logRows)), alertCandidates: JSON.parse(JSON.stringify(alertCandidates)),
  results,
} }];