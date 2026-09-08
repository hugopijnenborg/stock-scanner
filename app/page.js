'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { Activity, BarChart3, Bell, ChevronRight, Database, History, LayoutDashboard, RefreshCw, Search, Target, TrendingUp, X } from 'lucide-react';

const num = (v, d = 1) => v == null || !Number.isFinite(Number(v)) ? '—' : Number(v).toFixed(d);
const pct = v => v == null || !Number.isFinite(Number(v)) ? '—' : `${(Number(v) * 100).toFixed(1)}%`;
const signed = v => v == null || !Number.isFinite(Number(v)) ? '—' : `${Number(v) >= 0 ? '+' : ''}${(Number(v) * 100).toFixed(1)}%`;
const money = v => v == null || !Number.isFinite(Number(v)) ? '—' : `$${Number(v).toLocaleString('en-US', { maximumFractionDigits: 2 })}`;
const pathName = p => ({ '25pct_1m': '+25% binnen 1 maand', '50pct_3m': '+50% binnen 3 maanden', '100pct_12m': '+100% binnen 12 maanden' }[p] || p || '—');
const actionClass = a => String(a || 'NONE').toLowerCase().replaceAll(' ', '-');

function Action({ value }) { return <span className={`miAction miAction-${actionClass(value)}`}>{value || 'NONE'}</span>; }
function ScoreRing({ value, large = false }) { const score = Math.max(0, Math.min(100, Number(value) || 0)); return <div className={`miRing ${large ? 'large' : ''}`} style={{ '--score-angle': `${score * 3.6}deg` }}><div><strong>{num(score)}</strong><small>/100</small></div></div>; }

const componentMeta = [
  ['technical', 'Technical'], ['fundamentals', 'Fundamentals'], ['valuation', 'Valuation'], ['analysts', 'Analysts'],
  ['catalysts', 'Catalysts'], ['institutional', 'Institutional'], ['macro_sector', 'Market / sector'], ['liquidity_risk', 'Liquidity / risk'],
];

function ComponentBars({ stock }) {
  return <div className="miComponents">{componentMeta.map(([key, label]) => {
    const score = Number(stock[`opportunity_${key}_score`]);
    const weighted = Number(stock[`opportunity_${key}_weighted`]);
    return <div className="miComponent" key={key}>
      <div className="miComponentTop"><span>{label}</span><strong>{Number.isFinite(score) ? num(score) : '—'}</strong></div>
      <div className="miBar"><i style={{ width: `${Math.max(0, Math.min(100, score || 0))}%` }} /></div>
      <small>{Number.isFinite(weighted) ? `${weighted.toFixed(1)} punten van score` : 'Geen gewogen bijdrage beschikbaar'}</small>
    </div>;
  })}</div>;
}

function AnalystPanel({ stock }) {
  const rows = [['Strong Buy', stock.analyst_strong_buy], ['Buy', stock.analyst_buy], ['Hold', stock.analyst_hold], ['Sell', stock.analyst_sell], ['Strong Sell', stock.analyst_strong_sell]];
  const total = rows.reduce((sum, [, value]) => sum + (Number(value) || 0), 0) || Number(stock.analyst_count) || 0;
  let firms = stock.analyst_firm_targets;
  if (typeof firms === 'string') { try { firms = JSON.parse(firms); } catch { firms = []; } }
  if (!Array.isArray(firms)) firms = firms && typeof firms === 'object' ? Object.entries(firms).map(([name, target]) => ({ name, target })) : [];
  return <div className="miAnalystPanel">
    <div className="miAnalystHero">
      <div><span>CONSENSUS</span><strong>{stock.analyst_recommendation || 'Niet beschikbaar'}</strong><small>{total || 'Geen'} beoordelingen</small></div>
      <div className="miTarget"><span>GEMIDDELD KOERSDOEL</span><strong>{money(stock.analyst_target_mean)}</strong><small>{stock.analyst_target_upside != null ? signed(stock.analyst_target_upside) : 'Geen target-upside'}</small></div>
    </div>
    <div className="miAnalystGrid">
      <div className="miDistribution">{rows.map(([label, value]) => <div key={label}><div><span>{label}</span><b>{Number(value) || 0}</b></div><div className="miBar"><i style={{ width: `${total ? Math.min(100, (Number(value) || 0) / total * 100) : 0}%` }} /></div></div>)}</div>
      <div className="miTargetStats"><div><span>Mediaan</span><strong>{money(stock.analyst_target_median)}</strong></div><div><span>Laagste</span><strong>{money(stock.analyst_target_low)}</strong></div><div><span>Hoogste</span><strong>{money(stock.analyst_target_high)}</strong></div></div>
    </div>
    {firms.length > 0 && <div className="miFirmTargets"><div className="miMiniLabel">KOERSDOELEN PER ANALIST / BANK</div>{firms.slice(0, 12).map((firm, i) => <div key={`${firm.firm || firm.name || 'firm'}-${i}`}><span>{firm.firm || firm.name || firm.company || 'Analist'}</span><strong>{money(firm.target ?? firm.price_target ?? firm.target_price ?? firm.mean)}</strong></div>)}</div>}
  </div>;
}

