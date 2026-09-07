'use client';

import { useEffect, useMemo, useState } from 'react';
import { Activity, ArrowUpRight, BarChart3, Bell, ChevronRight, CircleDot, Database, History, LayoutDashboard, LineChart, RefreshCw, Search, ShieldCheck, Target, TrendingUp, X } from 'lucide-react';
import Link from 'next/link';

function pct(v, d = 1) {
  return v == null || !Number.isFinite(Number(v)) ? '—' : `${(Number(v) * 100).toFixed(d)}%`;
}
function signedPct(v, d = 1) {
  return v == null || !Number.isFinite(Number(v)) ? '—' : `${Number(v) >= 0 ? '+' : ''}${(Number(v) * 100).toFixed(d)}%`;
}
function score(v) {
  return v == null || !Number.isFinite(Number(v)) ? '—' : Number(v).toFixed(0);
}
function num(v, d = 1) {
  return v == null || !Number.isFinite(Number(v)) ? '—' : Number(v).toFixed(d);
}
function money(v, d = 0) {
  return v == null || !Number.isFinite(Number(v)) || Number(v) <= 0 ? '—' : `$${Number(v).toLocaleString('en-US', { maximumFractionDigits: d, minimumFractionDigits: d })}`;
}
function dateOnly(v) {
  if (!v) return '—';
  const d = new Date(v);
  return Number.isNaN(d.getTime()) ? String(v).slice(0, 10) : d.toLocaleDateString('nl-NL');
}

function reasons(r) {
  const a = [];
  if (Number(r.rsi_14) < 30) a.push(`RSI ${num(r.rsi_14)} oversold`);
  if (Number(r.return_5d) <= -0.08) a.push(`${pct(r.return_5d)} in 5 dagen`);
  if (Number(r.distance_52w_high) <= -0.15) a.push(`${pct(r.distance_52w_high)} onder 52W high`);
  if (Number(r.volume_ratio) >= 1.5) a.push(`${num(r.volume_ratio)}x normaal volume`);
  if (Number(r.revenue_growth) > 0.1) a.push(`Omzetgroei ${pct(r.revenue_growth)}`);
  if (Number(r.eps_growth) > 0.1) a.push(`EPS-groei ${pct(r.eps_growth)}`);
  if (Number(r.fcf) > 0) a.push('Positieve vrije kasstroom');
  return a.slice(0, 5);
}

function ScoreRing({ value, size = 'large' }) {
  const v = Math.max(0, Math.min(100, Number(value) || 0));
  return <div className={`scoreRing ${size}`} style={{ '--score': `${v * 3.6}deg` }}><div><strong>{score(value)}</strong><span>/100</span></div></div>;
}

function MiniChart({ r }) {
  const points = (Array.isArray(r.history_6m) ? r.history_6m : Array.isArray(r.history) ? r.history : [])
    .filter(x => x && Number.isFinite(Number(x.close)))
    .slice(-140);
  if (points.length < 2) {
    return <div className="chartEmpty"><LineChart size={22} /><span>Historische koersdata is voor dit aandeel niet beschikbaar.</span></div>;
  }
  const w = 900, h = 300, p = 24;
  const vals = points.map(x => Number(x.close));
  const min = Math.min(...vals), max = Math.max(...vals), range = max - min || 1;
  const path = vals.map((v, i) => `${p + (i / (vals.length - 1)) * (w - p * 2)},${h - p - ((v - min) / range) * (h - p * 2)}`).join(' ');
  const start = vals[0], end = vals[vals.length - 1];
  const move = start ? end / start - 1 : null;
  return <div className="marketChart">
    <div className="chartHeader"><span>6 MAAND KOERSVERLOOP</span><b className={Number(move) >= 0 ? 'positive' : 'negative'}>{signedPct(move)}</b></div>
    <div className="chartWrap"><svg viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none"><polyline points={path} fill="none" stroke="currentColor" strokeWidth="3" vectorEffect="non-scaling-stroke" /></svg></div>
    <div className="chartLabels"><span>{dateOnly(points[0].date)}</span><span>{dateOnly(points[points.length - 1].date)}</span></div>
  </div>;
}

