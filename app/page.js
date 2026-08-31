'use client';

import { useEffect, useMemo, useState } from 'react';
import { RefreshCw, Bell, Search, Activity, ArrowUpRight, Eye, Database } from 'lucide-react';

function pct(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—';
  return `${(Number(value) * 100).toFixed(1)}%`;
}
function score(value) {
  return value === null || value === undefined || Number.isNaN(Number(value)) ? '—' : Number(value).toFixed(0);
}
function num(value, digits = 1) {
  return value === null || value === undefined || Number.isNaN(Number(value)) ? '—' : Number(value).toFixed(digits);
}
function reasons(row) {
  const out = [];
  if (Number(row.trader_similarity_score) >= 90) out.push('Sterke trader-match');
  if (Number(row.rsi_14) < 30) out.push(`RSI ${num(row.rsi_14)} oversold`);
  if (Number(row.return_5d) <= -0.10) out.push(`${pct(row.return_5d)} in 5 dagen`);
  if (Number(row.distance_52w_high) <= -0.20) out.push(`${pct(row.distance_52w_high)} onder 52w high`);
  if (Number(row.volume_ratio) >= 1.5) out.push(`${num(row.volume_ratio)}x normaal volume`);
  if (Number(row.macd_histogram_change) > 0) out.push('MACD verbetert');
  return out.slice(0, 4);
}

