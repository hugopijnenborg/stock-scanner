'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { RefreshCw, Bell, Search, Activity, ArrowUpRight, Database, BarChart3, X, TrendingUp, ShieldCheck, LineChart, History, LayoutDashboard, Target, ChevronRight, CircleDot } from 'lucide-react';
import Link from 'next/link';

function pct(v) { return v == null || Number.isNaN(Number(v)) ? '—' : `${(Number(v) * 100).toFixed(1)}%`; }
function score(v) { return v == null || Number.isNaN(Number(v)) ? '—' : Number(v).toFixed(0); }
function num(v, d = 1) { return v == null || Number.isNaN(Number(v)) ? '—' : Number(v).toFixed(d); }

function reasons(r) {
  const a = [];
  if (Number(r.rsi_14) < 30) a.push(`RSI ${num(r.rsi_14)} oversold`);
  else if (Number(r.rsi_14) < 35) a.push(`RSI ${num(r.rsi_14)} laag`);
  if (Number(r.return_5d) <= -0.06) a.push(`${pct(r.return_5d)} in 5 dagen`);
  else if (Number(r.return_10d) <= -0.1) a.push(`${pct(r.return_10d)} in 10 dagen`);
  if (Number(r.volume_ratio) >= 1.5) a.push(`${num(r.volume_ratio)}x normaal volume`);
  if (Number(r.distance_52w_high) < -0.15) a.push(`${pct(r.distance_52w_high)} onder 52-weeks high`);
  if (Number(r.analyst_score) >= 75) a.push(`Analisten: ${r.analyst_recommendation || 'positief'}`);
  return a.slice(0, 5);
}

function signalLabel(r) {
  return r?.signal === 'ALERT' ? 'BUY ALERT' : 'NO SIGNAL';
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
    <div><span>Sector</span><b>{r.sector || '—'}</b></div>
    <div><span>PE vs sector</span><b>{num(r.pe_vs_sector, 2)}</b></div>
    <div><span>FCF marge</span><b>{pct(r.fcf_margin)}</b></div>
  </div>;
}

function AnalystPanel({ r }) {
  const counts = [['Strong Buy', r.analyst_strong_buy], ['Buy', r.analyst_buy], ['Hold', r.analyst_hold], ['Sell', r.analyst_sell], ['Strong Sell', r.analyst_strong_sell]];
  const targetUpside = r.analyst_target_upside_live != null ? r.analyst_target_upside_live : r.analyst_target_upside;
  return <div className="analystPanel">
    <div className="analystTop">
      <div><span>CONSENSUS</span><b>{r.analyst_recommendation || '—'}</b></div>
      <div><span>ANALISTEN</span><b>{r.analyst_count ?? '—'}</b></div>
      <div><span>ANALYST SCORE</span><b>{score(r.analyst_score)}</b></div>
    </div>
    <div className="ratingCounts">{counts.map(([label, value]) => <div key={label}><span>{label}</span><b>{value ?? 0}</b></div>)}</div>
    <div className="targetGrid">
      <div><span>Huidige koers</span><b>${num(r.price, 2)}</b></div>
      <div><span>Gemiddeld doel</span><b>${num(r.analyst_target_mean, 2)}</b></div>
      <div><span>Mediaan doel</span><b>${num(r.analyst_target_median, 2)}</b></div>
      <div><span>Laagste doel</span><b>${num(r.analyst_target_low, 2)}</b></div>
      <div><span>Hoogste doel</span><b>${num(r.analyst_target_high, 2)}</b></div>
      <div><span>Upside gemiddeld</span><b>{pct(targetUpside)}</b></div>
    </div>
    <div className="analystChanges"><span>Laatste 30 dagen</span><b>{r.analyst_bullish_changes_30d ?? 0} bullish</b><b>{r.analyst_bearish_changes_30d ?? 0} bearish</b><b>{r.analyst_target_changes_30d ?? 0} target changes</b></div>
  </div>;
}