function AnalystPanel({ r }) {
  const hasTarget = Number.isFinite(Number(r.analyst_target_mean)) && Number(r.analyst_target_mean) > 0;
  const hasConsensus = r.analyst_recommendation || Number.isFinite(Number(r.analyst_consensus_score));
  const total = Number(r.analyst_count);
  return <div className="analystPanel">
    <div className="analystSummary">
      <div><span>CONSENSUS</span><strong>{hasConsensus ? (r.analyst_recommendation || `${score(r.analyst_consensus_score)}/100`) : 'Niet beschikbaar'}</strong><small>{Number.isFinite(total) && total > 0 ? `${total} beoordelingen` : 'Aantal beoordelingen niet beschikbaar'}</small></div>
      <div><span>GEM. KOERSDOEL</span><strong>{hasTarget ? money(r.analyst_target_mean, 0) : 'Niet beschikbaar'}</strong><small>{hasTarget && Number.isFinite(Number(r.analyst_target_upside)) ? `${signedPct(r.analyst_target_upside)} vanaf huidige koers` : 'Geen betrouwbaar koersdoel'}</small></div>
    </div>
    <div className="analystGrid">
      <div><span>Strong Buy</span><b>{Number(r.analyst_strong_buy) || 0}</b></div>
      <div><span>Buy</span><b>{Number(r.analyst_buy) || 0}</b></div>
      <div><span>Hold</span><b>{Number(r.analyst_hold) || 0}</b></div>
      <div><span>Sell</span><b>{Number(r.analyst_sell) || 0}</b></div>
      <div><span>Strong Sell</span><b>{Number(r.analyst_strong_sell) || 0}</b></div>
      <div><span>Mediaan target</span><b>{Number(r.analyst_target_median) > 0 ? money(r.analyst_target_median, 0) : '—'}</b></div>
      <div><span>Low target</span><b>{Number(r.analyst_target_low) > 0 ? money(r.analyst_target_low, 0) : '—'}</b></div>
      <div><span>High target</span><b>{Number(r.analyst_target_high) > 0 ? money(r.analyst_target_high, 0) : '—'}</b></div>
    </div>
  </div>;
}

function Fundamentals({ r }) {
  return <div className="fundGrid">
    <div><span>Omzetgroei</span><b>{pct(r.revenue_growth)}</b></div>
    <div><span>EPS groei</span><b>{pct(r.eps_growth)}</b></div>
    <div><span>Nettomarge</span><b>{pct(r.net_margin)}</b></div>
    <div><span>FCF</span><b>{r.fcf == null ? '—' : `${(Number(r.fcf) / 1e9).toFixed(2)}B`}</b></div>
    <div><span>ROE</span><b>{pct(r.roe)}</b></div>
    <div><span>Debt / Equity</span><b>{num(r.debt_equity, 2)}</b></div>
    <div><span>P/E</span><b>{num(r.pe)}</b></div>
    <div><span>Forward P/E</span><b>{num(r.forward_pe)}</b></div>
    <div><span>PEG</span><b>{num(r.peg, 2)}</b></div>
  </div>;
}

function FallbackSummary({ r }) {
  const selloff = Number(r.return_5d);
  const target = Number(r.analyst_target_mean);
  const upside = Number(r.analyst_target_upside);
  return <div className="aiText">
    <p><strong>{r.company_name || r.ticker}</strong> heeft een score van {score(r.overall_score)}/100 en voldoet daarmee aan de huidige alertdrempel. De setup wordt vooral gedragen door een trader match van {score(r.trader_similarity_score)}/100 en een technische score van {score(r.technical_score)}/100.</p>
    <p>Technisch staat het aandeel {pct(r.distance_52w_high)} onder de 52-weeks high. De koers staat {pct(r.distance_sma20)} ten opzichte van de SMA20 en de RSI staat op {num(r.rsi_14)}. De 5-daagse beweging bedraagt {signedPct(selloff)}.</p>
    <p>{Number(r.revenue_growth) > 0 ? `De omzet groeit met ${pct(r.revenue_growth)} en ` : ''}{Number(r.eps_growth) > 0 ? `EPS groeit met ${pct(r.eps_growth)}. ` : ''}{Number(r.fcf) > 0 ? 'De vrije kasstroom is positief.' : 'De beschikbare fundamentele data geeft geen positieve vrije kasstroom aan.'}</p>
    <p>{target > 0 ? `Het gemiddelde analistenkoersdoel ligt op ${money(target)} en impliceert ongeveer ${signedPct(upside)} vanaf de huidige koers.` : 'Er is momenteel geen betrouwbaar gemiddeld analistenkoersdoel beschikbaar.'}</p>
  </div>;
}

