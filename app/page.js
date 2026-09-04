'use client';

import { useEffect, useMemo, useState } from 'react';
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
    setLoading(true); setError('');
    try { const x = await fetch('/api/scan?ts=' + Date.now(), { cache: 'no-store' }); const body = await x.json(); if (!x.ok) throw Error(body.error || 'Latest scan is niet beschikbaar.'); setData(body); }
    catch (e) { setError(e.message); }
    finally { setLoading(false); }
  }

  async function startScan() {
    const previous = data?.generated_at || '';
    setScanning(true); setError(''); setScanMessage('Scan wordt gestart...');
    try {
      const trigger = await fetch('/api/trigger-scan', { method: 'POST', cache: 'no-store' });
      const triggerBody = await trigger.json().catch(() => ({}));
      if (!trigger.ok) throw Error(triggerBody.error || 'De scan kon niet worden gestart.');
      setScanMessage('Scan gestart. Marktdata wordt opnieuw berekend...');
      const started = Date.now(), maxWait = 10 * 60 * 1000;
      while (Date.now() - started < maxWait) {
        await new Promise(resolve => setTimeout(resolve, 10000));
        const x = await fetch('/api/scan?ts=' + Date.now(), { cache: 'no-store' });
        if (!x.ok) continue;
        const body = await x.json();
        if (body?.generated_at && body.generated_at !== previous) { setData(body); setScanMessage('Nieuwe scan voltooid.'); setScanning(false); return; }
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
      <header className="topbar"><div><div className="eyebrow">MARKET INTELLIGENCE / LIVE SCANNER</div><h1>Market intelligence</h1><p>Trader pattern, technische setup en analistenconsensus in één score.</p></div><div className="topActions"><div className="scanMeta"><span className="liveDot" /> LIVE DATA <b>{data?.generated_at ? new Date(data.generated_at).toLocaleTimeString('nl-NL', { hour: '2-digit', minute: '2-digit' }) : '—'}</b></div><Link href="/history" className="refresh secondary"><History size={15} /> Historie</Link><button className="refresh primary" onClick={startScan}>{scanning ? <><RefreshCw size={15} className="spin" /> Scan opnieuw</> : <><RefreshCw size={15} /> Nieuwe scan</>}</button></div></header>
      {scanMessage && <div className="scanNotice">{scanMessage}</div>}
      {error && <div className="error">{error}</div>}

      <section className="heroGrid"><div className="heroPanel"><div><span className="sectionEyebrow">SCANNER OVERVIEW</span><h2>Vandaag in de markt</h2><p>De scanner rangschikt {data?.universe_count || all.length || '—'} aandelen op basis van trader pattern, technische setup en analistenconsensus.</p></div><div className="heroStats"><div><span>GESCAND</span><strong>{all.length || '—'}</strong></div><div><span>BUY ALERTS</span><strong>{alerts.length}</strong></div><div><span>GEM. SCORE</span><strong>{all.length ? avg.toFixed(0) : '—'}</strong></div><div><span>≥75 SCORE</span><strong>{highQuality}</strong></div></div></div>{top && <div className="heroOpportunity" onClick={() => setSelected(top)}><div className="opTop"><span>TOP OPPORTUNITY</span><span className={`signal ${String(top.signal).toLowerCase()}`}>{signalLabel(top)}</span></div><div className="opMain"><div><h3>{top.ticker}</h3><p>{top.company_name || '—'}</p></div><ScoreRing value={top.overall_score} /></div><div className="opScores"><span>TRADER <b>{score(top.trader_similarity_score)}</b></span><span>TECHNICAL <b>{score(top.technical_score)}</b></span><span>ANALYST <b>{score(top.analyst_score)}</b></span></div></div>}</section>

      <section className="sectionBlock"><div className="sectionHead"><div><span className="sectionEyebrow">BUY ALERTS</span><h2>Actieve signalen</h2></div><span className="countBadge">{alerts.length}</span></div>{alerts.length ? <div className="alertGrid">{alerts.map(r => <button key={r.ticker} className="alertCard" onClick={() => setSelected(r)}><div className="cardTop"><span>{r.ticker}</span><span className="signal alert">BUY ALERT</span></div><div className="cardName">{r.company_name || '—'}</div><div className="cardBottom"><div><small>TOTAAL</small><strong>{score(r.overall_score)}</strong></div><div><small>TRADER</small><b>{score(r.trader_similarity_score)}</b></div><div><small>TECH</small><b>{score(r.technical_score)}</b></div><div><small>ANALIST</small><b>{score(r.analyst_score)}</b></div></div></button>)}</div> : <div className="emptyState"><Bell size={20} /><div><b>Geen BUY ALERTS</b><span>Er is momenteel geen aandeel met een totaalscore van 80 of hoger.</span></div></div>}</section>

      <section className="sectionBlock"><div className="sectionHead"><div><span className="sectionEyebrow">TOP OPPORTUNITIES</span><h2>Hoogste scores</h2></div><button className="textButton" onClick={() => setShowAll(!showAll)}>{showAll ? 'Toon minder' : 'Bekijk alles'} <ChevronRight size={15} /></button></div><div className="tableWrap"><table><thead><tr><th>AANDEEL</th><th>KOERS</th><th>TOTAAL</th><th>TRADER</th><th>TECHNICAL</th><th>ANALYST</th><th>RSI</th><th>ONDER 52W HIGH</th></tr></thead><tbody>{(showAll ? filtered : opps).map(r => <tr key={r.ticker} onClick={() => setSelected(r)}><td><b>{r.ticker}</b><span>{r.company_name || '—'}</span></td><td>${num(r.price, 2)}</td><td><strong className={Number(r.overall_score) >= 80 ? 'scoreGood' : ''}>{score(r.overall_score)}</strong></td><td>{score(r.trader_similarity_score)}</td><td>{score(r.technical_score)}</td><td>{score(r.analyst_score)}</td><td>{num(r.rsi_14)}</td><td>{pct(r.distance_52w_high)}</td></tr>)}</tbody></table></div></section>

      <section className="sectionBlock"><div className="sectionHead"><div><span className="sectionEyebrow">UNIVERSE</span><h2>Alle aandelen</h2></div><div className="searchBox"><Search size={16} /><input value={query} onChange={e => setQuery(e.target.value)} placeholder="Zoek ticker of bedrijf..." /></div></div><div className="universeGrid">{filtered.map(r => <button key={r.ticker} className="universeCard" onClick={() => setSelected(r)}><div><b>{r.ticker}</b><span>{r.company_name || '—'}</span></div><strong>{score(r.overall_score)}</strong></button>)}</div></section>
    </main>
    <Detail r={selected} onClose={() => setSelected(null)} />
  </div>;
}
