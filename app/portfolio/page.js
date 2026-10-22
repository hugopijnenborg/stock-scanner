'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import {
  Activity,
  BarChart3,
  Bell,
  Download,
  History,
  LayoutDashboard,
  RefreshCw,
  Target,
  Upload,
  Wallet,
  X,
} from 'lucide-react';
import './portfolio.css';
import { evaluate, normalize, withEvent, planOf, PLANS, ADD_DROP, REBUY_DROP, MAX_UNITS } from './positionEngine';

const KEY = 'marketintel_portfolio';

const money = (v, d = 2) => {
  if (v == null || !Number.isFinite(Number(v))) return '—';
  return `$${Number(v).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d })}`;
};
const pct = (v) => {
  if (v == null || !Number.isFinite(Number(v))) return '—';
  return `${Number(v) >= 0 ? '+' : ''}${(Number(v) * 100).toFixed(1)}%`;
};
const qtyFmt = (v) => (v == null || !Number.isFinite(Number(v)) ? '—' : Number(v).toLocaleString('nl-NL', { maximumFractionDigits: 2 }));

const read = () => {
  try {
    return JSON.parse(localStorage.getItem(KEY) || '[]').map(normalize);
  } catch {
    return [];
  }
};
const write = (rows) => {
  localStorage.setItem(KEY, JSON.stringify(rows));
  window.dispatchEvent(new Event('marketintel-portfolio-change'));
};

const SIGNAL_LABEL = { TP: 'WINSTNIVEAU', ADD: 'BIJKOOPNIVEAU', REBUY: 'TERUGKOOPNIVEAU', HOLD: 'GEEN NIVEAU', REVIEW: 'OPNIEUW BEOORDELEN', CLOSED: 'GESLOTEN' };
const SIGNAL_TONE = { TP: 'tp', ADD: 'add', REBUY: 'rebuy', HOLD: 'hold', REVIEW: 'review', CLOSED: 'hold' };
const EVENT_LABEL = { buy: 'Gekocht', add: 'Bijgekocht', rebuy: 'Teruggekocht', tp: 'Winst genomen', sell: 'Verkocht' };

function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="sideBrand">
        <div className="brandMark"><Activity size={18} /></div>
        <div>
          <b>MARKET<span>INTEL</span></b>
          <small>TRADER PATTERN SCANNER</small>
        </div>
      </div>
      <nav>
        <div className="navLabel">WORKSPACE</div>
        <Link href="/" className="navItem"><LayoutDashboard size={16} />Scanner</Link>
        <Link href="/portfolio" className="navItem active"><Wallet size={16} />Portfolio</Link>
        <Link href="/history" className="navItem"><History size={16} />Alert history</Link>
        <Link href="/performance" className="navItem"><BarChart3 size={16} />Performance</Link>
        <Link href="/validation" className="navItem"><Target size={16} />Model validation</Link>
      </nav>
      <div className="sideBottom">
        <div className="liveStatus"><span className="liveDot" />PORTFOLIO ACTIEF</div>
      </div>
    </aside>
  );
}

function ActionForm({ type, price, qty, onCancel, onSave }) {
  const [q, setQ] = useState(qty != null ? String(Math.round(qty * 100) / 100) : '');
  const [p, setP] = useState(price != null ? String(Number(price).toFixed(2)) : '');
  const ok = Number(q) > 0 && Number(p) > 0;
  return (
    <div className="actionForm">
      <label>Aantal<input type="number" min="0" step="any" value={q} onChange={(e) => setQ(e.target.value)} /></label>
      <label>Prijs per aandeel<input type="number" min="0" step="0.01" value={p} onChange={(e) => setP(e.target.value)} /></label>
      <button className="refresh primary" disabled={!ok} onClick={() => onSave({ type, qty: Number(q), price: Number(p) })}>Opslaan</button>
      <button className="refresh secondary" onClick={onCancel}>Annuleren</button>
    </div>
  );
}

