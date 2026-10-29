// Zet een signaal als nieuwe positie (of bijkoop) in het portfolio van deze browser. Zelfde opslag als de portfolio-pagina.
const KEY = 'marketintel_portfolio';
const read = () => { try { return JSON.parse(localStorage.getItem(KEY) || '[]'); } catch { return []; } };

export function entrySnapshot(r) {
  const c = r?.dip_context || {};
  return { revenue_growth: c.revenue_growth ?? r?.revenue_growth ?? null, fcf_margin: c.fcf_margin ?? null, pt_upside: c.pt_upside ?? null, consensus: c.grades_consensus ?? null, sector: r?.sector || null, at: new Date().toISOString() };
}

export function addPosition(r, qty, price) {
  const now = new Date().toISOString();
  const rows = read().map((x) => (Array.isArray(x.events) && x.events.length ? x : { ...x, events: Number(x.quantity) > 0 && Number(x.entryPrice) > 0 ? [{ type: 'buy', qty: Number(x.quantity), price: Number(x.entryPrice), date: x.addedAt || now }] : [] }));
  const existing = rows.find((x) => x.ticker === r.ticker);
  if (existing) { existing.events.push({ type: 'add', qty, price, date: now }); existing.updatedAt = now; }
  else rows.push({ ticker: r.ticker, company: r.company_name || r.ticker, plan: '6.2', entryFacts: entrySnapshot(r), events: [{ type: 'buy', qty, price, date: now }], addedAt: now, updatedAt: now });
  localStorage.setItem(KEY, JSON.stringify(rows));
  window.dispatchEvent(new Event('marketintel-portfolio-change'));
}