function MiniChart({ r }) {
  const points = Array.isArray(r.history_6m) ? r.history_6m.filter(x => x && Number.isFinite(Number(x.close))).slice(-90) : Array.isArray(r.history) ? r.history.filter(x => x && Number.isFinite(Number(x.close))).slice(-90) : [];
  if (points.length < 2) return <div className="chartEmpty"><LineChart size={20} /><span>Historische koersdata wordt nog opgebouwd.</span></div>;
  const w = 760, h = 250, p = 18, vals = points.map(x => Number(x.close)), min = Math.min(...vals), max = Math.max(...vals), range = max - min || 1;
  const path = vals.map((v, i) => `${p + (i / (vals.length - 1)) * (w - p * 2)},${h - p - ((v - min) / range) * (h - p * 2)}`).join(' ');
  return <div className="chartWrap"><svg viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none"><polyline points={path} fill="none" stroke="currentColor" strokeWidth="2.5" vectorEffect="non-scaling-stroke" /></svg><div className="chartLabels"><span>{points[0].date || ''}</span><span>{points[points.length - 1].date || ''}</span></div></div>;
}

function Detail({ r, onClose }) {
  if (!r) return null;
  return <div className="modalBackdrop" onClick={onClose}>
    <div className="detailPanel" onClick={e => e.stopPropagation()}>
      <div className="detailTop"><div><span className="eyebrow">AANDELENANALYSE</span><h2>{r.company_name || r.ticker}</h2><div className="detailTicker">{r.ticker} · ${num(r.price, 2)}</div></div><button className="closeBtn" onClick={onClose}><X size={18} /></button></div>
      <div className="detailScore"><div><span>TOTAALSCORE</span><strong>{score(r.overall_score)}<small>/100</small></strong></div><span className={`signal ${String(r.signal).toLowerCase()}`}>{signalLabel(r)}</span></div>
      <div className="detailCards"><div><TrendingUp size={16} /><span>Trader · 50%</span><b>{score(r.trader_similarity_score)}</b></div><div><Activity size={16} /><span>Technical · 30%</span><b>{score(r.technical_score)}</b></div><div><Target size={16} /><span>Analyst · 20%</span><b>{score(r.analyst_score)}</b></div><div><ShieldCheck size={16} /><span>Fundamentals</span><b>INFO</b></div></div>
      <div className="detailSection"><h3>Koersverloop</h3><MiniChart r={r} /><div className="chartStats"><span>Huidige koers <b>${num(r.price, 2)}</b></span><span>52W high <b>${num(r.high_52w, 2)}</b></span><span>Onder 52W high <b>{pct(r.distance_52w_high)}</b></span></div></div>
      <div className="detailSection"><h3>Waarom deze score?</h3><div className="reasonList">{reasons(r).length ? reasons(r).map((x, i) => <div key={i}>{x}</div>) : <div>Geen dominante signalen gevonden.</div>}</div><div className="scoreMethod"><span>Score-opbouw</span><b>50% Trader · 30% Technical · 20% Analyst</b><small>Fundamentals beïnvloeden de alertscore niet.</small></div></div>
      <div className="detailSection"><h3>Analisten & koersdoelen</h3><AnalystPanel r={r} /></div>
      <div className="detailSection"><h3>Technische data</h3><div className="detailGrid"><div><span>RSI 14</span><b>{num(r.rsi_14)}</b></div><div><span>MACD histogram</span><b>{num(r.macd_histogram, 3)}</b></div><div><span>Volume ratio</span><b>{num(r.volume_ratio, 2)}x</b></div><div><span>ATR</span><b>{pct(r.atr_pct)}</b></div><div><span>Onder 52W high</span><b>{pct(r.distance_52w_high)}</b></div><div><span>vs SMA20</span><b>{pct(r.distance_sma20)}</b></div><div><span>vs SMA50</span><b>{pct(r.distance_sma50)}</b></div><div><span>Rel. strength</span><b>{pct(r.relative_strength_20d)}</b></div></div></div>
      <div className="detailSection"><h3>Fundamentals · alleen ter beoordeling</h3><Fundamentals r={r} /></div>
    </div>
  </div>;
}

function ScoreRing({ value, size = 'large' }) {
  const v = Math.max(0, Math.min(100, Number(value) || 0));
  return <div className={`scoreRing ${size}`} style={{ '--score': `${v * 3.6}deg` }}><div><strong>{score(value)}</strong><span>/100</span></div></div>;
}