function PositionCard({ position, r, onChange, onRemove }) {
  const ev = useMemo(() => evaluate(position, r), [position, r]);
  const [form, setForm] = useState(null); // { type, qty, price }
  const st = ev.state;
  const tone = SIGNAL_TONE[ev.signal] || 'hold';
  const events = [...position.events].sort((a, b) => String(b.date).localeCompare(String(a.date)));
  const c = r?.dip_context || {};

  const openForm = (type, qty) => setForm({ type, qty, price: ev.price });
  const save = (e) => {
    onChange(withEvent(position, e));
    setForm(null);
  };
  const primaryType = ev.signal === 'TP' ? 'tp' : ev.signal === 'ADD' ? 'add' : ev.signal === 'REBUY' ? 'rebuy' : null;

  return (
    <div className="positionCard">
      <div className="positionTop">
        <div>
          <span className="positionTicker">{position.ticker}</span>
          <span className="positionCompany">{position.company}</span>
        </div>
        <span className={`positionAction ${tone}`}>{SIGNAL_LABEL[ev.signal]}</span>
      </div>

      <div className="positionMain">
        <div><span>HUIDIGE KOERS</span><strong>{money(ev.price)}</strong></div>
        <div><span>GEM. KOERS</span><strong>{money(st.avg)}</strong></div>
        <div><span>AANTAL</span><strong>{qtyFmt(st.shares)}</strong></div>
        <div><span>POSITIE</span><strong>{money(ev.pnl?.value)}</strong></div>
        <div>
          <span>RENDEMENT TOTAAL</span>
          <strong className={ev.pnl == null || ev.pnl.total >= 0 ? 'positive' : 'negative'}>
            {ev.pnl == null ? '—' : `${ev.pnl.total >= 0 ? '+' : ''}${money(ev.pnl.total)} (${pct(ev.pnl.totalPct)})`}
          </strong>
        </div>
      </div>

      <div className={`positionAlert ${tone}`}>
        <div>
          <Bell size={16} />
          <div>
            <b>{ev.title}</b>
            <span>{ev.reason}</span>
            {primaryType && ev.qty != null && (
              <span className="suggest">Volgens het plan: {qtyFmt(ev.qty)} aandelen ≈ {money(ev.amount, 0)}</span>
            )}
          </div>
        </div>
      </div>

      {ev.notes.map((n, i) => (
        <div key={i} className={`posNote ${n.tone}`}>{n.tone === 'warn' ? '⚠ ' : 'ℹ '}{n.text}</div>
      ))}

      {form ? (
        <ActionForm type={form.type} price={form.price} qty={form.qty} onCancel={() => setForm(null)} onSave={save} />
      ) : (
        <div className="actionRow">
          {primaryType && <button className="refresh primary" onClick={() => openForm(primaryType, ev.qty)}>Gedaan: {EVENT_LABEL[primaryType].toLowerCase()}</button>}
          {ev.signal !== 'CLOSED' && <button className="refresh secondary" onClick={() => openForm('add', null)}>Bijgekocht</button>}
          {ev.signal !== 'CLOSED' && <button className="refresh secondary" onClick={() => openForm('tp', st.shares * planOf(position).sell)}>Winst genomen</button>}
          {ev.signal !== 'CLOSED' && <button className="refresh secondary" onClick={() => openForm('rebuy', null)}>Teruggekocht</button>}
          {ev.signal !== 'CLOSED' && <button className="refresh secondary" onClick={() => openForm('sell', st.shares)}>Alles verkocht</button>}
        </div>
      )}

      <div className="levelRow">
        <span>Volgende winstnemen <b>{ev.levels.nextTP ? `${money(ev.levels.nextTP)} (+${Math.round(ev.levels.nextTPpct * 100)}%)` : 'alle trappen gehad'}</b></span>
        <span>Bijkopen onder <b>{ev.levels.add ? money(ev.levels.add) : `max ${MAX_UNITS - 1}x gedaan`}</b></span>
        <span>Terugkopen onder <b>{ev.levels.rebuy ? money(ev.levels.rebuy) : '—'}</b></span>
        {st.pool > 0 && <span>Terugkoop-potje <b>{money(st.pool, 0)}</b></span>}
      </div>

      <div className="positionMeta">
        <span>Koersdoel analisten <b>{c.pt_upside != null ? pct(c.pt_upside) : '—'}</b></span>
        <span>Consensus <b>{c.grades_consensus || '—'}</b></span>
        <span>Volgende cijfers <b>{r?.next_earnings_date ? String(r.next_earnings_date).slice(0, 10) : '—'}</b></span>
        <span>Omzetgroei <b>{r?.revenue_growth != null && Math.abs(r.revenue_growth) < 5 ? pct(r.revenue_growth) : '—'}</b></span>
        <button onClick={() => onRemove(position.ticker)} title="Verwijder positie"><X size={14} /></button>
      </div>

      <details className="eventLog">
        <summary>Geschiedenis ({events.length})</summary>
        <ul>
          {events.map((e, i) => (
            <li key={i}>{new Date(e.date).toLocaleDateString('nl-NL')} · {EVENT_LABEL[e.type] || e.type} · {qtyFmt(e.qty)} × {money(e.price)}</li>
          ))}
        </ul>
      </details>
    </div>
  );
}

