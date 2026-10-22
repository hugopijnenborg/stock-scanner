// Positiebeheer volgens het geteste model (zie validatie): winst nemen in trappen, bijkopen, terugkopen,
// altijd een restpositie houden. Alle regels komen uit de historische simulatie (2020-2026).
// Plannen per modelversie. Bestaande posities houden hun plan (zonder plan = 6.1), nieuwe posities krijgen 6.2.
export const PLANS = {
  '6.1': { tiers: [0.10, 0.25, 0.50, 1.00], sell: 0.20 },
  '6.2': { tiers: [0.15, 0.30, 0.60, 1.20], sell: 0.10 },
};
export const CURRENT_PLAN = '6.2';
export const planOf = (position) => PLANS[position?.plan] || PLANS['6.1'];
export const TIERS = PLANS['6.2'].tiers;          // standaard (nieuwe posities)
export const SELL_FRACTION = PLANS['6.2'].sell;
export const ADD_DROP = 0.12;                     // bijkopen: koers >= 12% onder gemiddelde koers
export const REBUY_DROP = 0.12;                   // terugkopen: koers >= 12% onder laatste verkoopprijs
export const MAX_UNITS = 3;                       // eerste aankoop + maximaal 2 keer bijkopen
export const MIN_DAYS_BETWEEN_BUYS = 7;           // ~5 handelsdagen
export const DIP_MAX_FOR_BUY = 0.35;              // bij- en terugkopen alleen als het aandeel nog in een dip zit
export const MOMENTUM_STRETCH = 0.12;             // >12% boven 20d-gemiddelde = sterk momentum
export const DEEP_LOSS = -0.40;

const num = (v) => (v === null || v === undefined || v === '' || !Number.isFinite(Number(v)) ? null : Number(v));
const DAY = 86400000;

// Oude posities (aantal + aankoopprijs) worden omgezet naar een gebeurtenissenlijst.
export function normalize(position) {
  if (Array.isArray(position.events) && position.events.length) return position;
  const qty = num(position.quantity), price = num(position.entryPrice);
  const events = qty > 0 && price > 0
    ? [{ type: 'buy', qty, price, date: position.addedAt || new Date().toISOString() }]
    : [];
  return { ...position, events };
}

export function deriveState(position) {
  const p = normalize(position);
  const plan = planOf(position);
  let shares = 0, cost = 0, ext = 0, cash = 0, pool = 0, lastTP = null, tierIdx = 0, units = 0, lastBuy = null, ntp = 0, nadd = 0, nrebuy = 0, unitCost = null;
  for (const e of [...p.events].sort((a, b) => String(a.date).localeCompare(String(b.date)))) {
    const q = num(e.qty), pr = num(e.price);
    if (!(q > 0) || !(pr > 0)) continue;
    const t = e.type;
    if (t === 'buy' || t === 'add') {
      shares += q; cost += q * pr; ext += q * pr; units += 1; lastBuy = e.date;
      if (t === 'buy' && unitCost === null) unitCost = q * pr;
      if (t === 'add') nadd += 1;
    } else if (t === 'rebuy') {
      shares += q; cost += q * pr; pool = Math.max(0, pool - q * pr); cash -= q * pr; tierIdx = 0; lastBuy = e.date; nrebuy += 1;
    } else if (t === 'tp' || t === 'sell') {
      const sold = Math.min(q, shares);
      if (shares > 0) cost -= (cost / shares) * sold;
      shares -= sold; cash += sold * pr;
      if (t === 'tp') { pool += sold * pr; lastTP = pr; tierIdx = Math.min(plan.tiers.length, tierIdx + 1); ntp += 1; }
    }
  }
  if (shares < 1e-9) { shares = 0; cost = 0; }
  const avg = shares > 0 ? cost / shares : null;
  return { shares, cost, ext, cash, pool, lastTP, tierIdx, units, lastBuy, ntp, nadd, nrebuy, avg, unitCost: unitCost ?? (ext > 0 ? ext / Math.max(1, units) : null) };
}

const pctTxt = (v) => `${(v * 100).toFixed(0)}%`;
const CONS_NL = { 'Strong Buy': 'sterk kopen', Buy: 'kopen', Hold: 'aanhouden', Sell: 'verkopen', 'Strong Sell': 'sterk verkopen' };

