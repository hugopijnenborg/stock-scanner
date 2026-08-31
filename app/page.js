'use client';

import { useEffect, useMemo, useState } from 'react';
import { RefreshCw, TrendingUp, Activity, Database, ShieldCheck } from 'lucide-react';

function pct(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—';
  return `${(Number(value) * 100).toFixed(1)}%`;
}

function score(value) {
  return value === null || value === undefined ? '—' : Number(value).toFixed(0);
}

export default function Home() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [filter, setFilter] = useState('ALL');

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

  const rows = useMemo(() => {
    const all = data?.results || [];
    return filter === 'ALL' ? all : all.filter(x => x.setup_type?.toUpperCase() === filter);
  }, [data, filter]);

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <div className="eyebrow">TRADER SCANNER</div>
          <h1>Market opportunities</h1>
          <p>Ranked setups across the US large-cap universe.</p>
        </div>
        <button className="refresh" onClick={load} disabled={loading}>
          <RefreshCw size={16} className={loading ? 'spin' : ''} /> Refresh
        </button>
      </header>

      {error && <div className="error">{error}</div>}

      <section className="stats">
        <div className="stat"><Database size={18}/><span>Universe</span><strong>{data?.universe_size ?? '—'}</strong></div>
        <div className="stat"><TrendingUp size={18}/><span>Alerts</span><strong>{data?.alert_count ?? '—'}</strong></div>
        <div className="stat"><Activity size={18}/><span>Top score</span><strong>{score(data?.top_score)}</strong></div>
        <div className="stat"><ShieldCheck size={18}/><span>Last scan</span><strong>{data?.generated_at ? new Date(data.generated_at).toLocaleString() : '—'}</strong></div>
      </section>

      <section className="panel">
        <div className="panelhead">
          <div>
            <h2>Top setups</h2>
            <p>Technical opportunity blended with learned trader similarity.</p>
          </div>
          <div className="tabs">
            {['ALL', 'REBOUND', 'QUALITY', 'CYCLICAL'].map(x => <button key={x} className={filter === x ? 'active' : ''} onClick={() => setFilter(x)}>{x}</button>)}
          </div>
        </div>

        {loading && !data ? <div className="empty">Loading scan...</div> : (
          <div className="tablewrap">
            <table>
              <thead><tr><th>#</th><th>Ticker</th><th>Price</th><th>Setup</th><th>Score</th><th>Similarity</th><th>Reversal</th><th>5D</th><th>20D</th><th>RSI</th></tr></thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr key={r.ticker}>
                    <td className="muted">{i + 1}</td>
                    <td className="ticker">{r.ticker}</td>
                    <td>${Number(r.price).toFixed(2)}</td>
                    <td><span className={`badge ${String(r.setup_type).toLowerCase()}`}>{r.setup_type}</span></td>
                    <td className="score">{score(r.overall_score)}</td>
                    <td>{score(r.trader_similarity_score)}</td>
                    <td>{score(r.reversal_trigger)}</td>
                    <td className={Number(r.return_5d) < 0 ? 'negative' : 'positive'}>{pct(r.return_5d)}</td>
                    <td className={Number(r.return_20d) < 0 ? 'negative' : 'positive'}>{pct(r.return_20d)}</td>
                    <td>{Number(r.rsi_14).toFixed(1)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <footer>Research tool. Scores are model outputs and are not financial advice.</footer>
    </main>
  );
}