export default function PortfolioPage() {
  const [positions, setPositions] = useState([]);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const fileRef = useRef(null);

  const load = async () => {
    setPositions(read());
    setLoading(true);
    try {
      const res = await fetch(`/api/scan?ts=${Date.now()}`, { cache: 'no-store' });
      if (res.ok) setData(await res.json());
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    const onChange = () => setPositions(read());
    window.addEventListener('marketintel-portfolio-change', onChange);
    const timer = setInterval(load, 60000);
    return () => {
      window.removeEventListener('marketintel-portfolio-change', onChange);
      clearInterval(timer);
    };
  }, []);

  const map = useMemo(() => Object.fromEntries((data?.results || []).map((r) => [r.ticker, r])), [data]);

  const update = (next) => {
    const rows = read().map((p) => (p.ticker === next.ticker ? next : p));
    write(rows);
    setPositions(rows);
  };
  const remove = (ticker) => {
    if (!window.confirm(`Positie ${ticker} verwijderen uit je portfolio?`)) return;
    const rows = read().filter((x) => x.ticker !== ticker);
    write(rows);
    setPositions(rows);
  };

  const evals = useMemo(() => positions.map((p) => ({ p, ev: evaluate(p, map[p.ticker]) })), [positions, map]);
  const stats = useMemo(() => {
    let ext = 0, value = 0, cash = 0;
    for (const { ev } of evals) {
      if (!ev.pnl) continue;
      ext += ev.state.ext;
      cash += ev.state.cash;
      value += ev.pnl?.value || 0;
    }
    // Hoeveel er in totaal in kan als alle bijkoopniveaus worden gebruikt (eerste inleg x maximaal aantal eenheden)
    let maxExt = 0;
    for (const { ev } of evals) {
      if (!ev.pnl) continue;
      maxExt += ev.state.ext + Math.max(0, MAX_UNITS - ev.state.units) * (ev.state.unitCost || 0);
    }
    return { ext, maxExt, total: cash + value - ext, totalPct: ext ? (cash + value) / ext - 1 : null };
  }, [evals]);
  const sectorNote = useMemo(() => {
    const cnt = {};
    let open = 0;
    for (const { p, ev } of evals) {
      if (ev.signal === 'CLOSED') continue;
      open += 1;
      const sec = map[p.ticker]?.sector || p.entryFacts?.sector;
      if (sec) cnt[sec] = (cnt[sec] || 0) + 1;
    }
    const top = Object.entries(cnt).sort((a, b) => b[1] - a[1])[0];
    return top && top[1] >= 3 ? `${top[1]} van je ${open} posities zitten in de sector ${top[0]}. Aandelen in dezelfde sector bewegen vaak samen, dus het risico is groter dan het aantal posities doet vermoeden.` : null;
  }, [evals, map]);
  const counts = useMemo(() => {
    const c = { TP: 0, ADD: 0, REBUY: 0, HOLD: 0, REVIEW: 0 };
    evals.forEach(({ ev }) => { if (c[ev.signal] != null) c[ev.signal] += 1; });
    return c;
  }, [evals]);

  const exportData = () => {
    const blob = new Blob([JSON.stringify(read(), null, 2)], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `portfolio-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(a.href);
  };
  const importData = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const rows = JSON.parse(await file.text());
      if (!Array.isArray(rows)) throw new Error('geen lijst');
      write(rows.map(normalize));
      setPositions(read());
    } catch {
      window.alert('Dit bestand is geen geldige portfolio-export.');
    }
    e.target.value = '';
  };

  return (
    <div className="appShell">
      <Sidebar />
      <main className="dashboard">
        <header className="topbar">
          <div>
            <div className="eyebrow">PORTFOLIO / POSITIEPLAN</div>
            <h1>Mijn portfolio</h1>
            <p>De app volgt je posities met het positieplan van model 6.2: winst nemen in stappen, bijkopen, terugkopen en altijd een restpositie houden. Dit is geen financieel advies.</p>
          </div>
          <div className="topActions">
            <div className="scanMeta">
              <span className="liveDot" /> SCANNER <b>{data?.generated_at ? new Date(data.generated_at).toLocaleTimeString('nl-NL', { hour: '2-digit', minute: '2-digit' }) : '—'}</b>
            </div>
            <Link href="/" className="refresh secondary"><LayoutDashboard size={15} /> Scanner</Link>
            <button className="refresh secondary" onClick={exportData}><Download size={15} /> Export</button>
            <button className="refresh secondary" onClick={() => fileRef.current?.click()}><Upload size={15} /> Import</button>
            <input ref={fileRef} type="file" accept="application/json" hidden onChange={importData} />
            <button className="refresh primary" onClick={load}><RefreshCw size={15} /> Vernieuwen</button>
          </div>
        </header>

        <section className="heroGrid">
          <div className="heroPanel">
            <div>
              <span className="sectionEyebrow">PORTFOLIO OVERVIEW</span>
              <h2>Stand van je posities</h2>
              <p>Je posities staan alleen in deze browser en zijn voor niemand anders zichtbaar. Maak af en toe een export als back-up.</p>
            </div>
            <div className="heroStats">
              <div><span>POSITIES</span><strong>{positions.length}</strong><small>aandelen</small></div>
              <div><span>INLEG</span><strong>{money(stats.ext, 0)}</strong><small>totaal geïnvesteerd · tot {money(stats.maxExt, 0)} als alle bijkoopniveaus worden gebruikt</small></div>
              <div>
                <span>RENDEMENT TOTAAL</span>
                <strong className={stats.total >= 0 ? 'positive' : 'negative'}>{stats.totalPct == null ? '—' : pct(stats.totalPct)}</strong>
                <small>{stats.ext ? money(stats.total, 0) : 'geen posities'}</small>
              </div>
            </div>
          </div>
          <div className="heroSignal">
            <div className="signalHeader"><span>SIGNALEN NU</span><Wallet size={15} /></div>
            <div className="portfolioSignalSummary five">
              <div><strong>{counts.TP}</strong><span>WINSTNIVEAU</span></div>
              <div><strong>{counts.ADD}</strong><span>BIJKOOPNIVEAU</span></div>
              <div><strong>{counts.REBUY}</strong><span>TERUGKOOPNIVEAU</span></div>
              <div><strong>{counts.HOLD}</strong><span>GEEN NIVEAU</span></div><div><strong>{counts.REVIEW}</strong><span>BEOORDELEN</span></div>
            </div>
          </div>
        </section>

        <section className="sectionBlock">
          <div className="sectionHeader">
            <div>
              <div className="sectionEyebrow">01 · POSITIES</div>
              <h2>Actieve posities</h2>
              <p>Heb je een stap uitgevoerd, klik dan op “Gedaan”. Dan houdt de app je gemiddelde koers, het terugkoop-potje en de volgende niveaus bij.</p>
            </div>
            <div className="statusPill live"><Activity size={13} />{positions.length} actief</div>
          </div>

          {sectorNote && <div className="posNote" style={{ margin: '0 12px 12px' }}>ℹ {sectorNote}</div>}
          {loading && !positions.length ? (
            <div className="emptyState">Portfolio laden...</div>
          ) : positions.length === 0 ? (
            <div className="emptyState alertEmpty">
              <div className="emptyIcon"><Wallet size={20} /></div>
              <strong>Nog geen posities</strong>
              <span>Je kunt alleen een aandeel toevoegen dat een actief signaal heeft. Open een signaal en klik op “Voeg toe aan portfolio”.</span>
              <Link href="/" className="refresh primary"><Bell size={14} /> Bekijk signalen</Link>
            </div>
          ) : (
            <div className="positionGrid">
              {positions.map((p) => (
                <PositionCard key={p.ticker} position={p} r={map[p.ticker]} onChange={update} onRemove={remove} />
              ))}
            </div>
          )}
        </section>

        <section className="sectionBlock">
          <div className="sectionHeader">
            <div>
              <div className="sectionEyebrow">02 · REGELS</div>
              <h2>Hoe het positieplan werkt</h2>
              <p>Deze regels komen uit een historische simulatie op de S&P 500 en Nasdaq-100 (2020-2026, 6 maanden vooruit), waarin ongeveer 70% van de gesimuleerde posities na 6 maanden in de plus stond. Dat is een gemiddelde over alle jaren, in slechte periodes ligt het lager. Een simulatie, geen garantie en geen financieel advies. Posities die vóór 6.2 zijn geopend houden hun oorspronkelijke niveaus (+10/25/50/100%, 20% per trap).</p>
            </div>
            <Target size={18} />
          </div>
          <div className="signalRules five">
            <div>
              <span className="positionAction tp">WINSTNIVEAU</span>
              <p>Bij {PLANS['6.2'].tiers.map((t) => `+${Math.round(t * 100)}%`).join(', ')} boven je gemiddelde koers verkoopt het plan telkens {PLANS['6.2'].sell * 100}% van de aandelen. Er blijft altijd een restpositie.</p>
            </div>
            <div>
              <span className="positionAction add">BIJKOOPNIVEAU</span>
              <p>Het plan koopt bij als de koers {ADD_DROP * 100}% of meer onder je gemiddelde koers staat en het aandeel nog in een dip zit. Eén eenheid is je eerste inleg, maximaal {MAX_UNITS - 1} keer, minimaal 7 dagen na de vorige aankoop. In totaal kan een positie dus tot {MAX_UNITS} keer je eerste inleg groeien.</p>
            </div>
            <div>
              <span className="positionAction rebuy">TERUGKOOPNIVEAU</span>
              <p>Zakt de koers {REBUY_DROP * 100}% onder je laatste verkoopprijs, dan koopt het plan de opbrengst van de winstnemingen terug. Daarna beginnen de winsttrappen opnieuw.</p>
            </div>
            <div>
              <span className="positionAction hold">GEEN NIVEAU</span>
              <p>In alle andere gevallen gebeurt er niets. Cijfers, analisten en koersdoelen staan erbij als context.</p>
            </div>
            <div>
              <span className="positionAction review">OPNIEUW BEOORDELEN</span>
              <p>Er is geen vaste stop. De app meldt wel als er iets in het bedrijf verandert sinds het signaal: omzetgroei onder de 10%, negatieve vrije kasstroom, koers boven het koersdoel van analisten, een sell-consensus of kwartaalcijfers onder de verwachting. Dat is een moment om opnieuw te kijken, geen verkoopopdracht. Deze controle is niet historisch getest.</p>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
