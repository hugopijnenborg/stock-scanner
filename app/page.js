'use client';

import { useEffect, useMemo, useState } from 'react';
import { RefreshCw, Bell, Search, ShieldCheck, TrendingDown, Volume2, Activity } from 'lucide-react';

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
  if (Number(row.trader_similarity_score) >= 90) out.push('Sterke overeenkomst met historische trader-entries');
  if (Number(row.rsi_14) < 30) out.push(`RSI ${num(row.rsi_14)}: oversold`);
  if (Number(row.return_5d) <= -0.10) out.push(`${pct(row.return_5d)} in 5 dagen`);
  if (Number(row.distance_52w_high) <= -0.20) out.push(`${pct(row.distance_52w_high)} onder 52-weeks high`);
  if (Number(row.volume_ratio) >= 1.5) out.push(`${num(row.volume_ratio, 1)}x normaal volume`);
  if (Number(row.macd_histogram_change) > 0) out.push('MACD histogram verbetert');
  if (Number(row.relative_strength_20d) > 0) out.push('Sterkere relatieve performance dan markt');
  if (!out.length) out.push('Meerdere technische kenmerken wijzen dezelfde kant op');
  return out.slice(0, 4);
}

function signal(row) {
  return row?.signal || 'WATCH';
}

export default function Home() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [filter, setFilter] = useState('ALL');
  const [query, setQuery] = useState('');

  async function load() {
    setLoading(true);
    setError('');
    try {
      const res = await fetch('/data/latest_scan.json?ts=' + Date.now(), { cache: 'no-store' });
      if (!res.ok) throw new Error('Latest scan is not available yet.');
      setData(await res.json());
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  const all = data?.results || [];
  const alerts = useMemo(() => all.filter(r => signal(r) === 'ALERT'), [all]);
  const watches = useMemo(() => all.filter(r => signal(r) === 'WATCH'), [all]);

  const rows = useMemo(() => {
    return all
      .filter(r => filter === 'ALL' || String(r.setup_type).toUpperCase() === filter)
      .filter(r => !query || String(r.ticker).toLowerCase().includes(query.toLowerCase()) || String(r.company_name || '').toLowerCase().includes(query.toLowerCase()));
  }, [all, filter, query]);

  const topAlert = alerts[0];

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <div className="eyebrow">TRADER PATTERN SCANNER</div>
          <h1>Market alerts</h1>
          <p>Scans the largest U.S.-listed companies and looks for setups that resemble the trader's historical entries.</p>
        </div>
        <button className="refresh" onClick={load} disabled={loading}>
          <RefreshCw size={16} className={loading ? 'spin' : ''} /> Scan opnieuw
        </button>
      </header>

      {error && <div className="error">{error}</div>}

      <section className={`alertHero ${topAlert ? 'hasAlert' : 'noAlert'}`}>
        <div className="alertIcon"><Bell size={22} /></div>
        <div className="alertBody">
          <div className="alertLabel">{topAlert ? 'ACTIEVE BUY ALERT' : 'GEEN BUY ALERT'}</div>
          {topAlert ? (
            <>
              <div className="alertTitle"><strong>{topAlert.ticker}</strong><span>{topAlert.company_name || 'Company name unavailable'}</span></div>
              <div className="alertMeta">${num(topAlert.price, 2)} · Score <strong>{score(topAlert.overall_score)}/100</strong> · Trader similarity <strong>{score(topAlert.trader_similarity_score)}/100</strong> · {String(topAlert.setup_type).toUpperCase()}</div>
              <div className="reasonGrid">{reasons(topAlert).map((r, i) => <div key={i} className="reason">{r}</div>)}</div>
            </>
          ) : (
            <>
              <div className="alertTitle"><strong>Er is nu geen sterk genoeg signaal</strong></div>
              <div className="alertMeta">De scanner blijft wel kandidaten volgen. Een WATCH is geen koopalert.</div>
            </>
          )}
        </div>
      </section>

      <section className="stats">
        <div className="stat"><span>MARKT</span><strong>{data?.universe_size ?? '—'}</strong><small>bedrijven gescand</small></div>
        <div className="stat"><span>BUY ALERTS</span><strong>{data?.alert_count ?? 0}</strong><small>score boven alert-drempel</small></div>
        <div className="stat"><span>WATCHLIST</span><strong>{watches.length}</strong><small>interessante kandidaten</small></div>
        <div className="stat"><span>LAATSTE SCAN</span><strong>{data?.generated_at ? new Date(data.generated_at).toLocaleTimeString('nl-NL', { hour: '2-digit', minute: '2-digit' }) : '—'}</strong><small>{data?.generated_at ? new Date(data.generated_at).toLocaleDateString('nl-NL') : ''}</small></div>
      </section>

      <section className="panel">
        <div className="panelhead">
          <div>
            <div className="sectionEyebrow">WATCHLIST</div>
            <h2>Beste huidige kandidaten</h2>
            <p>Geen automatische koopadviezen. De score bepaalt alleen welke setups nader onderzoek verdienen.</p>
          </div>
          <div className="controls">
            <div className="search"><Search size={15}/><input value={query} onChange={e => setQuery(e.target.value)} placeholder="Zoek aandeel..." /></div>
            <div className="tabs">{['ALL', 'REBOUND', 'QUALITY', 'CYCLICAL'].map(x => <button key={x} className={filter === x ? 'active' : ''} onClick={() => setFilter(x)}>{x}</button>)}</div>
          </div>
        </div>

        {loading && !data ? <div className="empty">Scanresultaten laden...</div> : (
          <div className="tablewrap">
            <table>
              <thead><tr><th>#</th><th>Aandeel</th><th>Prijs</th><th>Signaal</th><th>Score</th><th>Trader match</th><th>Setup</th><th>5D</th><th>RSI</th><th>Volume</th></tr></thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr key={r.ticker} className={signal(r) === 'ALERT' ? 'alertRow' : ''}>
                    <td className="muted">{i + 1}</td>
                    <td><div className="company"><span className="ticker">{r.ticker}</span><small>{r.company_name || 'Onbekende bedrijfsnaam'}</small></div></td>
                    <td>${num(r.price, 2)}</td>
                    <td><span className={`signal ${String(signal(r)).toLowerCase()}`}>{signal(r)}</span></td>
                    <td className="score">{score(r.overall_score)}</td>
                    <td>{score(r.trader_similarity_score)}</td>
                    <td><span className={`badge ${String(r.setup_type).toLowerCase()}`}>{r.setup_type}</span></td>
                    <td className={Number(r.return_5d) < 0 ? 'negative' : 'positive'}>{pct(r.return_5d)}</td>
                    <td>{num(r.rsi_14)}</td>
                    <td>{num(r.volume_ratio, 1)}x</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="infoGrid">
        <div className="infoCard"><TrendingDown size={18}/><div><strong>Wat is een alert?</strong><p>Een alert verschijnt alleen wanneer de combinatie van trader similarity en technische setup boven de ingestelde drempel komt.</p></div></div>
        <div className="infoCard"><Volume2 size={18}/><div><strong>Waarom meerdere factoren?</strong><p>RSI alleen is niet genoeg. De scanner gebruikt onder meer momentum, volume, volatiliteit, gemiddelden, support en relatieve performance.</p></div></div>
        <div className="infoCard"><Activity size={18}/><div><strong>Wat wordt geleerd?</strong><p>Het model vergelijkt historische trader entries met dezelfde marktcondities zonder entry en zoekt naar terugkerende kenmerken.</p></div></div>
        <div className="infoCard"><ShieldCheck size={18}/><div><strong>Belangrijk</strong><p>Dit is een onderzoeksprototype. Een hoge score is geen garantie op rendement.</p></div></div>
      </section>

      <footer>Trader Pattern Scanner · laatste scan {data?.generated_at ? new Date(data.generated_at).toLocaleString('nl-NL') : '—'}</footer>
    </main>
  );
}