function Detail({ r, onClose }) {
  const [ai, setAi] = useState(null);
  const [aiLoading, setAiLoading] = useState(false);
  useEffect(() => {
    let cancelled = false;
    async function generate() {
      setAi(null);
      setAiLoading(true);
      try {
        const res = await fetch('/api/alert-summary', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ stock: r }) });
        const body = await res.json();
        if (!cancelled) setAi(body?.summary || null);
      } catch (_) {
        if (!cancelled) setAi(null);
      } finally {
        if (!cancelled) setAiLoading(false);
      }
    }
    generate();
    return () => { cancelled = true; };
  }, [r?.ticker]);
  if (!r) return null;
  const news = Array.isArray(r.recent_news) ? r.recent_news : [];
  return <div className="modalBackdrop" onClick={onClose}>
    <div className="detailPanel" onClick={e => e.stopPropagation()}>
      <div className="detailTop"><div><span className="eyebrow">STOCK OPPORTUNITY ALERT</span><h2>{r.ticker}: <span className="detailBuy">{r.signal === 'ALERT' ? 'BUY' : r.signal}</span></h2><div className="detailTicker">{r.company_name || r.ticker} · ${num(r.price, 2)}</div></div><button className="closeBtn" onClick={onClose}><X size={18} /></button></div>
      <div className="detailScore"><div><span>OPPORTUNITY SCORE</span><strong>{score(r.overall_score)}<small>/100</small></strong></div><span className={`signal ${String(r.signal).toLowerCase()}`}>{r.signal === 'NO_SIGNAL' ? 'NO SIGNAL' : r.signal === 'DATA_INCOMPLETE' ? 'DATA MISSING' : r.signal}</span></div>
      <div className="detailCards"><div><TrendingUp size={16} /><span>Trader match</span><b>{score(r.trader_similarity_score)}</b></div><div><Activity size={16} /><span>Technical</span><b>{score(r.technical_score)}</b></div><div><BarChart3 size={16} /><span>Analyst</span><b>{score(r.analyst_consensus_score)}</b></div><div><ShieldCheck size={16} /><span>Fundamentals</span><b>{score(r.fundamental_score)}</b></div></div>

      <div className="detailSection aiSummarySection"><div className="sectionEyebrow">AI OPPORTUNITY ANALYSIS</div><h3>Waarom nu?</h3>{aiLoading ? <div className="aiLoading"><span className="liveDot" /> Analyse wordt opgebouwd uit de actuele scannerdata...</div> : ai ? <div className="aiText">{ai.split('\n').map((line, i) => line.trim() ? <p key={i}>{line}</p> : null)}</div> : <FallbackSummary r={r} />}</div>

      <div className="detailSection"><h3>Koersverloop</h3><MiniChart r={r} /><div className="chartStats"><span>Huidige koers <b>${num(r.price, 2)}</b></span><span>52W high <b>{money(r.high_52w, 2)}</b></span><span>Onder 52W high <b>{pct(r.distance_52w_high)}</b></span></div></div>

      <div className="detailSection"><h3>Analistenconsensus</h3><AnalystPanel r={r} /></div>

      <div className="detailSection"><h3>Technische setup</h3><div className="detailGrid"><div><span>RSI 14</span><b>{num(r.rsi_14)}</b></div><div><span>1D rendement</span><b>{signedPct(r.return_1d)}</b></div><div><span>3D rendement</span><b>{signedPct(r.return_3d)}</b></div><div><span>5D rendement</span><b>{signedPct(r.return_5d)}</b></div><div><span>20D rendement</span><b>{signedPct(r.return_20d)}</b></div><div><span>Volume ratio</span><b>{num(r.volume_ratio, 2)}x</b></div><div><span>vs SMA20</span><b>{signedPct(r.distance_sma20)}</b></div><div><span>vs SMA50</span><b>{signedPct(r.distance_sma50)}</b></div><div><span>MACD histogram</span><b>{num(r.macd_histogram, 3)}</b></div><div><span>Rel. strength</span><b>{signedPct(r.relative_strength_20d)}</b></div></div></div>

      <div className="detailSection"><h3>Fundamentals · alleen ter beoordeling</h3><Fundamentals r={r} /></div>
      {news.length > 0 && <div className="detailSection"><h3>Recente nieuwscontext</h3><div className="newsList">{news.slice(0, 5).map((n, i) => <div key={i}><b>{n.title}</b><span>{n.publisher || 'Bron onbekend'} · {dateOnly(n.published)}</span></div>)}</div></div>}
    </div>
  </div>;
}