function Sidebar({ alerts }) {
  return <aside className="sidebar">
    <div className="sideBrand"><div className="brandMark"><Activity size={18} /></div><div><b>MARKET<span>INTEL</span></b><small>TRADER PATTERN SCANNER</small></div></div>
    <nav><div className="navLabel">WORKSPACE</div><Link href="/" className="navItem active"><LayoutDashboard size={16} />Scanner</Link><Link href="/history" className="navItem"><History size={16} />Alert history</Link><Link href="/performance" className="navItem"><BarChart3 size={16} />Performance</Link><Link href="/validation" className="navItem"><Target size={16} />Model validation</Link></nav>
    <div className="sideBottom"><div className="liveStatus"><span className="liveDot" />MARKTSCANNER ACTIEF</div><div className="sideStat"><span>ACTIEVE ALERTS</span><strong>{alerts.length}</strong></div></div>
  </aside>;
}

export default function Home() {
  const [data, setData] = useState(null), [loading, setLoading] = useState(true), [scanning, setScanning] = useState(false), [error, setError] = useState(''), [query, setQuery] = useState(''), [showAll, setShowAll] = useState(false), [selected, setSelected] = useState(null), [scanMessage, setScanMessage] = useState('');

  async function load() {
    setLoading(true); setError(''); setScanMessage('');
    try { const x = await fetch('/api/scan?ts=' + Date.now(), { cache: 'no-store' }); const body = await x.json(); if (!x.ok) throw Error(body.error || 'Latest scan is niet beschikbaar.'); setData(body); }
    catch (e) { setError(e.message); }
    finally { setLoading(false); }
  }

  async function startScan() {
    if (scanning) return;
    const previous = data?.generated_at || '';
    setScanning(true); setError(''); setScanMessage('Scan wordt gestart...');
    try {
      const trigger = await fetch('/api/trigger-scan', { method: 'POST' });
      const triggerBody = await trigger.json().catch(() => ({}));
      if (!trigger.ok) throw Error(triggerBody.error || 'De scan kon niet worden gestart.');
      setScanMessage('Scan gestart. Marktdata wordt opnieuw berekend...');
      const started = Date.now(), maxWait = 10 * 60 * 1000;
      while (Date.now() - started < maxWait) {
        await new Promise(resolve => setTimeout(resolve, 10000));
        const x = await fetch('/api/scan?ts=' + Date.now(), { cache: 'no-store' });
        if (!x.ok) continue;
        const body = await x.json();
        if (body?.generated_at && body.generated_at !== previous) { setData(body); setScanMessage('Nieuwe scan voltooid.'); return; }
      }
      throw Error('De scan duurt langer dan verwacht. Controleer over een paar minuten opnieuw.');
    } catch (e) { setError(e.message); setScanMessage(''); }
    finally { setScanning(false); }
  }

  useEffect(() => { load(); }, []);

  const all = data?.results || [];
  const alerts = useMemo(() => all.filter(r => r.signal === 'ALERT').sort((a, b) => Number(b.overall_score) - Number(a.overall_score)), [all]);
  const opps = useMemo(() => all.filter(r => r.signal !== 'ALERT').sort((a, b) => Number(b.overall_score) - Number(a.overall_score)).slice(0, 10), [all]);
  const filtered = useMemo(() => all.filter(r => !query || `${r.ticker} ${r.company_name || ''}`.toLowerCase().includes(query.toLowerCase())).sort((a, b) => Number(b.overall_score) - Number(a.overall_score)), [all, query]);
  const top = alerts[0] || opps[0];
  const avg = all.length ? all.reduce((s, r) => s + Number(r.overall_score || 0), 0) / all.length : 0;
  const highQuality = all.filter(r => Number(r.overall_score) >= 75).length;

  return <div className="appShell">
    <Sidebar alerts={alerts} />
    <main className="dashboard">
      <header className="topbar"><div><div className="eyebrow">MARKET INTELLIGENCE / LIVE SCANNER</div><h1>Market intelligence</h1><p>Trader pattern, technische setup en analistenconsensus in één score.</p></div><div className="topActions"><div className="scanMeta"><span className="liveDot" /> LIVE DATA <b>{data?.generated_at ? new Date(data.generated_at).toLocaleTimeString('nl-NL', { hour: '2-digit', minute: '2-digit' }) : '—'}</b></div><Link href="/history" className="refresh secondary"><History size={15} /> Historie</Link><button className="refresh primary" onClick={startScan} disabled={loading || scanning}><RefreshCw size={15} /> {scanning ? 'Scannen...' : loading ? 'Laden...' : 'Nieuwe scan'}</button></div></header>
      {scanMessage && <div className="scanNotice">{scanMessage}</div>}
      {error && <div className="error">{error}</div>}

      <section className="heroGrid"><div className="heroPanel"><div><span className="sectionEyebrow">SCANNER OVERVIEW</span><h2>Vandaag in de markt</h2><p>De scanner rangschikt {data?.universe_size ?? '—'} bedrijven op de gecombineerde alertscore.</p></div><div className="heroStats"><div><span>MARKTUNIVERSE</span><strong>{data?.universe_size ?? '—'}</strong><small>bedrijven</small></div><div><span>GEM. SCORE</span><strong>{num(avg, 0)}</strong><small>/100</small></div><div><span>STERKE SETUPS</span><strong>{highQuality}</strong><small>score 75+</small></div></div></div><div className="heroSignal"><div className="signalHeader"><span>SCANNER CONVICTION</span><CircleDot size={15} /></div><div className="convictionBody"><ScoreRing value={top?.overall_score || 0} /><div><strong>{top?.ticker || '—'}</strong><span>{top?.company_name || 'Geen topkandidaat'}</span><small>{alerts.length ? 'Hoogste actieve buy alert' : 'Hoogste score onder alertdrempel'}</small></div></div></div></section>

      <section className="kpiGrid"><div className={`kpiCard ${alerts.length ? 'hot' : ''}`}><div className="kpiIcon"><Bell size={17} /></div><div><span>BUY ALERTS</span><strong>{alerts.length}</strong><small>{alerts.length ? 'Direct bekijken' : 'Geen actief signaal'}</small></div><ChevronRight size={15} /></div><div className="kpiCard"><div className="kpiIcon"><Database size={17} /></div><div><span>UNIVERSE</span><strong>{data?.universe_size ?? '—'}</strong><small>Vaste aandelenlijst</small></div><ChevronRight size={15} /></div><div className="kpiCard"><div className="kpiIcon purple"><Activity size={17} /></div><div><span>LAATSTE SCAN</span><strong>{data?.generated_at ? new Date(data.generated_at).toLocaleTimeString('nl-NL', { hour: '2-digit', minute: '2-digit' }) : '—'}</strong><small>{data?.generated_at ? new Date(data.generated_at).toLocaleDateString('nl-NL') : ''}</small></div><ChevronRight size={15} /></div></section>

      <section className="sectionBlock alertBlock"><div className="sectionHeader"><div><div className="sectionEyebrow">01 · ACTION CENTER</div><h2>Actieve buy alerts</h2><p>50% trader · 30% technical · 20% analyst. Fundamentals zijn alleen context.</p></div><div className={`statusPill ${alerts.length ? 'live' : ''}`}><Bell size={13} />{alerts.length} actief</div></div>{alerts.length === 0 ? <div className="emptyState alertEmpty"><div className="emptyIcon"><Bell size={20} /></div><strong>Geen actieve buy alerts</strong><span>De scanner wacht op een gecombineerde score van minimaal 80/100.</span><div className="threshold"><i /><span>Alert threshold <b>80</b></span></div></div> : <div className="alertCards">{alerts.map(r => <button className="alertCard cardButton" key={r.ticker} onClick={() => setSelected(r)}><div className="alertGlow" /><div className="cardTop"><div><span className="tickerBig">{r.ticker}</span><span className="companyName">{r.company_name}</span></div><ScoreRing value={r.overall_score} /></div><div className="priceLine">${num(r.price, 2)} <span className="signal alert">BUY ALERT</span></div><div className="scoreBars"><div><span>TRADER 50%</span><i><b style={{ width: `${Math.min(100, Number(r.trader_similarity_score) || 0)}%` }} /></i><strong>{score(r.trader_similarity_score)}</strong></div><div><span>TECHNICAL 30%</span><i><b style={{ width: `${Math.min(100, Number(r.technical_score) || 0)}%` }} /></i><strong>{score(r.technical_score)}</strong></div><div><span>ANALYST 20%</span><i><b style={{ width: `${Math.min(100, Number(r.analyst_score) || 0)}%` }} /></i><strong>{score(r.analyst_score)}</strong></div></div><div className="why"><span>KEY DRIVERS</span><div>{reasons(r).map((x, i) => <span key={i}>{x}</span>)}</div></div></button>)}</div>}</section>

      <section className="sectionBlock"><div className="sectionHeader"><div><div className="sectionEyebrow">02 · RESEARCH</div><h2>Top opportunities</h2><p>De sterkste kandidaten onder de alertdrempel, gerangschikt op de gecombineerde score.</p></div><Activity size={18} /></div><div className="opportunityGrid">{opps.map((r, i) => <button className="opportunity opportunityButton" key={r.ticker} onClick={() => setSelected(r)}><div className="rank">{String(i + 1).padStart(2, '0')}</div><div className="oppMain"><div><strong>{r.ticker}</strong><span>{r.company_name}</span></div><span className="badge">{r.setup_type}</span></div><div className="oppScore"><strong>{score(r.overall_score)}</strong><small>/100</small></div><div className="oppStats"><span>TRADER <b>{score(r.trader_similarity_score)}</b></span><span>TECH <b>{score(r.technical_score)}</b></span><span>ANALYST <b>{score(r.analyst_score)}</b></span></div></button>)}</div></section>

      <section className="sectionBlock databaseBlock"><div className="sectionHeader"><div><div className="sectionEyebrow">03 · MARKET UNIVERSE</div><h2>Alle gescoorde bedrijven</h2><p>De volledige vaste universe, gerangschikt op alertscore.</p></div><div className="search"><Search size={15} /><input value={query} onChange={e => setQuery(e.target.value)} placeholder="Zoek ticker of bedrijf..." /></div></div><div className="tablewrap"><table><thead><tr><th>#</th><th>BEDRIJF</th><th>SIGNAAL</th><th>SCORE</th><th>TRADER</th><th>TECHNICAL</th><th>ANALYST</th><th>FUNDAMENTALS</th><th>OMZETGROEI</th><th>EPS GROEI</th><th>P/E</th></tr></thead><tbody>{(showAll ? filtered : filtered.slice(0, 20)).map((r, i) => <tr key={r.ticker} onClick={() => setSelected(r)} className="clickRow"><td className="muted">{String(i + 1).padStart(2, '0')}</td><td><div className="company"><span className="ticker">{r.ticker}</span><small>{r.company_name}</small></div></td><td><span className={`signal ${String(r.signal).toLowerCase()}`}>{signalLabel(r)}</span></td><td><div className="tableScore"><b>{score(r.overall_score)}</b><i><em style={{ width: `${Math.min(100, Number(r.overall_score) || 0)}%` }} /></i></div></td><td>{score(r.trader_similarity_score)}</td><td>{score(r.technical_score)}</td><td>{score(r.analyst_score)}</td><td>{score(r.fundamental_score)}</td><td>{pct(r.revenue_growth)}</td><td>{pct(r.eps_growth)}</td><td>{num(r.pe)}</td></tr>)}</tbody></table></div><button className="showMore" onClick={() => setShowAll(!showAll)}>{showAll ? 'Toon minder' : `Toon alle ${filtered.length} bedrijven`} <ArrowUpRight size={13} /></button></section>

      {selected && <Detail r={selected} onClose={() => setSelected(null)} />}
      <section className="footerInfo"><div><Database size={17} /><div><strong>Hoe de score werkt</strong><p>50% trader pattern, 30% technische setup en 20% analisten. Fundamentals worden niet gebruikt voor de alertscore.</p></div></div></section>
      <footer>TRADER PATTERN SCANNER · {data?.generated_at ? new Date(data.generated_at).toLocaleString('nl-NL') : '—'}</footer>
    </main>
  </div>;
}
