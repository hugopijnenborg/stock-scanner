// Meldingen bij de posities van de gebruiker. Puur rekenwerk op basis van positionEngine: geen eigen regels.
// Een melding blijft staan zolang het niveau bereikt is. Zodra de gebruiker de stap als "Gedaan" registreert verdwijnt hij vanzelf.
import { evaluate, normalize } from './positionEngine';

const money = (v) => (v == null || !Number.isFinite(Number(v)) ? '—' : `$${Number(v).toLocaleString('en-US', { maximumFractionDigits: 0 })}`);
const price2 = (v) => (v == null || !Number.isFinite(Number(v)) ? '—' : `$${Number(v).toFixed(2)}`);
const qtyTxt = (v) => (v == null || !Number.isFinite(Number(v)) ? '—' : Number(v).toLocaleString('nl-NL', { maximumFractionDigits: 2 }));

export const LEVEL_ORDER = { action: 0, review: 1, info: 2 };
export const KIND_LABEL = { TP: 'WINSTNIVEAU', ADD: 'BIJKOOPNIVEAU', REBUY: 'TERUGKOOPNIVEAU', REVIEW: 'BEOORDELEN', EARN: 'CIJFERS' };

export function buildNotifications(positions, marketMap, now = Date.now()) {
  const out = [];
  for (const raw of positions || []) {
    const p = normalize(raw);
    const r = marketMap?.[p.ticker];
    if (!r) continue;
    const ev = evaluate(p, r, now);
    if (ev.signal === 'CLOSED') continue;
    const st = ev.state;
    const base = { ticker: p.ticker, company: p.company || r.company_name || '', price: ev.price };
    if (ev.signal === 'TP' || ev.signal === 'ADD' || ev.signal === 'REBUY') {
      const idx = ev.signal === 'TP' ? st.tierIdx : ev.signal === 'ADD' ? st.units : st.ntp;
      out.push({
        ...base, key: `${p.ticker}|${ev.signal}|${idx}`, kind: ev.signal, level: 'action',
        title: ev.title, text: ev.reason,
        detail: `Circa ${qtyTxt(ev.qty)} stuks · ongeveer ${money(ev.amount)} · koers nu ${price2(ev.price)}`,
      });
    } else if (ev.signal === 'REVIEW') {
      const facts = ev.notes.filter((n) => n.tone === 'warn' && !/^Cijfers /.test(n.text) && !/^Analisten:/.test(n.text)).map((n) => n.text);
      out.push({
        ...base, key: `${p.ticker}|REVIEW|${facts.join('~').length}`, kind: 'REVIEW', level: 'review',
        title: 'Opnieuw beoordelen', text: facts.slice(0, 3).join(' ') || ev.reason,
        detail: 'Geen verkoopopdracht en niet historisch getest: een moment om opnieuw te kijken.',
      });
    }
    const earn = ev.notes.find((n) => /^Cijfers /.test(n.text));
    if (earn) out.push({ ...base, key: `${p.ticker}|EARN|${String(r.next_earnings_date || '').slice(0, 10)}`, kind: 'EARN', level: 'info', title: 'Cijfers komen eraan', text: earn.text, detail: '' });
  }
  return out.sort((a, b) => (LEVEL_ORDER[a.level] - LEVEL_ORDER[b.level]) || a.ticker.localeCompare(b.ticker));
}
