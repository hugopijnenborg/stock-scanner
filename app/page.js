'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { Activity, Bell, ChevronRight, Database, History, LayoutDashboard, RefreshCw, Search, Target, TrendingUp, X } from 'lucide-react';

const pct = v => v == null || !Number.isFinite(Number(v)) ? '—' : `${(Number(v) * 100).toFixed(1)}%`;
const signed = v => v == null || !Number.isFinite(Number(v)) ? '—' : `${Number(v) >= 0 ? '+' : ''}${(Number(v) * 100).toFixed(1)}%`;
const n = (v, d = 0) => v == null || !Number.isFinite(Number(v)) ? '—' : Number(v).toFixed(d);
const money = (v, d = 2) => v == null || !Number.isFinite(Number(v)) ? '—' : `$${Number(v).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d })}`;
const actionClass = a => String(a || 'NONE').toLowerCase().replaceAll(' ', '-');
const pathName = p => ({ '25pct_1m': '+25% binnen 1 maand', '50pct_3m': '+50% binnen 3 maanden', '100pct_12m': '+100% binnen 12 maanden' }[p] || p || '—');

function Ring({ v, size = '' }) {
  const x = Math.max(0, Math.min(100, Number(v) || 0));
  return <div className={`scoreRing ${size}`} style={{ '--score': `${x * 3.6}deg` }}><div><strong>{n(v, 1)}</strong><span>/100</span></div></div>;
}

function Action({ v }) {
  return <span className={`signal action-${actionClass(v)}`}>{v || 'NONE'}</span>;
}

function Components({ r }) {
  const items = [
    ['Technical', r.opportunity_technical_score],
    ['Fundamentals', r.opportunity_fundamentals_score],
    ['Valuation', r.opportunity_valuation_score],
    ['Analysts', r.opportunity_analysts_score],
    ['Catalysts', r.opportunity_catalysts_score],
    ['Institutional', r.opportunity_institutional_score],
    ['Market / sector', r.opportunity_macro_sector_score],
    ['Liquidity / risk', r.opportunity_liquidity_risk_score],
  ];
  return <div className="componentGrid">{items.map(([label, value]) => <div key={label}><div><span>{label}</span><b>{n(value)}</b></div><i><em style={{ width: `${Math.max(0, Math.min(100, Number(value) || 0))}%` }} /></i></div>)}</div>;
}

function Analyst({ r }) {
  const rows = [
    ['Strong Buy', r.analyst_strong_buy], ['Buy', r.analyst_buy], ['Hold', r.analyst_hold], ['Sell', r.analyst_sell], ['Strong Sell', r.analyst_strong_sell],
  ];
  const total = rows.reduce((s, [, v]) => s + (Number(v) || 0), 0) || Number(r.analyst_count) || 0;
  let firms = r.analyst_firm_targets;
  if (typeof firms === 'string') { try { firms = JSON.parse(firms); } catch { firms = []; } }
  if (!Array.isArray(firms)) firms = firms && typeof firms === 'object' ? Object.entries(firms).map(([name, value]) => ({ name, target: value })) : [];
  return <div className="analystPanel analystPanelLarge">
    <div className="analystHero">
      <div className="consensusBlock"><span>ANALISTENCONSENSUS</span><strong>{r.analyst_recommendation || 'Niet beschikbaar'}</strong><small>{total || 'Geen'} beoordelingen</small></div>
      <div className="targetBlock"><span>GEMIDDELD KOERSDOEL</span><strong>{r.analyst_target_mean != null ? money(r.analyst_target_mean) : 'Niet beschikbaar'}</strong><small>{r.analyst_target_upside != null ? signed(r.analyst_target_upside) : 'Geen betrouwbaar koersdoel'}</small></div>
    </div>
    <div className="analystBody">
      <div className="consensusDistribution">{rows.map(([label, value]) => <div className="consensusRow" key={label}><div><span>{label}</span><b>{Number(value) || 0}</b></div><i><em style={{ width: `${total ? Math.min(100, (Number(value) || 0) / total * 100) : 0}%` }} /></i></div>)}</div>
      <div className="targetStats"><div><span>Mediaan</span><b>{r.analyst_target_median != null ? money(r.analyst_target_median) : '—'}</b></div><div><span>Laagste</span><b>{r.analyst_target_low != null ? money(r.analyst_target_low) : '—'}</b></div><div><span>Hoogste</span><b>{r.analyst_target_high != null ? money(r.analyst_target_high) : '—'}</b></div></div>
      {firms.length > 0 && <div className="bankTargets"><div className="sectionEyebrow">KOERSDOELEN PER ANALIST / BANK</div>{firms.map((f, i) => <div className="bankTarget" key={`${f.name || 'firm'}-${i}`}><span>{f.name || f.firm || f.company || 'Analist'}</span><b>{money(f.target ?? f.price_target ?? f.target_price ?? f.mean)}</b></div>)}</div>}
    </div>
  </div>;
}

