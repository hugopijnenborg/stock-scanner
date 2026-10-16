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

// market = rij uit de scan (price, dip, distance_sma20, next_earnings_date, analist-velden)
export function evaluate(position, market, now = Date.now()) {
  const st = deriveState(position);
  const plan = planOf(position);
  const TIERS = plan.tiers, SELL_FRACTION = plan.sell;
  const price = num(market?.price);
  const out = { state: st, price, signal: 'HOLD', title: 'Positie aanhouden', reason: '', qty: null, amount: null, levels: {}, notes: [], pnl: null };
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
  const stretch = num(market?.distance_sma20);

  const daysSinceBuy = st.lastBuy ? (now - Date.parse(st.lastBuy)) / DAY : 999;
  const dipOk = dip === null || dip <= DIP_MAX_FOR_BUY;

  if (nextTier !== null && price >= out.levels.nextTP) {
    out.signal = 'TP'; out.title = `Winst nemen (trap ${st.tierIdx + 1} van ${TIERS.length})`;
    out.qty = st.shares * SELL_FRACTION; out.amount = out.qty * price;
    out.reason = `Koers staat ${Math.round(nextTier * 100)}% of meer boven je gemiddelde koers. Verkoop ${SELL_FRACTION * 100}% van je aandelen en houd de rest voor de upside.`;
    if (stretch !== null && stretch > MOMENTUM_STRETCH) {
      out.notes.push({ tone: 'info', text: `Sterk momentum (${(stretch * 100).toFixed(0)}% boven het 20-daags gemiddelde). Historisch liepen zulke aandelen na een winstniveau gemiddeld verder door (+13 tot +15% in 3 maanden, tegen +4 tot +8% bij zwak momentum), maar met grote uitschieters. Je mag deze verkoop uitstellen.` });
    }
  } else if (out.levels.add && price <= out.levels.add && dipOk && daysSinceBuy >= MIN_DAYS_BETWEEN_BUYS) {
    out.signal = 'ADD'; out.title = `Bijkopen (${st.units} van ${MAX_UNITS} eenheden gebruikt)`;
    out.amount = st.unitCost; out.qty = st.unitCost ? st.unitCost / price : null;
    out.reason = `Koers staat ${Math.round(ADD_DROP * 100)}% of meer onder je gemiddelde koers en het aandeel zit nog in een dip. Eén eenheid is je eerste inleg.`;
    if (out.pnl.openPct !== null && out.pnl.openPct <= DEEP_LOSS) {
      out.notes.push({ tone: 'warn', text: 'Je zit 40% of meer onder je gemiddelde koers. Het model heeft hier geen stop; toets of de reden om te kopen nog klopt voor je bijkoopt.' });
    }
  } else if (out.levels.rebuy && price <= out.levels.rebuy && dipOk) {
    out.signal = 'REBUY'; out.title = 'Terugkopen';
    out.amount = st.pool; out.qty = st.pool / price;
    out.reason = `Koers staat ${Math.round(REBUY_DROP * 100)}% of meer onder je laatste verkoopprijs (${st.lastTP.toFixed(2)}). Koop je winstopbrengst (${st.pool.toFixed(0)}) terug.`;
  } else {
    out.signal = 'HOLD';
    const bits = [];
    if (out.levels.nextTP) bits.push(`volgende winstnemming bij ${out.levels.nextTP.toFixed(2)} (+${Math.round(nextTier * 100)}%)`);
    if (out.levels.add) bits.push(`bijkopen onder ${out.levels.add.toFixed(2)}`);
    if (out.levels.rebuy) bits.push(`terugkopen onder ${out.levels.rebuy.toFixed(2)}`);
    out.title = 'Aanhouden';
    out.reason = bits.length ? `Geen actie nodig: ${bits.join(', ')}.` : 'Geen actie nodig.';
    if (out.levels.add && price <= out.levels.add && !dipOk) out.notes.push({ tone: 'info', text: 'De koers staat onder het bijkoopniveau, maar het aandeel zit niet meer diep in een dip. Het model koopt dan niet bij.' });
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