export default function Home() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');
  const [showAll, setShowAll] = useState(false);

  async function load() {
    setLoading(true); setError('');
    try {
      const res = await fetch('/data/latest_scan.json?ts=' + Date.now(), { cache: 'no-store' });
      if (!res.ok) throw new Error('Latest scan is niet beschikbaar.');
      setData(await res.json());
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  }
  useEffect(() => { load(); }, []);

  const all = data?.results || [];
  const alerts = useMemo(() => all.filter(r => r.signal === 'ALERT').sort((a,b) => Number(b.overall_score)-Number(a.overall_score)), [all]);
  const opportunities = useMemo(() => all.filter(r => r.signal !== 'ALERT').sort((a,b) => Number(b.overall_score)-Number(a.overall_score)).slice(0, 10), [all]);
  const filtered = useMemo(() => all.filter(r => !query || `${r.ticker} ${r.company_name || ''}`.toLowerCase().includes(query.toLowerCase())).sort((a,b) => Number(b.overall_score)-Number(a.overall_score)), [all, query]);

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <div className="eyebrow">TRADER PATTERN SCANNER</div>
          <h1>Market intelligence</h1>
          <p>Een vaste selectie van interessante Amerikaanse bedrijven. De scanner zoekt naar setups die lijken op historische trades.</p>
        </div>
        <button className="refresh" onClick={load} disabled={loading}><RefreshCw size={16} className={loading ? 'spin' : ''}/> Scan opnieuw</button>
      </header>

      {error && <div className="error">{error}</div>}

      <section className="overview">
        <div className="overviewItem"><span>UNIVERSE</span><strong>{data?.universe_size ?? '—'}</strong><small>bedrijven</small></div>
        <div className={`overviewItem ${alerts.length ? 'attention' : ''}`}><span>BUY ALERTS</span><strong>{alerts.length}</strong><small>{alerts.length ? 'direct bekijken' : 'geen actief signaal'}</small></div>
        <div className="overviewItem"><span>OPPORTUNITIES</span><strong>{opportunities.length}</strong><small>hoogste scores zonder alert</small></div>
        <div className="overviewItem"><span>LAATSTE SCAN</span><strong>{data?.generated_at ? new Date(data.generated_at).toLocaleTimeString('nl-NL',{hour:'2-digit',minute:'2-digit'}) : '—'}</strong><small>{data?.generated_at ? new Date(data.generated_at).toLocaleDateString('nl-NL') : ''}</small></div>
      </section>

      <section className="sectionBlock">
        <div className="sectionHeader"><div><div className="sectionEyebrow">1 · ACTIE</div><h2>Actieve buy alerts</h2><p>Alleen aandelen die momenteel aan de ingestelde alertvoorwaarden voldoen.</p></div><div className="statusPill"><Bell size={14}/>{alerts.length} actief</div></div>
        {alerts.length === 0 ? <div className="emptyState"><Bell size={20}/><strong>Geen buy alerts</strong><span>Dat is normaal. De scanner geeft alleen een alert wanneer de combinatie sterk genoeg is.</span></div> : (
          <div className="alertCards">{alerts.map(r => <div className="alertCard" key={r.ticker}>
            <div className="cardTop"><div><span className="tickerBig">{r.ticker}</span><span className="companyName">{r.company_name}</span></div><div className="scoreLarge">{score(r.overall_score)}<small>/100</small></div></div>
            <div className="priceLine">${num(r.price,2)} <span className="signal alert">BUY ALERT</span> <span className="setupText">{r.setup_type}</span></div>
            <div className="metricRow"><div><span>TRADER MATCH</span><strong>{score(r.trader_similarity_score)}</strong></div><div><span>TECHNICAL</span><strong>{score(r.technical_opportunity_score)}</strong></div><div><span>RSI</span><strong>{num(r.rsi_14)}</strong></div><div><span>5D</span><strong className={Number(r.return_5d)<0?'negative':'positive'}>{pct(r.return_5d)}</strong></div></div>
            <div className="why"><span>WAAROM</span><div>{reasons(r).map((x,i)=><span key={i}>{x}</span>)}</div></div>
          </div>)}</div>
        )}
      </section>

      <section className="sectionBlock">
        <div className="sectionHeader"><div><div className="sectionEyebrow">2 · ONDERZOEK</div><h2>Top opportunities</h2><p>De hoogste scores die nog geen buy alert zijn. Dit zijn kandidaten om te volgen.</p></div><Eye size={19}/></div>
        <div className="opportunityGrid">{opportunities.map((r,i)=><div className="opportunity" key={r.ticker}><div className="rank">{i+1}</div><div className="oppMain"><div><strong>{r.ticker}</strong><span>{r.company_name}</span></div><span className="badge">{r.setup_type}</span></div><div className="oppScore"><strong>{score(r.overall_score)}</strong><small>/100</small></div><div className="oppStats"><span>Trader <b>{score(r.trader_similarity_score)}</b></span><span>RSI <b>{num(r.rsi_14)}</b></span><span>5D <b className={Number(r.return_5d)<0?'negative':'positive'}>{pct(r.return_5d)}</b></span></div></div>)}</div>
      </section>

      <section className="sectionBlock databaseBlock">
        <div className="sectionHeader"><div><div className="sectionEyebrow">3 · VOLLEDIGE SCAN</div><h2>Gescoorde bedrijven</h2><p>De volledige universe. Gesorteerd op huidige scanner-score.</p></div><div className="search"><Search size={15}/><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Zoek bedrijf..."/></div></div>
        <div className="tablewrap"><table><thead><tr><th>#</th><th>Bedrijf</th><th>Signaal</th><th>Score</th><th>Trader</th><th>Setup</th><th>5D</th><th>RSI</th></tr></thead><tbody>{(showAll ? filtered : filtered.slice(0,20)).map((r,i)=><tr key={r.ticker}><td className="muted">{i+1}</td><td><div className="company"><span className="ticker">{r.ticker}</span><small>{r.company_name}</small></div></td><td><span className={`signal ${String(r.signal).toLowerCase()}`}>{r.signal === 'NO_SIGNAL' ? 'NO SIGNAL' : r.signal}</span></td><td className="score">{score(r.overall_score)}</td><td>{score(r.trader_similarity_score)}</td><td><span className="badge">{r.setup_type}</span></td><td className={Number(r.return_5d)<0?'negative':'positive'}>{pct(r.return_5d)}</td><td>{num(r.rsi_14)}</td></tr>)}</tbody></table></div>
        <button className="showMore" onClick={()=>setShowAll(!showAll)}>{showAll ? 'Toon minder' : `Toon alle ${filtered.length} bedrijven`} <ArrowUpRight size={14}/></button>
      </section>

      <section className="footerInfo"><div><Database size={18}/><div><strong>Hoe je dit dashboard leest</strong><p>ALERT betekent dat de huidige combinatie sterk genoeg is voor onze ingestelde drempel. OPPORTUNITY betekent dat het aandeel hoog scoort maar nog geen alert is. De score is een onderzoeksmodel en geen garantie op rendement.</p></div></div><div><Activity size={18}/><div><strong>Volgende stap</strong><p>We voegen fundamentals toe en testen daarna historisch welke scores daadwerkelijk voorspellende waarde hebben.</p></div></div></section>
      <footer>Trader Pattern Scanner · laatste scan {data?.generated_at ? new Date(data.generated_at).toLocaleString('nl-NL') : '—'}</footer>
    </main>
  );
}
