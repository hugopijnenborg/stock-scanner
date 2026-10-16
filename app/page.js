'use client';

import { useEffect, useMemo, useState } from 'react';
import { ChevronRight, RefreshCw, X } from 'lucide-react';
import AppNav from './components/AppNav';
import { PLANS, ADD_DROP, REBUY_DROP } from './portfolio/positionEngine';
import './ds.css';

const PLAN = PLANS['6.2'];
const PORTFOLIO_KEY = 'marketintel_portfolio';

// ---------- Opmaak ----------
const isNum = (v) => v != null && Number.isFinite(Number(v));
const nl = new Intl.NumberFormat('nl-NL', { maximumFractionDigits: 1 });
function pct(v, digits = 0) {
  if (!isNum(v)) return '—';
  return `${(Number(v) * 100).toLocaleString('nl-NL', { maximumFractionDigits: digits, minimumFractionDigits: digits })}%`;
}
function signed(v, digits = 1) {
  if (!isNum(v)) return '—';
  const n = Number(v) * 100;
  const s = Math.abs(n).toLocaleString('nl-NL', { maximumFractionDigits: digits, minimumFractionDigits: digits });
  return `${n < 0 ? '−' : '+'}${s}%`;
}
function money(v) {
  if (!isNum(v) || Number(v) <= 0) return '—';
  const n = Number(v);
  return `$${n.toLocaleString('nl-NL', { maximumFractionDigits: n < 100 ? 2 : 0, minimumFractionDigits: n < 100 ? 2 : 0 })}`;
}
function timeOf(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleTimeString('nl-NL', { hour: '2-digit', minute: '2-digit' });
}
function dateOf(iso) {
  if (!iso) return '—';
  const d = new Date(String(iso).slice(0, 10) + 'T00:00:00');
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleDateString('nl-NL', { day: 'numeric', month: 'long' });
}

// ---------- Inhoud per signaal ----------
// Waarschuwingen zijn feitelijk en geen filter: het signaal blijft staan.
function warningsOf(r) {
  const c = r.dip_context || {};
  const out = [];
  const d = c.earnings_in_days;
  if (isNum(d) && d >= -1 && d <= 7) {
    out.push({
      short: d <= 0 ? 'Cijfers vandaag' : d === 1 ? 'Cijfers morgen' : `Cijfers over ${d} dagen`,
      title: 'Kwartaalcijfers komen eraan',
      text: 'Rond cijfers bewegen koersen vaak extra sterk, omhoog én omlaag.',
    });
  }
  if (c.stock_specific) {
    out.push({
      short: 'Zwakker dan de markt',
      title: 'Zwakker dan de markt',
      text: `Het aandeel deed de afgelopen 30 dagen ${pct(Math.abs(c.rel30), 0)} slechter dan de S&P 500, terwijl de markt zelf niet in een dip zit. In de historische test deden zulke dips het wat zwakker.`,
    });
  }
  if (c.post_earnings) {
    out.push({
      short: `Cijfers ${c.days_since_earnings} dagen geleden`,
      title: 'Net na kwartaalcijfers',
      text: 'De cijfers kwamen maximaal 10 dagen geleden. In de historische test deden dips vlak na cijfers het wat zwakker.',
    });
  }
  if (r.dip_speculative) {
    out.push({
      short: 'Negatieve kasstroom',
      title: 'Negatieve vrije kasstroom',
      text: 'Het bedrijf geeft meer uit dan het binnenhaalt. In de historische test gaf dat gemiddeld diepere dalingen.',
    });
  }
  return out;
}