function WhyScore({ stock }) {
  const rows = [
    ['Technical', stock.opportunity_technical_score, 'Dislocation, exhaustion en reversal'],
    ['Fundamentals', stock.opportunity_fundamentals_score, 'Groei, kwaliteit, FCF en balans'],
    ['Valuation', stock.opportunity_valuation_score, 'P/E, forward P/E en PEG versus waarde'],
    ['Analysts', stock.opportunity_analysts_score, 'Consensus, target en revisies'],
  ];
  return <div className="miScoreReason"><div className="miMiniLabel">WAAROM DEZE SCORE?</div>{rows.map(([label, value, text]) => <div className="miReasonRow" key={label}><div><strong>{label}</strong><span>{text}</span></div><b>{num(value)}</b></div>)}<p>De overige 20% van de score komt uit catalysts, institutional, market / sector en liquidity / risk.</p></div>;
}

function OpportunityCard({ stock, rank, onOpen }) {
  return <button className="miOpportunityCard" onClick={() => onOpen(stock)}>
    <div className="miCardTop"><span className="miRank">{String(rank).padStart(2, '0')}</span><Action value={stock.action} /><ScoreRing value={stock.opportunity_score} /></div>
    <div className="miIdentity"><strong>{stock.ticker}</strong><span>{stock.company_name || stock.ticker}</span></div>
    <div className="miCardSetup"><span>SETUP</span><strong>{stock.setup_type || '—'}</strong></div>
    <div className="miCardStats"><div><span>CONFIDENCE</span><strong>{stock.confidence != null ? `${(Number(stock.confidence) / 10).toFixed(1)}/10` : '—'}</strong></div><div><span>RISK / REWARD</span><strong>{stock.risk_reward != null ? `${num(stock.risk_reward)} : 1` : '—'}</strong></div><div><span>KOERS</span><strong>{money(stock.price)}</strong></div></div>
    <div className="miCardBottom"><span>Technical <b>{num(stock.opportunity_technical_score)}</b></span><span>Fundamentals <b>{num(stock.opportunity_fundamentals_score)}</b></span><span>Analysts <b>{num(stock.opportunity_analysts_score)}</b></span><ChevronRight size={18} /></div>
  </button>;
}