// Veranderingen in het bedrijf die de reden van het signaal zwakker maken. Geen vaste koersstop en geen verkoopregel:
// het zijn feiten om opnieuw te beoordelen. Dit is niet historisch getest (kwaliteits- en cijferfilters bleken in de test geen robuuste voorspeller).
// Heeft de positie een momentopname van de feiten bij het signaal (entryFacts), dan telt alleen wat sindsdien is verslechterd.
export function reviewFacts(position, market) {
  const f = [];
  if (!market) return f;
  const e = position?.entryFacts || null;
  const c = market.dip_context || {};

  const g = num(market.revenue_growth ?? c.revenue_growth);
  const g0 = num(e?.revenue_growth);
  if (g !== null && Math.abs(g) < 5 && g < 0.10) f.push(`De omzetgroei is ${pctTxt(g)}${g0 !== null ? ` (bij het signaal ${pctTxt(g0)})` : ''}. Het model vraagt minimaal 10%.`);

  const m = num(c.fcf_margin ?? market.fcf_margin), m0 = num(e?.fcf_margin);
  if (m !== null && Math.abs(m) < 5 && m < 0 && (e ? (m0 !== null && m0 >= 0) : true)) f.push('De vrije kasstroom is negatief geworden.');

  const u = num(c.pt_upside), u0 = num(e?.pt_upside);
  if (u !== null && u < 0 && (e ? (u0 === null || u0 >= 0) : true)) f.push('De koers staat boven het gemiddelde koersdoel van analisten: de upside volgens analisten is weg.');

  const cons = c.grades_consensus;
  if (cons && /sell/i.test(cons) && !(e?.consensus && /sell/i.test(e.consensus))) f.push(`Het analistenconsensus is nu "${CONS_NL[cons] || cons}".`);

  const s = num(market.last_earnings_surprise_pct), led = market.last_earnings_date ? String(market.last_earnings_date).slice(0, 10) : null;
  const added = String(position?.addedAt || position?.events?.[0]?.date || '').slice(0, 10);
  if (s !== null && s < 0 && led && added && led > added) f.push(`De kwartaalcijfers van ${led} kwamen ${Math.abs(s).toFixed(1)}% onder de verwachting.`);

  return f;
}