function nearMissReason(r) {
  if (r.dip_qualifies) {
    if (r.dip_excluded === 'groei') return 'Voldoet aan de dip-regels, maar omzetgroei is onder 10%';
    if (r.dip_excluded === 'sector') return 'Voldoet aan de dip-regels, maar valt in een uitgesloten sector';
    return 'Voldoet aan de regels, maar staat buiten de top 5';
  }
  const parts = [];
  if (isNum(r.d52) && r.d52 > -0.15) parts.push(`52 weken: ${signed(r.d52, 0)} (nodig −15%)`);
  if (isNum(r.dd30) && r.dd30 > -0.08) parts.push(`30 dagen: ${signed(r.dd30, 0)} (nodig −8%)`);
  if (isNum(r.dip) && r.dip > 0.3) parts.push('dip nog niet diep genoeg');
  return parts.join(' · ') || '—';
}

function sparkOf(r) {
  if (Array.isArray(r.spark)) return r.spark;
  const h = Array.isArray(r.history_6m) ? r.history_6m : [];
  return h.filter((_, i) => i % 6 === 5).map((x) => x.close);
}

// ---------- Kleine onderdelen ----------
function Spark({ data }) {
  if (!Array.isArray(data) || data.length < 3) return null;
  const w = 110, h = 34, min = Math.min(...data), max = Math.max(...data), span = max - min || 1;
  const pts = data.map((v, i) => `${((i / (data.length - 1)) * w).toFixed(1)},${(h - 3 - ((v - min) / span) * (h - 6)).toFixed(1)}`);
  const last = pts[pts.length - 1].split(',');
  return (
    <svg className="ds-spark" width={w} height={h} viewBox={`0 0 ${w} ${h}`} aria-hidden="true">
      <polyline points={pts.join(' ')} fill="none" stroke="#64748b" strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={last[0]} cy={last[1]} r="2.4" fill="#2457d6" />
    </svg>
  );
}

function AddToPortfolio({ r }) {
  const [open, setOpen] = useState(false);
  const [qty, setQty] = useState('1');
  const [price, setPrice] = useState(isNum(r.price) ? Number(r.price).toFixed(2) : '');
  function save() {
    const q = Number(qty), p = Number(price);
    if (!(q > 0 && p > 0)) return;
    let rows = [];
    try { rows = JSON.parse(localStorage.getItem(PORTFOLIO_KEY) || '[]'); } catch { rows = []; }
    const now = new Date().toISOString();
    const existing = rows.find((x) => x.ticker === r.ticker);
    if (existing) {
      if (!Array.isArray(existing.events)) existing.events = [];
      existing.events.push({ type: 'add', qty: q, price: p, date: now });
      existing.updatedAt = now;
    } else {
      rows.push({ ticker: r.ticker, company: r.company_name || r.ticker, plan: '6.2', events: [{ type: 'buy', qty: q, price: p, date: now }], addedAt: now, updatedAt: now });
    }
    try { localStorage.setItem(PORTFOLIO_KEY, JSON.stringify(rows)); } catch { return; }
    window.dispatchEvent(new Event('marketintel-portfolio-change'));
    window.location.href = '/portfolio';
  }
  if (!open) return <button className="ds-btn primary" onClick={() => setOpen(true)}>Toevoegen aan portfolio</button>;
  return (
    <div className="ds-form">
      <label>Aantal<input type="number" min="0" step="any" value={qty} onChange={(e) => setQty(e.target.value)} /></label>
      <label>Aankoopprijs ($)<input type="number" min="0" step="0.01" value={price} onChange={(e) => setPrice(e.target.value)} /></label>
      <div className="full">
        <button className="ds-btn primary" onClick={save}>Opslaan</button>
        <button className="ds-btn" onClick={() => setOpen(false)}>Annuleren</button>
      </div>
    </div>
  );
}