function OpportunityAnalysis({ r }) {
  const reasons = Array.isArray(r.reasons) ? r.reasons : [];
  const warnings = Array.isArray(r.warnings) ? r.warnings : [];
  const catalyst = r.catalyst_description;
  const plan = r.trading_plan || {};
  return <div className="aiAnalysis">
    <div className="analysisGrid">
      <div><span>WAAROM NU?</span>{reasons.length ? <ul>{reasons.slice(0, 6).map((x, i) => <li key={i}>{x}</li>)}</ul> : <p>Geen dominante positieve signalen beschikbaar.</p>}</div>
      <div><span>TECHNISCHE SETUP</span><p>{r.setup_type || 'Geen setup beschikbaar'}. Reversal-confirmatie: <b>{pct(r.reversal_confirmation)}</b>. RSI 14: <b>{n(r.rsi_14, 1)}</b>. 5D beweging: <b>{signed(r.return_5d)}</b>. Volume: <b>{n(r.volume_ratio, 2)}x</b>.</p></div>
      <div><span>FUNDAMENTALS</span><p>Omzetgroei <b>{pct(r.revenue_growth)}</b>, EPS-groei <b>{pct(r.eps_growth)}</b>, FCF <b>{r.fcf == null ? '—' : money(r.fcf / 1e9, 2) + 'B'}</b>, ROE <b>{pct(r.roe)}</b> en Debt/Equity <b>{n(r.debt_equity, 2)}</b>.</p></div>
      <div><span>ANALISTENBEVESTIGING</span><p>{r.analyst_recommendation || 'Geen consensus beschikbaar'}. Gemiddeld koersdoel <b>{r.analyst_target_mean != null ? money(r.analyst_target_mean) : '—'}</b>, upside <b>{r.analyst_target_upside != null ? signed(r.analyst_target_upside) : '—'}</b>.</p></div>
      <div><span>KATALYSATOR / TIMING</span><p>{catalyst || 'Geen specifieke katalysator uit de beschikbare data.'}{r.catalyst_nearest_days != null ? ` (${r.catalyst_nearest_days} dagen)` : ''}</p></div>
      <div><span>RENDEMENTSPOTENTIEEL</span><p>{r.expected_return != null ? `Verwachte upside: ${signed(r.expected_return)}.` : 'Geen onafhankelijk koersdoel beschikbaar.'} {r.qualifying_paths?.length ? `Gekwalificeerd pad: ${pathName(r.qualifying_paths[0])}.` : 'Geen return-pad voldoet aan alle voorwaarden.'}</p></div>
      <div><span>BELANGRIJKSTE RISICO</span><p>{warnings.length ? warnings[0] : 'Geen aanvullende engine-waarschuwing. De score blijft afhankelijk van de kwaliteit en actualiteit van de onderliggende data.'}</p></div>
      <div><span>HANDELSPLAN</span><p>Entry <b>{money(plan.entry_low)} – {money(plan.entry_high)}</b>. Add <b>{money(plan.add_low)} – {money(plan.add_high)}</b>. Invalidation <b>{money(plan.invalidation)}</b>. TP1 <b>{money(plan.tp1)}</b>. TP2 <b>{money(plan.tp2)}</b>.</p></div>
    </div>
    <div className="analysisVerdict"><span>MIJN OORDEEL</span><strong>{r.action || 'NONE'} · {r.score_label || '—'}</strong><p>Opportunity Score {n(r.opportunity_score, 1)}/100 met {r.confidence != null ? `${n(Number(r.confidence) / 10, 1)}/10 confidence` : 'onbekende confidence'} en {r.risk_reward != null ? `${n(r.risk_reward, 1)} : 1 risk/reward` : 'geen betrouwbare risk/reward-berekening'}.</p></div>
  </div>;
}