function Detail({ stock, close }) {
  const plan = stock.trading_plan || {};
  const scenarios = Array.isArray(stock.scenarios) ? stock.scenarios : [];
  const paths = stock.qualifying_paths || [];
  const reasons = Array.isArray(stock.reasons) ? stock.reasons : [];
  const warnings = Array.isArray(stock.warnings) ? stock.warnings : [];
  return <div className="miModal" onClick={close}><div className="miDetail" onClick={e => e.stopPropagation()}>
    <header className="miDetailHeader"><div><span className="miEyebrow">STOCK OPPORTUNITY</span><h2>{stock.ticker}</h2><p>{stock.company_name || stock.ticker} · {money(stock.price)}</p></div><button onClick={close} aria-label="Sluiten"><X size={20} /></button></header>
    <div className="miDetailScore"><div><span>OPPORTUNITY SCORE</span><strong>{num(stock.opportunity_score)}<small>/100</small></strong></div><Action value={stock.action} /></div>
    <div className="miDetailFacts"><div><span>SETUP</span><strong>{stock.setup_type || '—'}</strong></div><div><span>CONFIDENCE</span><strong>{stock.confidence != null ? `${(Number(stock.confidence) / 10).toFixed(1)}/10` : '—'}</strong></div><div><span>RISK / REWARD</span><strong>{stock.risk_reward != null ? `${num(stock.risk_reward)} : 1` : '—'}</strong></div><div><span>EXPECTED RETURN</span><strong>{signed(stock.expected_return)}</strong></div></div>

    <section><div className="miSectionTitle">AI OPPORTUNITY ANALYSIS</div><div className="miAnalysis"><div><span>WAAROM NU?</span>{reasons.length ? <ul>{reasons.slice(0, 6).map((reason, i) => <li key={i}>{reason}</li>)}</ul> : <p>Geen dominante positieve signalen beschikbaar.</p>}</div><div><span>TECHNISCHE SETUP</span><p>{stock.setup_type || 'Geen setup'}. Reversal <b>{pct(stock.reversal_confirmation)}</b>, RSI 14 <b>{num(stock.rsi_14)}</b>, 5D <b>{signed(stock.return_5d)}</b> en volume <b>{num(stock.volume_ratio, 2)}x</b>.</p></div><div><span>FUNDAMENTALS</span><p>Omzetgroei <b>{pct(stock.revenue_growth)}</b>, EPS-groei <b>{pct(stock.eps_growth)}</b>, ROE <b>{pct(stock.roe)}</b> en Debt/Equity <b>{num(stock.debt_equity, 2)}</b>.</p></div><div><span>ANALISTEN</span><p>{stock.analyst_recommendation || 'Geen consensus'}. Gemiddeld target <b>{money(stock.analyst_target_mean)}</b>, upside <b>{signed(stock.analyst_target_upside)}</b>.</p></div><div><span>KATALYSATOR / TIMING</span><p>{stock.catalyst_description || 'Geen specifieke katalysator uit de beschikbare data.'}{stock.catalyst_nearest_days != null ? ` · ${stock.catalyst_nearest_days} dagen` : ''}</p></div><div><span>RETURN-POTENTIEEL</span><p>{stock.expected_return != null ? `Analistentarget impliceert ${signed(stock.expected_return)} upside.` : 'Geen betrouwbaar target beschikbaar.'} {paths.length ? `Gekwalificeerd: ${pathName(paths[0])}.` : 'Geen return-pad voldoet aan de voorwaarden.'}</p></div><div><span>BELANGRIJKSTE RISICO</span><p>{warnings[0] || 'Geen aanvullende engine-waarschuwing.'}</p></div><div><span>MIJN OORDEEL</span><p><b>{stock.action || 'NONE'} · {stock.score_label || '—'}</b>. De score is gebaseerd op acht gewogen componenten en niet op één losse indicator.</p></div></div></section>

    <section><div className="miSectionTitle">WAAROM DE SCORE {num(stock.opportunity_score)} IS</div><WhyScore stock={stock}/><ComponentBars stock={stock}/></section>
    <section><div className="miSectionTitle">ANALISTENCONSENSUS</div><AnalystPanel stock={stock}/></section>
    <section><div className="miSectionTitle">RENDEMENTSPADEN</div><div className="miPaths">{scenarios.length ? scenarios.map(s => <div className={paths.includes(s.name) ? 'qualified' : ''} key={s.name}><div><strong>{pathName(s.name)}</strong><span>{(Number(s.probability || 0) * 100).toFixed(0)}% kans · {s.horizon_days} dagen</span></div><b>{signed(s.return_pct)}</b></div>) : <p>Geen betrouwbaar return-pad beschikbaar.</p>}</div></section>
    <section><div className="miSectionTitle">HANDELSPLAN</div><div className="miPlan"><div><span>ENTRY</span><strong>{money(plan.entry_low)} – {money(plan.entry_high)}</strong></div><div><span>ADD</span><strong>{money(plan.add_low)} – {money(plan.add_high)}</strong></div><div><span>INVALIDATION</span><strong>{money(plan.invalidation)}</strong></div><div><span>TP1</span><strong>{money(plan.tp1)}</strong></div><div><span>TP2</span><strong>{money(plan.tp2)}</strong></div></div></section>
  </div></div>;
}