function Detail({ r, onClose }) {
  const c = r.dip_context || {};
  const warns = warningsOf(r);
  const p = Number(r.price);
  return (
    <>
      <div className="ds-scrim" onClick={onClose} />
      <aside className="ds-drawer" role="dialog" aria-label={`${r.ticker} details`}>
        <div className="ds-drawerHead">
          <div>
            <h2>{r.ticker} <span className="ds-company" style={{ fontWeight: 400, fontSize: 15 }}>{r.company_name}</span></h2>
            <div className="ds-drawerPrice"><b className="num">{money(p)}</b> · {r.sector || c.sector || 'Sector onbekend'}</div>
          </div>
          <button className="ds-x" onClick={onClose} aria-label="Sluiten"><X size={18} /></button>
        </div>

        <div className="ds-drawerBody">
          {warns.length > 0 && (
            <div className="ds-block">
              <h3>Let op</h3>
              {warns.map((w) => <div className="ds-warn" key={w.title}><b>{w.title}</b>{w.text}</div>)}
            </div>
          )}

          <div className="ds-block">
            <h3>Waarom dit signaal</h3>
            <ul className="ds-list num">
              <li><span>Onder de 52-weekshoogte</span><b>{pct(Math.abs(r.d52), 0)}</b></li>
              <li><span>Onder de hoogste koers van 30 dagen</span><b>{pct(Math.abs(r.dd30), 0)}</b></li>
              <li><span>RSI (onder 30 = sterk uitverkocht)</span><b>{isNum(c.rsi) ? nl.format(c.rsi) : '—'}</b></li>
              <li><span>Omzetgroei (minimaal 10%)</span><b>{pct(c.revenue_growth, 0)}</b></li>
            </ul>
          </div>

          <div className="ds-block">
            <h3>Positieplan van het model</h3>
            <table className="ds-plan num"><tbody>
              {PLAN.tiers.map((t) => (
                <tr key={t}><td>Winst nemen bij {signed(t, 0)}</td><td>{money(p * (1 + t))} · {PLAN.sell * 100}% verkopen</td></tr>
              ))}
              <tr><td>Bijkopen onder (max. 2 keer)</td><td>{money(p * (1 - ADD_DROP))}</td></tr>
              <tr><td>Terugkopen</td><td>{REBUY_DROP * 100}% onder je laatste verkoop</td></tr>
            </tbody></table>
            <p className="ds-small">Prijzen gelden als je nu instapt. Er is geen stop: het model houdt altijd een restpositie.</p>
          </div>

          <div className="ds-block">
            <details className="ds-details">
              <summary>Bedrijfsgegevens</summary>
              <ul className="ds-list num">
                <li><span>Brutomarge</span><b>{pct(c.gross_margin, 0)}</b></li>
                <li><span>Vrije kasstroom (marge)</span><b>{pct(c.fcf_margin, 0)}</b></li>
                <li><span>Analisten</span><b>{c.grades_consensus || '—'}</b></li>
                <li><span>Gemiddeld koersdoel analisten</span><b>{isNum(c.pt_upside) ? signed(c.pt_upside, 0) : '—'}</b></li>
                <li><span>Volgende kwartaalcijfers</span><b>{c.next_earnings ? dateOf(c.next_earnings) : '—'}</b></li>
              </ul>
              <p className="ds-small">Analistendata is context en geen onderdeel van de regels.</p>
            </details>
          </div>
        </div>

        <div className="ds-drawerFoot">
          <AddToPortfolio r={r} />
          <p className="ds-small" style={{ marginBottom: 0 }}>Gebaseerd op een historische simulatie. Geen financieel advies en geen garantie.</p>
        </div>
      </aside>
    </>
  );
}