function Detail({ r, close }) {
  const plan = r.trading_plan || {};
  const scenarios = Array.isArray(r.scenarios) ? r.scenarios : [];
  const paths = r.qualifying_paths || [];
  return <div className="modalBackdrop" onClick={close}><div className="detailPanel detailPanelOpportunity" onClick={e => e.stopPropagation()}>
    <div className="detailTop"><div><span className="eyebrow">STOCK OPPORTUNITY</span><h2>{r.ticker}: <span className="detailBuy">{r.action}</span></h2><div className="detailTicker">{r.company_name || r.ticker} · {money(r.price)}</div></div><button className="closeBtn" onClick={close}><X size={18} /></button></div>
    <div className="detailScore"><div><span>OPPORTUNITY SCORE</span><strong>{n(r.opportunity_score, 1)}<small>/100</small></strong></div><Action v={r.action} /></div>
    <div className="opportunitySummaryGrid"><div><span>SETUP</span><strong>{r.setup_type || '—'}</strong></div><div><span>CONFIDENCE</span><strong>{r.confidence != null ? `${n(Number(r.confidence) / 10, 1)}/10` : '—'}</strong></div><div><span>RISK / REWARD</span><strong>{r.risk_reward != null ? `${n(r.risk_reward, 1)} : 1` : '—'}</strong></div><div><span>EXPECTED RETURN</span><strong>{r.expected_return != null ? signed(r.expected_return) : '—'}</strong></div></div>
    <div className="detailSection"><div className="sectionEyebrow">AI OPPORTUNITY ANALYSIS</div><OpportunityAnalysis r={r} /></div>
    <div className="detailSection"><div className="sectionEyebrow">ANALISTENCONSENSUS</div><Analyst r={r} /></div>
    <div className="detailSection"><div className="sectionEyebrow">OPPORTUNITY COMPONENTS</div><Components r={r} /></div>
    <div className="detailSection"><div className="sectionEyebrow">RENDEMENTSPADEN</div><div className="pathList">{scenarios.length ? scenarios.map(s => <div className={`pathRow ${paths.includes(s.name) ? 'qualified' : ''}`} key={s.name}><div><strong>{pathName(s.name)}</strong><small>{n(Number(s.probability || 0) * 100)}% kans · {s.horizon_days} dagen</small></div><b>{signed(s.return_pct)}</b></div>) : <span>Geen betrouwbaar return-pad beschikbaar.</span>}</div></div>
    <div className="detailSection"><div className="sectionEyebrow">HANDELSPLAN</div><div className="tradePlanGrid"><div><span>ENTRY</span><b>{money(plan.entry_low)} – {money(plan.entry_high)}</b></div><div><span>ADD</span><b>{money(plan.add_low)} – {money(plan.add_high)}</b></div><div><span>INVALIDATION</span><b>{money(plan.invalidation)}</b></div><div><span>TP1</span><b>{money(plan.tp1)}</b></div><div><span>TP2</span><b>{money(plan.tp2)}</b></div></div></div>
    <div className="detailSection"><div className="sectionEyebrow">TECHNISCHE DATA</div><div className="detailGrid"><div><span>RSI 14</span><b>{n(r.rsi_14, 1)}</b></div><div><span>1D</span><b>{signed(r.return_1d)}</b></div><div><span>5D</span><b>{signed(r.return_5d)}</b></div><div><span>20D</span><b>{signed(r.return_20d)}</b></div><div><span>Volume</span><b>{n(r.volume_ratio, 2)}x</b></div><div><span>Reversal</span><b>{pct(r.reversal_confirmation)}</b></div></div></div>
  </div></div>;
}