// market = rij uit de scan (price, dip, distance_sma20, next_earnings_date, analist-velden)
export function evaluate(position, market, now = Date.now()) {
  const st = deriveState(position);
  const plan = planOf(position);
  const TIERS = plan.tiers, SELL_FRACTION = plan.sell;
  const price = num(market?.price);
  const out = { state: st, price, signal: 'HOLD', title: 'Geen niveau bereikt', reason: '', qty: null, amount: null, levels: {}, notes: [], pnl: null };
  if (st.shares <= 0) { out.signal = 'CLOSED'; out.title = 'Positie gesloten'; out.reason = 'Er zijn geen aandelen meer over.'; return out; }
  const nextTier = st.tierIdx < TIERS.length ? TIERS[st.tierIdx] : null;
  out.levels = {
    nextTP: nextTier !== null ? st.avg * (1 + nextTier) : null,
    nextTPpct: nextTier,
    add: st.units < MAX_UNITS ? st.avg * (1 - ADD_DROP) : null,
    rebuy: st.pool > 0 && st.lastTP ? st.lastTP * (1 - REBUY_DROP) : null,
  };
  if (!(price > 0)) { out.reason = 'Geen actuele koers beschikbaar.'; return out; }

  const value = st.shares * price;
  out.pnl = { value, total: st.cash + value - st.ext, totalPct: st.ext > 0 ? (st.cash + value) / st.ext - 1 : null, openPct: st.avg ? price / st.avg - 1 : null };
  const dip = num(market?.dip);

  const daysSinceBuy = st.lastBuy ? (now - Date.parse(st.lastBuy)) / DAY : 999;
  const dipOk = dip === null || dip <= DIP_MAX_FOR_BUY;

  if (nextTier !== null && price >= out.levels.nextTP) {
    out.signal = 'TP'; out.title = `Winstniveau bereikt (trap ${st.tierIdx + 1} van ${TIERS.length})`;
    out.qty = st.shares * SELL_FRACTION; out.amount = out.qty * price;
    out.reason = `De koers staat ${Math.round(nextTier * 100)}% of meer boven je gemiddelde koers. Volgens het plan wordt hier ${Math.round(SELL_FRACTION * 100)}% van de aandelen verkocht en blijft de rest staan.`;
  } else if (out.levels.add && price <= out.levels.add && dipOk && daysSinceBuy >= MIN_DAYS_BETWEEN_BUYS) {
    out.signal = 'ADD'; out.title = `Bijkoopniveau bereikt (${st.units} van ${MAX_UNITS} eenheden gebruikt)`;
    out.amount = st.unitCost; out.qty = st.unitCost ? st.unitCost / price : null;
    out.reason = `De koers staat ${Math.round(ADD_DROP * 100)}% of meer onder je gemiddelde koers en het aandeel zit nog in een dip. Volgens het plan is bijkopen hier één eenheid (je eerste inleg).`;
  } else if (out.levels.rebuy && price <= out.levels.rebuy && dipOk) {
    out.signal = 'REBUY'; out.title = 'Terugkoopniveau bereikt';
    out.amount = st.pool; out.qty = st.pool / price;
    out.reason = `De koers staat ${Math.round(REBUY_DROP * 100)}% of meer onder je laatste verkoopprijs (${st.lastTP.toFixed(2)}). Volgens het plan wordt hier de opbrengst van je winstnemingen (${st.pool.toFixed(0)}) teruggekocht.`;
  } else {
    out.signal = 'HOLD';
    const bits = [];
    if (out.levels.nextTP) bits.push(`volgende winstniveau bij ${out.levels.nextTP.toFixed(2)} (+${Math.round(nextTier * 100)}%)`);
    if (out.levels.add) bits.push(`bijkoopniveau onder ${out.levels.add.toFixed(2)}`);
    if (out.levels.rebuy) bits.push(`terugkoopniveau onder ${out.levels.rebuy.toFixed(2)}`);
    out.reason = bits.length ? `Er is geen niveau bereikt: ${bits.join(', ')}.` : 'Er is geen niveau bereikt.';
    if (out.levels.add && price <= out.levels.add && !dipOk) out.notes.push({ tone: 'info', text: 'De koers staat onder het bijkoopniveau, maar het aandeel zit niet meer diep in een dip. Het plan koopt dan niet bij.' });
  }

  // Veranderingen in het bedrijf sinds het signaal (geen vaste koersstop)
  const facts = reviewFacts(position, market);
  facts.forEach((t) => out.notes.push({ tone: 'warn', text: t }));
  if (facts.length) {
    if (out.signal === 'HOLD') {
      out.signal = 'REVIEW'; out.title = 'Opnieuw beoordelen';
      out.reason = 'Sinds het signaal is er iets veranderd in het bedrijf dat de reden voor dit signaal zwakker maakt (zie hieronder). Het plan heeft geen vaste stop. Dit is een moment om opnieuw te kijken, geen opdracht om te verkopen. Deze controle is niet historisch getest.';
    } else {
      out.notes.push({ tone: 'warn', text: 'Er is iets verslechterd in het bedrijf sinds het signaal (zie hierboven). Weeg dat mee naast het plan. Deze controle is niet historisch getest.' });
    }
  }

  // Context (geen trigger): cijfers en analisten
  const ed = market?.next_earnings_date ? Math.round((Date.parse(String(market.next_earnings_date).slice(0, 10) + 'T00:00:00Z') - now) / DAY) : null;
  if (ed !== null && ed >= -1 && ed <= 7) out.notes.push({ tone: 'warn', text: ed <= 0 ? 'Cijfers vandaag: verwacht grote koersbewegingen.' : `Cijfers over ${ed} dagen: verwacht grotere koersbewegingen.` });
  const up = num(market?.analyst_bullish_changes_30d), down = num(market?.analyst_bearish_changes_30d);
  if (down !== null && up !== null && down >= 2 && down > up) out.notes.push({ tone: 'warn', text: `Analisten: ${down} verlagingen en ${up} verhogingen in 30 dagen. Dit is context en geen verkoopregel.` });
  if (down !== null && up !== null && up >= 2 && up > down) out.notes.push({ tone: 'info', text: `Analisten: ${up} verhogingen en ${down} verlagingen in 30 dagen.` });
  return out;
}

// Voegt een gebeurtenis toe en geeft de nieuwe positie terug.
export function withEvent(position, event) {
  const p = normalize(position);
  return { ...p, events: [...p.events, { ...event, date: event.date || new Date().toISOString() }], updatedAt: new Date().toISOString() };
}
