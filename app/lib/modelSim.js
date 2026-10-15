// Hulpfuncties voor het positiebeheer-resultaat per alert (berekend door n8n in scanner_alerts.model_return / model_sim).
// Simulatie: 100 per signaal, met winst nemen, bijkopen en terugkopen volgens het model.

const fin = (v) => v !== null && v !== undefined && v !== '' && Number.isFinite(Number(v));

// Rendement als je had vastgehouden, gemeten over dezelfde periode als het model-resultaat.
export function holdReturn(row) {
  const sim = row?.model_sim;
  const first = sim?.events?.[0]?.price;
  if (!sim || !fin(sim.last_price) || !fin(first) || Number(first) <= 0) return null;
  return (Number(sim.last_price) / Number(first) - 1) * 100;
}

export function modelReturn(row) {
  return fin(row?.model_return) ? Number(row.model_return) : null;
}

export function eventCounts(row) {
  const ev = row?.model_sim?.events || [];
  return {
    tp: ev.filter((e) => e.type === 'tp').length,
    add: ev.filter((e) => e.type === 'add').length,
    rebuy: ev.filter((e) => e.type === 'rebuy').length,
  };
}

export function simStats(rows) {
  const use = rows.filter((r) => modelReturn(r) !== null && holdReturn(r) !== null);
  const n = use.length;
  const avg = (f) => (n ? use.reduce((s, r) => s + f(r), 0) / n : null);
  const c = use.reduce((a, r) => {
    const e = eventCounts(r);
    return { tp: a.tp + e.tp, add: a.add + e.add, rebuy: a.rebuy + e.rebuy };
  }, { tp: 0, add: 0, rebuy: 0 });
  return {
    n,
    avgModel: avg(modelReturn),
    avgHold: avg(holdReturn),
    winModel: n ? (100 * use.filter((r) => modelReturn(r) > 0).length) / n : null,
    winHold: n ? (100 * use.filter((r) => holdReturn(r) > 0).length) / n : null,
    ...c,
  };
}

const px = (v) => (fin(v) ? Number(v).toFixed(2) : null);

// Korte tekst met de volgende niveaus uit het model (geen opdracht, alleen de niveaus).
export function nextLevels(row) {
  const nx = row?.model_sim?.next;
  if (!nx) return '';
  const bits = [];
  if (px(nx.tp)) bits.push(`winstniveau ${px(nx.tp)}`);
  if (px(nx.add)) bits.push(`bijkoopniveau ${px(nx.add)}`);
  if (px(nx.rebuy)) bits.push(`terugkoopniveau ${px(nx.rebuy)}`);
  return bits.join(' · ');
}