function Sidebar({ alerts, opps }) {
  return <aside className="sidebar"><div className="sideBrand"><div className="brandMark"><Activity size={18} /></div><div><b>MARKET<span>INTEL</span></b><small>OPPORTUNITY SCANNER</small></div></div><nav><div className="navLabel">WORKSPACE</div><Link href="/" className="navItem active"><LayoutDashboard size={16} />Scanner</Link><Link href="/history" className="navItem"><History size={16} />Alert history</Link><Link href="/performance" className="navItem"><TrendingUp size={16} />Performance</Link><Link href="/validation" className="navItem"><Target size={16} />Model validation</Link></nav><div className="sideBottom"><div className="liveStatus"><span className="liveDot" />MARKTSCANNER ACTIEF</div><div className="sideStat"><span>BUY ALERTS</span><strong>{alerts.length}</strong></div><div className="sideStat"><span>TOP OPPORTUNITIES</span><strong>{opps.length}</strong></div></div></aside>;
}

export default function Home() {
  const [data, setData] = useState(null), [loading, setLoading] = useState(true), [error, setError] = useState(''), [query, setQuery] = useState(''), [showAll, setShowAll] = useState(false), [selected, setSelected] = useState(null), [scanMessage, setScanMessage] = useState('');
  async function load() { setError(''); try { const response = await fetch('/api/scan?ts=' + Date.now(), { cache: 'no-store' }); const body = await response.json(); if (!response.ok) throw Error(body.error || 'Scan data niet beschikbaar.'); setData(body); } catch (e) { setError(e.message); } finally { setLoading(false); } }
  async function scan() {
    if (loading) return;
    const previous = data?.scan_version || data?.generated_at || '';
    setLoading(true); setError(''); setScanMessage('Nieuwe scan wordt gestart...');
    try {
      const trigger = await fetch('/api/trigger-scan', { method: 'POST' });
      const triggerBody = await trigger.json().catch(() => ({}));
      if (!trigger.ok) throw Error(triggerBody.error || 'De scan kon niet worden gestart.');
      const started = Date.now();
      while (Date.now() - started < 10 * 60 * 1000) {
        await new Promise(resolve => setTimeout(resolve, 10000));
        const response = await fetch('/api/scan?ts=' + Date.now(), { cache: 'no-store' });
        if (!response.ok) continue;
        const body = await response.json();
        const version = body?.scan_version || body?.generated_at || '';
        if (version && version !== previous) { setData(body); setScanMessage('Nieuwe scan voltooid.'); return; }
        setScanMessage('Scan draait... data wordt opnieuw berekend.');
      }
      throw Error('De scan duurt langer dan verwacht.');
    } catch (e) { setError(e.message); setScanMessage(''); } finally { setLoading(false); }
  }
  useEffect(() => { load(); }, []);
  const all = data?.results || [];
  const alerts = useMemo(() => all.filter(r => r.action === 'BUY').sort((a, b) => Number(b.opportunity_score) - Number(a.opportunity_score)), [all]);
  const opps = useMemo(() => all.filter(r => !['BUY', 'EXIT', 'NONE'].includes(r.action)).sort((a, b) => Number(b.opportunity_score) - Number(a.opportunity_score)).slice(0, 10), [all]);
  const filtered = useMemo(() => all.filter(r => !query || `${r.ticker} ${r.company_name || ''}`.toLowerCase().includes(query.toLowerCase())).sort((a, b) => Number(b.opportunity_score) - Number(a.opportunity_score)), [all, query]);
  const visible = showAll ? filtered : filtered.slice(0, 25);
  const top = alerts[0] || opps[0];
  const avg = all.length ? all.reduce((s, r) => s + Number(r.opportunity_score || 0), 0) / all.length : 0;
  const scored = all.filter(r => Number.isFinite(Number(r.opportunity_score))).length;

  return <div className="appShell"><Sidebar alerts={alerts} opps={opps} /><main className="dashboard">
    <header className="topbar"><div><div className="eyebrow">MARKET INTELLIGENCE / LIVE SCANNER</div><h1>Opportunity scanner</h1><p>Alle aandelen worden beoordeeld met één Opportunity Engine.</p></div><div className="topActions"><div className="scanMeta"><span className="liveDot" /> LIVE DATA <b>{data?.generated_at ? new Date(data.generated_at).toLocaleTimeString('nl-NL', { hour: '2-digit', minute: '2-digit' }) : '—'}</b></div><Link href="/history" className="refresh secondary"><History size={15} />Historie</Link><button className="refresh primary" onClick={scan} disabled={loading}><RefreshCw size={15} />{loading ? 'Laden...' : 'Nieuwe scan'}</button></div></header>
    {scanMessage && <div className="scanNotice">{scanMessage}</div>}{error && <div className="error">{error}</div>}
    <section className="heroGrid"><div className="heroPanel"><div><span className="sectionEyebrow">SCANNER OVERVIEW</span><h2>Vandaag in de markt</h2><p>Rangschikking op Opportunity Score, setup en actie.</p></div><div className="heroStats"><div><span>MARKTUNIVERSE</span><strong>{data?.universe_size ?? all.length}</strong><small>bedrijven</small></div><div><span>GEM. OPPORTUNITY SCORE</span><strong>{n(avg)}</strong><small>/100</small></div><div><span>GESCOREDE AANDELEN</span><strong>{scored}</strong><small>van {all.length}</small></div></div></div><div className="heroSignal"><div className="signalHeader"><span>TOP OPPORTUNITY</span><Target size={15} /></div><div className="convictionBody"><Ring v={top?.opportunity_score || 0} /><div><strong>{top?.ticker || '—'}</strong><span>{top?.company_name || 'Geen kandidaat'}</span><small>{top?.action === 'BUY' ? 'Actieve BUY alert' : 'Hoogste opportunity'}</small></div></div></div></section>
    <section className="kpiGrid"><div className={`kpiCard ${alerts.length ? 'hot' : ''}`}><div className="kpiIcon"><Bell size={17} /></div><div><span>BUY ALERTS</span><strong>{alerts.length}</strong><small>action BUY</small></div><ChevronRight size={15} /></div><div className="kpiCard"><div className="kpiIcon blue"><TrendingUp size={17} /></div><div><span>TOP OPPORTUNITIES</span><strong>{opps.length}</strong><small>hoogste 10 zonder BUY</small></div><ChevronRight size={15} /></div><div className="kpiCard"><div className="kpiIcon"><Database size={17} /></div><div><span>UNIVERSE</span><strong>{data?.universe_size ?? all.length}</strong><small>vaste lijst</small></div><ChevronRight size={15} /></div><div className="kpiCard"><div className="kpiIcon purple"><Activity size={17} /></div><div><span>LAATSTE SCAN</span><strong>{data?.generated_at ? new Date(data.generated_at).toLocaleTimeString('nl-NL', { hour: '2-digit', minute: '2-digit' }) : '—'}</strong><small>{data?.generated_at ? new Date(data.generated_at).toLocaleDateString('nl-NL') : ''}</small></div><ChevronRight size={15} /></div></section>
    <section className="sectionBlock"><div className="sectionHeader"><div><div className="sectionEyebrow">01 · ACTION CENTER</div><h2>Actieve BUY alerts</h2><p>Alleen action BUY uit de Opportunity Engine.</p></div><div className="statusPill live"><Bell size={13} />{alerts.length} actief</div></div>{alerts.length ? <div className="alertCards">{alerts.map(r => { const plan = r.trading_plan || {}; return <button className="alertCard cardButton" key={r.ticker} onClick={() => setSelected(r)}><div className="alertGlow" /><div className="cardTop"><div><span className="tickerBig">{r.ticker}</span><span className="companyName">{r.company_name}</span></div><Ring v={r.opportunity_score} /></div><div className="priceLine">{money(r.price)} <Action v="BUY" /></div><div className="alertMetaGrid"><div><span>SETUP</span><b>{r.setup_type || '—'}</b></div><div><span>CONFIDENCE</span><b>{r.confidence != null ? `${n(Number(r.confidence) / 10, 1)}/10` : '—'}</b></div><div><span>RISK / REWARD</span><b>{r.risk_reward != null ? `${n(r.risk_reward, 1)} : 1` : '—'}</b></div></div><div className="returnPath"><span>RENDEMENTSPAD</span><strong>{r.qualifying_paths?.length ? pathName(r.qualifying_paths[0]) : 'Geen gekwalificeerd pad'}</strong></div><div className="why"><span>WAAROM NU?</span><div>{(r.reasons || []).slice(0, 5).map((x, i) => <span key={i}>{x}</span>)}</div></div><div className="tradePlanGrid compact"><div><span>ENTRY</span><b>{money(plan.entry_low)} – {money(plan.entry_high)}</b></div><div><span>ADD</span><b>{money(plan.add_low)} – {money(plan.add_high)}</b></div><div><span>INVALIDATION</span><b>{money(plan.invalidation)}</b></div><div><span>TP1</span><b>{money(plan.tp1)}</b></div><div><span>TP2</span><b>{money(plan.tp2)}</b></div></div></button>; })}</div> : <div className="emptyState alertEmpty"><strong>Geen actieve BUY alerts</strong><span>Geen aandeel voldoet momenteel aan alle BUY-voorwaarden.</span></div>}</section>
    <section className="sectionBlock"><div className="sectionHeader"><div><div className="sectionEyebrow">02 · RESEARCH</div><h2>Top opportunities</h2><p>De 10 hoogste Opportunity Scores zonder BUY alert.</p></div><div className="statusPill"><TrendingUp size={13} />10 hoogste</div></div><div className="opportunityGrid">{opps.map((r, i) => <button className="opportunityButton" key={r.ticker} onClick={() => setSelected(r)}><div className="opportunityCard"><div className="oppRank">{String(i + 1).padStart(2, '0')}</div><div className="oppIdentity"><b>{r.ticker}</b><span>{r.company_name}</span></div><Action v={r.action} /><div className="oppScore"><Ring v={r.opportunity_score} size="medium" /><strong>{n(r.opportunity_score, 1)}</strong><small>/100</small></div><div className="oppMeta"><span>SETUP <b>{r.setup_type || '—'}</b></span><span>CONFIDENCE <b>{r.confidence != null ? n(Number(r.confidence) / 10, 1) : '—'}</b></span><span>R / R <b>{r.risk_reward != null ? n(r.risk_reward, 1) : '—'}</b></span></div></div></button>)}</div></section>
    <section className="sectionBlock"><div className="sectionHeader"><div><div className="sectionEyebrow">03 · MARKET UNIVERSE</div><h2>Alle gescande bedrijven</h2><p>Gesorteerd op Opportunity Score en actie.</p></div><div className="searchBox"><Search size={14} /><input value={query} onChange={e => setQuery(e.target.value)} placeholder="Zoek ticker of bedrijf" /></div></div><div className="universeTable"><div className="tableHead"><span>TICKER</span><span>ACTION</span><span>OPPORTUNITY</span><span>SETUP</span><span>TECHNICAL</span><span>ANALYSTS</span><span>KOERS</span></div>{visible.map(r => <div className="tableRow tableRowStatic" key={r.ticker}><span><b>{r.ticker}</b><small>{r.company_name}</small></span><span><Action v={r.action} /></span><span><strong>{n(r.opportunity_score, 1)}</strong></span><span>{r.setup_type || '—'}</span><span>{n(r.opportunity_technical_score)}</span><span>{n(r.opportunity_analysts_score)}</span><span>{money(r.price)}</span></div>)}</div>{filtered.length > 25 && <div className="tableFooter"><button className="refresh secondary" onClick={() => setShowAll(v => !v)}>{showAll ? 'Toon alleen top 25' : 'Toon volledige lijst'}<ChevronRight size={14} /></button><span>{showAll ? `${filtered.length} bedrijven zichtbaar` : `25 van ${filtered.length} bedrijven zichtbaar`}</span></div>}</section>
  </main>{selected && <Detail r={selected} close={() => setSelected(null)} />}</div>;
}