function Sidebar({ alerts, opps }) { return <aside className="miSidebar"><div className="miBrand"><div className="miBrandMark"><Activity size={19}/></div><div><strong>MARKET<span>INTEL</span></strong><small>OPPORTUNITY SCANNER</small></div></div><nav><span>WORKSPACE</span><Link href="/" className="active"><LayoutDashboard size={16}/>Scanner</Link><Link href="/history"><History size={16}/>Alert history</Link><Link href="/performance"><TrendingUp size={16}/>Performance</Link><Link href="/validation"><Target size={16}/>Model validation</Link></nav><div className="miSideBottom"><div className="miLive"><i/>MARKTSCANNER ACTIEF</div><div><span>BUY ALERTS</span><strong>{alerts.length}</strong></div><div><span>TOP OPPORTUNITIES</span><strong>{opps.length}</strong></div></div></aside>; }

export default function Home() {
  const [data, setData] = useState(null), [loading, setLoading] = useState(true), [error, setError] = useState(''), [query, setQuery] = useState(''), [showAll, setShowAll] = useState(false), [selected, setSelected] = useState(null), [scanMessage, setScanMessage] = useState('');
  async function load(){setError('');try{const response=await fetch('/api/scan?ts='+Date.now(),{cache:'no-store'});const body=await response.json();if(!response.ok)throw Error(body.error||'Scan data niet beschikbaar.');setData(body);}catch(e){setError(e.message);}finally{setLoading(false);}}
  async function scan(){if(loading)return;const previous=data?.scan_version||data?.generated_at||'';setLoading(true);setError('');setScanMessage('Nieuwe scan wordt gestart...');try{const trigger=await fetch('/api/trigger-scan',{method:'POST'});const triggerBody=await trigger.json().catch(()=>({}));if(!trigger.ok)throw Error(triggerBody.error||'De scan kon niet worden gestart.');const started=Date.now();while(Date.now()-started<10*60*1000){await new Promise(r=>setTimeout(r,10000));const response=await fetch('/api/scan?ts='+Date.now(),{cache:'no-store'});if(!response.ok)continue;const body=await response.json();const version=body?.scan_version||body?.generated_at||'';if(version&&version!==previous){setData(body);setScanMessage('Nieuwe scan voltooid.');return;}setScanMessage('Scan draait... data wordt opnieuw berekend.');}throw Error('De scan duurt langer dan verwacht.');}catch(e){setError(e.message);setScanMessage('');}finally{setLoading(false);}}
  useEffect(()=>{load();},[]);
  const all=data?.results||[];
  const alerts=useMemo(()=>all.filter(r=>r.action==='BUY').sort((a,b)=>Number(b.opportunity_score)-Number(a.opportunity_score)),[all]);
  const opps=useMemo(()=>all.filter(r=>!['BUY','EXIT'].includes(r.action)).sort((a,b)=>Number(b.opportunity_score)-Number(a.opportunity_score)).slice(0,10),[all]);
  const filtered=useMemo(()=>all.filter(r=>!query||`${r.ticker} ${r.company_name||''}`.toLowerCase().includes(query.toLowerCase())).sort((a,b)=>Number(b.opportunity_score)-Number(a.opportunity_score)),[all,query]);
  const visible=showAll?filtered:filtered.slice(0,25);
  return <div className="miShell"><Sidebar alerts={alerts} opps={opps}/><main className="miMain"><header className="miTopbar"><div><span>MARKETINTEL</span><h1>Opportunity Scanner</h1><p>Alle aandelen beoordeeld met dezelfde Opportunity Engine.</p></div><div className="miTopActions"><div className="miLastScan"><span>LAATSTE SCAN</span><strong>{data?.generated_at?new Date(data.generated_at).toLocaleTimeString('nl-NL',{hour:'2-digit',minute:'2-digit'}):'—'}</strong><small>{data?.generated_at?new Date(data.generated_at).toLocaleDateString('nl-NL'):''}</small></div><button className="miScanButton" onClick={scan} disabled={loading}><RefreshCw size={16} className={loading?'spin':''}/>{loading?'Bezig...':'Nieuwe scan'}</button></div></header>
    {scanMessage&&<div className="miNotice">{scanMessage}</div>}{error&&<div className="miError">{error}</div>}
    <div className="miKpis"><div><Bell size={18}/><span>BUY ALERTS</span><strong>{alerts.length}</strong><small>actief</small></div><div><TrendingUp size={18}/><span>TOP OPPORTUNITIES</span><strong>10</strong><small>hoogste scores zonder BUY</small></div><div><Database size={18}/><span>MARKET UNIVERSE</span><strong>{data?.universe_size||all.length}</strong><small>aandelen</small></div><div><BarChart3 size={18}/><span>HOOGSTE SCORE</span><strong>{num(data?.top_score)}</strong><small>Opportunity Score</small></div></div>

    <section className="miSection"><div className="miSectionHead"><div><span>01 · ACTION CENTER</span><h2>Actieve BUY alerts</h2><p>Alleen aandelen die aan alle harde BUY-voorwaarden voldoen.</p></div><div className="miAlertCount"><Bell size={15}/>{alerts.length} actief</div></div>{alerts.length?<div className="miAlertList">{alerts.map(stock=><button className="miAlertRow" key={stock.ticker} onClick={()=>setSelected(stock)}><div><strong>{stock.ticker}</strong><span>{stock.company_name}</span></div><Action value={stock.action}/><b>{num(stock.opportunity_score)}</b><ChevronRight size={18}/></button>)}</div>:<div className="miEmpty"><strong>Geen actieve BUY alerts</strong><span>Geen aandeel voldoet momenteel aan alle BUY-voorwaarden van de Opportunity Engine.</span></div>}</section>

    <section className="miSection"><div className="miSectionHead"><div><span>02 · RESEARCH</span><h2>Top opportunities</h2><p>De 10 hoogste Opportunity Scores zonder BUY of EXIT.</p></div><div className="miPill">10 hoogste</div></div><div className="miOpportunityGrid">{opps.map((stock,i)=><OpportunityCard key={stock.ticker} stock={stock} rank={i+1} onOpen={setSelected}/>)}</div></section>

    <section className="miSection miUniverse"><div className="miSectionHead"><div><span>03 · MARKET UNIVERSE</span><h2>Alle gescande bedrijven</h2><p>Gesorteerd op Opportunity Score en actie.</p></div><label className="miSearch"><Search size={16}/><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Zoek ticker of bedrijf"/></label></div><div className="miTable"><div className="miTableHead"><span>TICKER</span><span>ACTION</span><span>SCORE</span><span>SETUP</span><span>TECHNICAL</span><span>ANALYSTS</span><span>KOERS</span></div>{visible.map(stock=><button className="miTableRow" key={stock.ticker} onClick={()=>setSelected(stock)}><span><strong>{stock.ticker}</strong><small>{stock.company_name||stock.ticker}</small></span><Action value={stock.action}/><strong className="miScoreText">{num(stock.opportunity_score)}</strong><span className="miSetup">{stock.setup_type||'—'}</span><span>{num(stock.opportunity_technical_score)}</span><span>{num(stock.opportunity_analysts_score)}</span><span>{money(stock.price)}</span></button>)}</div>{filtered.length>25&&<button className="miExpand" onClick={()=>setShowAll(v=>!v)}>{showAll?'Toon minder':`Toon alle ${filtered.length} bedrijven`}</button>}</section>
    <footer className="miFooter">Opportunity Engine v{data?.engine_version||3} · {data?.generated_at?'Data '+new Date(data.generated_at).toLocaleString('nl-NL'):''}</footer>
  </main>{selected&&<Detail stock={selected} close={()=>setSelected(null)}/>}</div>;
}