function Sidebar({ alerts, watches }) {
  return <aside className="sidebar"><div className="sideBrand"><div className="brandMark"><Activity size={18} /></div><div><b>MARKET<span>INTEL</span></b><small>TRADER PATTERN SCANNER</small></div></div><nav><div className="navLabel">WORKSPACE</div><Link href="/" className="navItem active"><LayoutDashboard size={16} />Scanner</Link><Link href="/history" className="navItem"><History size={16} />Alert history</Link><Link href="/performance" className="navItem"><BarChart3 size={16} />Performance</Link><Link href="/validation" className="navItem"><Target size={16} />Model validation</Link></nav><div className="sideBottom"><div className="liveStatus"><span className="liveDot" />MARKTSCANNER ACTIEF</div><div className="sideStat"><span>BUY ALERTS</span><strong>{alerts.length}</strong></div><div className="sideStat"><span>WATCH</span><strong>{watches.length}</strong></div></div></aside>;
}

export default function Home() {
  const [data, setData] = useState(null), [loading, setLoading] = useState(true), [error, setError] = useState(''), [query, setQuery] = useState(''), [selected, setSelected] = useState(null), [scanMessage, setScanMessage] = useState('');
  async function load() { setLoading(true); setError(''); try { const x = await fetch('/api/scan?ts=' + Date.now(), { cache: 'no-store' }); const body = await x.json(); if (!x.ok) throw Error(body.error || 'Latest scan is niet beschikbaar.'); setData(body); } catch (e) { setError(e.message); } finally { setLoading(false); } }
  async function startScan() { if (loading) return; const previous = data?.generated_at || ''; setLoading(true); setScanMessage('Scan wordt gestart...'); try { const t = await fetch('/api/trigger-scan', { method: 'POST' }); const tb = await t.json().catch(() => ({})); if (!t.ok) throw Error(tb.error || 'De scan kon niet worden gestart.'); const started = Date.now(); while (Date.now() - started < 10 * 60 * 1000) { await new Promise(r => setTimeout(r, 10000)); const x = await fetch('/api/scan?ts=' + Date.now(), { cache: 'no-store' }); if (!x.ok) continue; const body = await x.json(); if (body?.generated_at && body.generated_at !== previous) { setData(body); setScanMessage('Nieuwe scan voltooid.'); return; } } throw Error('De scan duurt langer dan verwacht.'); } catch (e) { setError(e.message); setScanMessage(''); } finally { setLoading(false); } }
  useEffect(() => { load(); }, []);
  const all = data?.results || [];
  const alerts = useMemo(() => all.filter(r => r.signal === 'ALERT').sort((a, b) => Number(b.overall_score) - Number(a.overall_score)), [all]);
  const watches = useMemo(() => all.filter(r => r.signal === 'WATCH').sort((a, b) => Number(b.overall_score) - Number(a.overall_score)), [all]);
  const opps = useMemo(() => all.filter(r => r.signal !== 'ALERT' && r.signal !== 'WATCH' && r.signal !== 'DATA_INCOMPLETE').sort((a, b) => Number(b.overall_score) - Number(a.overall_score)).slice(0, 10), [all]);
  const filtered = useMemo(() => all.filter(r => !query || `${r.ticker} ${r.company_name || ''}`.toLowerCase().includes(query.toLowerCase())).sort((a, b) => Number(b.overall_score) - Number(a.overall_score)), [all, query]);
  const top = alerts[0] || watches[0] || opps[0];
  const avg = all.length ? all.reduce((s, r) => s + Number(r.overall_score || 0), 0) / all.length : 0;
  return <div className="appShell"><Sidebar alerts={alerts} watches={watches} /><main className="dashboard">
    <header className="topbar"><div><div className="eyebrow">MARKET INTELLIGENCE / LIVE SCANNER</div><h1>Market intelligence</h1><p>Trader pattern, technische setup en analystdata in één overzicht.</p></div><div className="topActions"><div className="scanMeta"><span className="liveDot" /> LIVE DATA <b>{data?.generated_at ? new Date(data.generated_at).toLocaleTimeString('nl-NL', { hour: '2-digit', minute: '2-digit' }) : '—'}</b></div><Link href="/history" className="refresh secondary"><History size={15} /> Historie</Link><button className="refresh primary" onClick={startScan} disabled={loading}><RefreshCw size={15} /> {loading ? 'Laden...' : 'Nieuwe scan'}</button></div></header>
    {scanMessage && <div className="scanNotice">{scanMessage}</div>}{error && <div className="error">{error}</div>}
    <section className="heroGrid"><div className="heroPanel"><div><span className="sectionEyebrow">SCANNER OVERVIEW</span><h2>Vandaag in de markt</h2><p>De scanner controleert de vaste aandelenlijst en rangschikt de actuele setups.</p></div><div className="heroStats"><div><span>MARKTUNIVERSE</span><strong>{data?.universe_size ?? all.length}</strong><small>bedrijven</small></div><div><span>GEM. SCORE</span><strong>{num(avg, 0)}</strong><small>/100</small></div><div><span>STERKE SETUPS</span><strong>{all.filter(r => Number(r.overall_score) >= 75).length}</strong><small>score 75+</small></div></div></div><div className="heroSignal"><div className="signalHeader"><span>SCANNER CONVICTION</span><CircleDot size={15} /></div><div className="convictionBody"><ScoreRing value={top?.overall_score || 0} /><div><strong>{top?.ticker || '—'}</strong><span>{top?.company_name || 'Geen topkandidaat'}</span><small>{alerts.length ? 'Hoogste actieve buy alert' : 'Hoogste actuele setup'}</small></div></div></div></section>
    <section className="kpiGrid"><div className={`kpiCard ${alerts.length ? 'hot' : ''}`}><div className="kpiIcon"><Bell size={17} /></div><div><span>BUY ALERTS</span><strong>{alerts.length}</strong><small>score 80+</small></div><ChevronRight size={15} /></div><div className="kpiCard"><div className="kpiIcon blue"><TrendingUp size={17} /></div><div><span>WATCH</span><strong>{watches.length}</strong><small>hard afgestraft</small></div><ChevronRight size={15} /></div><div className="kpiCard"><div className="kpiIcon"><Database size={17} /></div><div><span>UNIVERSE</span><strong>{data?.universe_size ?? all.length}</strong><small>vaste lijst</small></div><ChevronRight size={15} /></div><div className="kpiCard"><div className="kpiIcon purple"><Activity size={17} /></div><div><span>LAATSTE SCAN</span><strong>{data?.generated_at ? new Date(data.generated_at).toLocaleTimeString('nl-NL', { hour: '2-digit', minute: '2-digit' }) : '—'}</strong><small>{data?.generated_at ? dateOnly(data.generated_at) : ''}</small></div><ChevronRight size={15} /></div></section>

    <section className="sectionBlock"><div className="sectionHeader"><div><div className="sectionEyebrow">01 · ACTION CENTER</div><h2>Actieve buy alerts</h2><p>Een score van 80/100 of hoger activeert een alert.</p></div><div className="statusPill live"><Bell size={13} />{alerts.length} actief</div></div>{alerts.length ? <div className="alertCards">{alerts.map(r => <button className="alertCard cardButton" key={r.ticker} onClick={() => setSelected(r)}><div className="alertGlow" /><div className="cardTop"><div><span className="tickerBig">{r.ticker}</span><span className="companyName">{r.company_name}</span></div><ScoreRing value={r.overall_score} /></div><div className="priceLine">${num(r.price, 2)} <span className="signal alert">BUY ALERT</span></div><div className="scoreBars"><div><span>TRADER</span><i><b style={{ width: `${Math.min(100, Number(r.trader_similarity_score) || 0)}%` }} /></i><strong>{score(r.trader_similarity_score)}</strong></div><div><span>TECHNICAL</span><i><b style={{ width: `${Math.min(100, Number(r.technical_score) || 0)}%` }} /></i><strong>{score(r.technical_score)}</strong></div><div><span>ANALYST</span><i><b style={{ width: `${Math.min(100, Number(r.analyst_consensus_score) || 0)}%` }} /></i><strong>{score(r.analyst_consensus_score)}</strong></div></div><div className="why"><span>KEY DRIVERS</span><div>{reasons(r).map((x, i) => <span key={i}>{x}</span>)}</div></div></button>)}</div> : <div className="emptyState alertEmpty"><strong>Geen actieve buy alerts</strong><span>De scanner wacht op een score van minimaal 80/100.</span></div>}</section>

    <section className="sectionBlock"><div className="sectionHeader"><div><div className="sectionEyebrow">02 · EARLY SIGNAL</div><h2>Watch candidates</h2><p>Geen tweede alertniveau. Alleen aandelen die al hard zijn afgestraft en richting een interessante setup bewegen.</p></div><div className="statusPill"><TrendingUp size={13} />{watches.length} watch</div></div>{watches.length ? <div className="opportunityGrid">{watches.slice(0, 10).map(r => <button className="opportunityCard opportunityButton" key={r.ticker} onClick={() => setSelected(r)}><div><b>{r.ticker}</b><span>{r.company_name}</span></div><strong>{score(r.overall_score)}</strong><small>{signedPct(r.return_5d)} in 5D · RSI {num(r.rsi_14)}</small></button>)}</div> : <div className="emptyState"><strong>Geen watch candidates</strong><span>Er voldoet momenteel geen aandeel aan zowel de score- als sell-offvoorwaarden.</span></div>}</section>

    <section className="sectionBlock"><div className="sectionHeader"><div><div className="sectionEyebrow">03 · RESEARCH</div><h2>Top opportunities</h2><p>Sterke kandidaten die nog geen BUY ALERT of WATCH zijn.</p></div><Activity size={18} /></div><div className="opportunityGrid">{opps.map(r => <button className="opportunityCard opportunityButton" key={r.ticker} onClick={() => setSelected(r)}><div><b>{r.ticker}</b><span>{r.company_name}</span></div><strong>{score(r.overall_score)}</strong><small>Trader {score(r.trader_similarity_score)} · Technical {score(r.technical_score)}</small></button>)}</div></section>

    <section className="sectionBlock"><div className="sectionHeader"><div><div className="sectionEyebrow">04 · MARKET UNIVERSE</div><h2>Alle gescoorde bedrijven</h2><p>Zoek direct in de vaste universe.</p></div><div className="searchBox"><Search size={14} /><input value={query} onChange={e => setQuery(e.target.value)} placeholder="Zoek ticker of bedrijf" /></div></div><div className="universeTable"><div className="tableHead"><span>TICKER</span><span>SIGNAL</span><span>SCORE</span><span>TRADER</span><span>TECHNICAL</span><span>ANALYST</span><span>KOERS</span></div>{filtered.slice(0, 173).map(r => <button className="tableRow" key={r.ticker} onClick={() => setSelected(r)}><span><b>{r.ticker}</b><small>{r.company_name}</small></span><span><i className={`signal ${String(r.signal).toLowerCase()}`}>{r.signal === 'ALERT' ? 'BUY' : r.signal === 'WATCH' ? 'WATCH' : 'NO SIGNAL'}</i></span><span><strong>{score(r.overall_score)}</strong></span><span>{score(r.trader_similarity_score)}</span><span>{score(r.technical_score)}</span><span>{score(r.analyst_consensus_score)}</span><span>${num(r.price, 2)}</span></button>)}</div></section>
    </main>{selected && <Detail r={selected} onClose={() => setSelected(null)} />}</div>;
}