// ---------- Pagina ----------
export default function Home() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selected, setSelected] = useState(null);
  const [query, setQuery] = useState('');
  const [showAll, setShowAll] = useState(false);
  const [scanMsg, setScanMsg] = useState('');

  async function load() {
    setLoading(true); setError('');
    try {
      const res = await fetch('/api/scan?ts=' + Date.now(), { cache: 'no-store' });
      const body = await res.json();
      if (!res.ok) throw Error(body.error || 'De laatste scan is niet beschikbaar.');
      setData(body);
    } catch (e) { setError(e.message); } finally { setLoading(false); }
  }
  async function startScan() {
    if (loading) return;
    const previous = data?.generated_at || '';
    setLoading(true); setScanMsg('Scan wordt gestart…');
    try {
      const t = await fetch('/api/trigger-scan', { method: 'POST' });
      const tb = await t.json().catch(() => ({}));
      if (!t.ok) throw Error(tb.error || 'De scan kon niet worden gestart.');
      const started = Date.now();
      while (Date.now() - started < 10 * 60 * 1000) {
        await new Promise((r) => setTimeout(r, 10000));
        const res = await fetch('/api/scan?ts=' + Date.now(), { cache: 'no-store' });
        if (!res.ok) continue;
        const body = await res.json();
        if (body?.generated_at && body.generated_at !== previous) { setData(body); setScanMsg(''); return; }
      }
      throw Error('De scan duurt langer dan verwacht.');
    } catch (e) { setError(e.message); setScanMsg(''); } finally { setLoading(false); }
  }
  useEffect(() => { load(); }, []);
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') setSelected(null); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  const all = data?.results || [];
  const breadth = data?.dip_breadth;
  const signals = useMemo(
    () => all.filter((r) => r.signal === 'ALERT').sort((a, b) => Number(a.dip_rank ?? 99) - Number(b.dip_rank ?? 99)),
    [all],
  );
  const nearMiss = useMemo(
    () => all.filter((r) => r.signal === 'WATCH').sort((a, b) => Number(a.dip_short ?? 9) - Number(b.dip_short ?? 9)).slice(0, 8),
    [all],
  );
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return all
      .filter((r) => !q || `${r.ticker} ${r.company_name || ''}`.toLowerCase().includes(q))
      .sort((a, b) => String(a.ticker).localeCompare(String(b.ticker)));
  }, [all, query]);
  const visible = showAll || query ? filtered : filtered.slice(0, 12);
  const statusOf = (r) => (r.signal === 'ALERT' ? 'Signaal' : r.signal === 'WATCH' ? 'Bijna' : '');

  return (
    <div className="ds">
      <AppNav active="/" modelVersion="6.2" />
      <main className="ds-main">
        <header className="ds-head">
          <div>
            <h1>Signalen</h1>
            <p className="ds-sub">
              Aandelen die diep gedaald zijn en voldoen aan de regels van het model. Laatste scan om {timeOf(data?.generated_at)}, tijdens beurstijd elk kwartier.
            </p>
          </div>
          <div className="ds-actions">
            <button className="ds-btn primary" onClick={startScan} disabled={loading}>
              <RefreshCw size={15} /> {scanMsg || (loading ? 'Laden…' : 'Nu scannen')}
            </button>
          </div>
        </header>

        {error && <div className="ds-error">{error}</div>}

        {loading && !data ? (
          <><div className="ds-skel" /><div className="ds-skel" /><div className="ds-skel" /></>
        ) : (
          <>
            <div className="ds-summary">
              <div className="ds-stat"><span>Signalen nu</span><strong className="num">{signals.length}</strong></div>
              <div className="ds-stat"><span>Voldoen aan de dip-regels</span><strong className="num">{breadth?.count ?? '—'}</strong></div>
              <div className="ds-stat"><span>Gescande aandelen</span><strong className="num">{breadth?.evaluated ?? data?.universe_size ?? '—'}</strong></div>
            </div>
            {breadth?.market_wide && (
              <p className="ds-note">
                Veel aandelen zitten tegelijk in een dip ({pct(breadth.pct, 0)} van de lijst). Signalen komen dan vaak in clusters en zijn vaak uit dezelfde sector. Het model toont maximaal {breadth.top_n || 5} signalen.
              </p>
            )}

            <section className="ds-section">
              <div className="ds-sectionHead">
                <h2>Actieve signalen</h2>
                <p>Gerangschikt van diepste dip naar minder diep</p>
              </div>
              <div className="ds-card">
                {signals.length === 0 ? (
                  <div className="ds-empty">Er is nu geen signaal. Zodra een aandeel aan de regels voldoet, verschijnt het hier.</div>
                ) : (
                  <table className="ds-table">
                    <thead>
                      <tr>
                        <th>Aandeel</th>
                        <th className="r">Koers</th>
                        <th className="r">Onder 52-weekshoogte</th>
                        <th className="ds-hide-sm">6 maanden</th>
                        <th>Let op</th>
                        <th />
                      </tr>
                    </thead>
                    <tbody>
                      {signals.map((r) => {
                        const w = warningsOf(r);
                        return (
                          <tr key={r.ticker} className="ds-row" onClick={() => setSelected(r)}>
                            <td><div className="ds-ticker">{r.ticker}</div><div className="ds-company">{r.company_name}</div></td>
                            <td className="r num">{money(r.price)}</td>
                            <td className="r num"><span className="ds-drop ds-neg">{signed(r.d52, 0)}</span></td>
                            <td className="ds-hide-sm"><Spark data={sparkOf(r)} /></td>
                            <td>
                              {w.length === 0 ? <span className="ds-mut">—</span> : (
                                <div className="ds-chips">{w.map((x) => <span className="ds-chip" key={x.short}>{x.short}</span>)}</div>
                              )}
                            </td>
                            <td className="r"><ChevronRight size={16} color="#8a94a3" /></td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                )}
              </div>
            </section>

            {nearMiss.length > 0 && (
              <section className="ds-section">
                <div className="ds-sectionHead">
                  <h2>Bijna een signaal</h2>
                  <p>Deze aandelen voldoen nog niet aan alle regels</p>
                </div>
                <div className="ds-card">
                  <table className="ds-table">
                    <thead><tr><th>Aandeel</th><th className="r">Koers</th><th>Wat ontbreekt</th></tr></thead>
                    <tbody>
                      {nearMiss.map((r) => (
                        <tr key={r.ticker}>
                          <td><span className="ds-ticker">{r.ticker}</span> <span className="ds-company">{r.company_name}</span></td>
                          <td className="r num">{money(r.price)}</td>
                          <td className="ds-mut">{nearMissReason(r)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            )}

            <section className="ds-section">
              <div className="ds-sectionHead">
                <h2>Alle aandelen</h2>
                <input className="ds-search" placeholder="Zoek op naam of ticker" value={query} onChange={(e) => setQuery(e.target.value)} />
              </div>
              <div className="ds-card">
                <table className="ds-table">
                  <thead><tr><th>Aandeel</th><th className="r">Koers</th><th className="r">Vandaag</th><th>Status</th></tr></thead>
                  <tbody>
                    {visible.map((r) => (
                      <tr key={r.ticker}>
                        <td><span className="ds-ticker">{r.ticker}</span> <span className="ds-company">{r.company_name}</span></td>
                        <td className="r num">{money(r.price)}</td>
                        <td className={`r num ${Number(r.return_1d) < 0 ? 'ds-neg' : 'ds-pos'}`}>{signed(r.return_1d, 1)}</td>
                        <td>{statusOf(r) ? <span className={`ds-chip${r.signal === 'ALERT' ? '' : ' plain'}`}>{statusOf(r)}</span> : <span className="ds-mut">—</span>}</td>
                      </tr>
                    ))}
                    {visible.length === 0 && <tr><td colSpan={4} className="ds-empty">Geen aandelen gevonden.</td></tr>}
                  </tbody>
                </table>
                {!showAll && !query && filtered.length > 12 && (
                  <button className="ds-more" onClick={() => setShowAll(true)}>Toon alle {filtered.length} aandelen</button>
                )}
              </div>
            </section>
          </>
        )}
      </main>
      {selected && <Detail r={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}
