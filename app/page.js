'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { Bell, ChevronRight, Clock, Layers, Target } from 'lucide-react';
import './ui/mi.css';
import { useSettings } from './ui/settings';
import { makeT } from './ui/i18n';
import { highlights, makeFmt, shortfall, whyNot } from './ui/dipText';
import { Avatar, DetailPanel, Kpi, MiniSpark, Sidebar, TopBar } from './ui/components';

const dipVal = (r) => (r.dip == null ? 9 : Number(r.dip));

export default function Home() {
  const { theme, lang, setTheme, setLang } = useSettings();
  const t = useMemo(() => makeT(lang), [lang]);
  const f = useMemo(() => makeFmt(lang), [lang]);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [query, setQuery] = useState('');
  const [showAll, setShowAll] = useState(false);
  const [selTicker, setSelTicker] = useState(null);
  const [sheet, setSheet] = useState(false);
  const universeRef = useRef(null);

  async function load() {
    setLoading(true); setError('');
    try {
      const x = await fetch('/api/scan?ts=' + Date.now(), { cache: 'no-store' });
      const body = await x.json();
      if (!x.ok) throw Error(body.error || t('err_scan'));
      setData(body);
    } catch (e) { setError(e.message); } finally { setLoading(false); }
  }
  async function startScan() {
    if (loading) return;
    const previous = data?.generated_at || '';
    setLoading(true); setNotice(t('scan_started'));
    try {
      const r = await fetch('/api/trigger-scan', { method: 'POST' });
      const rb = await r.json().catch(() => ({}));
      if (!r.ok) throw Error(rb.error || t('scan_fail'));
      const started = Date.now();
      while (Date.now() - started < 10 * 60 * 1000) {
        await new Promise((ok) => setTimeout(ok, 10000));
        const x = await fetch('/api/scan?ts=' + Date.now(), { cache: 'no-store' });
        if (!x.ok) continue;
        const body = await x.json();
        if (body?.generated_at && body.generated_at !== previous) { setData(body); setNotice(t('scan_done')); return; }
      }
      throw Error(t('scan_long'));
    } catch (e) { setError(e.message); setNotice(''); } finally { setLoading(false); }
  }
  useEffect(() => { load(); }, []);

  const all = data?.results || [];
  const topN = data?.dip_breadth?.top_n || 5;
  const alerts = useMemo(
    () => all.filter((r) => r.signal === 'ALERT').sort((a, b) => (Number(a.dip_rank ?? 1e9) - Number(b.dip_rank ?? 1e9)) || (Number(a.dip ?? 9) - Number(b.dip ?? 9))).slice(0, topN).sort((a, b) => Number(a.dip ?? 9) - Number(b.dip ?? 9)),
    [all, topN]
  );
  const opps = useMemo(
    () => all.filter((r) => !r.dip_signal && r.dip != null).sort((a, b) => {
      const qa = a.dip_qualifies && !a.dip_excluded ? 0 : 1, qb = b.dip_qualifies && !b.dip_excluded ? 0 : 1;
      return qa !== qb ? qa - qb : qa === 0 ? dipVal(a) - dipVal(b) : shortfall(a) - shortfall(b);
    }).slice(0, 10),
    [all]
  );
  const plek = useMemo(() => {
    const base = all.filter((r) => r.dip_signal).length, m = new Map();
    all.filter((r) => !r.dip_signal && r.dip_qualifies && !r.dip_excluded).sort((a, b) => Number(a.dip ?? 9) - Number(b.dip ?? 9)).forEach((r, i) => m.set(r.ticker, base + i + 1));
    return m;
  }, [all]);
  const oppIdx = useMemo(() => new Map(opps.map((r, i) => [r.ticker, i])), [opps]);
  const universe = useMemo(() => {
    const q = query.trim().toLowerCase();
    return all.filter((r) => !q || `${r.ticker} ${r.company_name || ''}`.toLowerCase().includes(q)).sort((a, b) => {
      const ga = a.dip_signal ? 0 : oppIdx.has(a.ticker) ? 1 : 2, gb = b.dip_signal ? 0 : oppIdx.has(b.ticker) ? 1 : 2;
      if (ga !== gb) return ga - gb;
      return a.dip_signal ? dipVal(a) - dipVal(b) : oppIdx.has(a.ticker) ? oppIdx.get(a.ticker) - oppIdx.get(b.ticker) : dipVal(a) - dipVal(b);
    });
  }, [all, query, oppIdx]);
  const visible = showAll || query ? universe : universe.slice(0, 25);

  const selected = all.find((r) => r.ticker === selTicker) || alerts[0] || null;
  useEffect(() => { try { window.__miSelected = selected || null; } catch { /* */ } }, [selected?.ticker]);
  useEffect(() => { if (query) universeRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }); }, [query === '']);
  const pick = (r) => { setSelTicker(r.ticker); setSheet(true); };

  const chg = (r) => (r.return_1d == null ? <span className="mi-faint">—</span> : <span className={r.return_1d >= 0 ? 'pos' : 'neg'}>{f.signed(r.return_1d, 1)}</span>);

  return (
    <div className="mi">
      <Sidebar t={t} counts={{ signals: alerts.length, near: opps.length }} />
      <div className="mi-content">
        <TopBar t={t} f={f} query={query} setQuery={setQuery} generatedAt={data?.generated_at} loading={loading} onScan={startScan} theme={theme} setTheme={setTheme} lang={lang} setLang={setLang} />
        <div className="mi-main">
          <div className="mi-left">
            <div className="mi-head">
              <span className="count">{alerts.length === 1 ? t('signals_count_one') : t('signals_count', { n: alerts.length })}</span>
              <h1>{t('signals_title')}</h1>
              <p>{t('signals_sub')}</p>
            </div>
            <div className="mi-kpis">
              <Kpi icon={Bell} tone="blue" label={t('kpi_signals')} value={alerts.length} sub={t('kpi_signals_sub')} />
              <Kpi icon={Target} tone="amber" label={t('kpi_near')} value={opps.length} sub={t('kpi_near_sub')} />
              <Kpi icon={Layers} tone="violet" label={t('kpi_universe')} value={universe.length || '—'} sub={t('kpi_universe_sub')} />
              <Kpi icon={Clock} tone="green" label={t('kpi_scan')} value={data?.generated_at ? f.time(data.generated_at) : '—'} sub={data?.generated_at ? f.date(data.generated_at) : ''} />
            </div>
            {notice && <div className="mi-notice">{notice}</div>}
            {error && <div className="mi-error">{error}</div>}

            <section className="mi-card" aria-label={t('signals_title')}>
              <div className="mi-row head mi-grid-sig">
                <span className="c-rank">#</span><span>{t('col_stock')}</span><span className="c-price">{t('col_price')}</span><span className="c-chg">{t('col_change')}</span><span className="c-trend">{t('col_trend')}</span><span>{t('col_52')}</span><span />
              </div>
              {alerts.length ? alerts.map((r, i) => (
                <button key={r.ticker} className={`mi-row mi-grid-sig${selected?.ticker === r.ticker ? ' sel' : ''}`} onClick={() => pick(r)}>
                  <span className="mi-rank num c-rank">{i + 1}</span>
                  <span className="mi-stock"><Avatar ticker={r.ticker} /><span><b>{r.ticker}</b><small>{r.company_name}</small></span></span>
                  <span className="num">{f.usd(r.price)}</span>
                  <span className="num c-chg">{chg(r)}</span>
                  <span className="c-trend"><MiniSpark data={r.spark} /></span>
                  <span className="num"><span className="mi-pill neg">{f.signed(r.d52, 0)}</span></span>
                                    <ChevronRight size={16} className="mi-chev" />
                </button>
              )) : <div className="mi-empty"><b>{t('empty_title')}</b>{t('empty_text')}</div>}
            </section>

            <section>
              <div className="mi-sec-head"><div><h2>{t('near_title')}</h2><p>{t('near_sub')}</p></div></div>
              <div className="mi-card">
                <div className="mi-row head mi-grid-tbl"><span>{t('col_stock')}</span><span>{t('col_price')}</span><span>{t('col_52')}</span><span className="c-30">{t('col_30')}</span><span className="c-miss">{t('col_missing')}</span></div>
                {opps.map((r) => (
                  <button key={r.ticker} className={`mi-row mi-grid-tbl${selected?.ticker === r.ticker ? ' sel' : ''}`} onClick={() => pick(r)}>
                    <span className="mi-stock"><Avatar ticker={r.ticker} /><span><b>{r.ticker}</b><small>{r.company_name}</small></span></span>
                    <span className="num">{f.usd(r.price)}</span>
                    <span className="num">{f.signed(r.d52, 0)}</span>
                    <span className="num c-30">{f.signed(r.dd30, 0)}</span>
                    <span className="mi-small c-miss">{whyNot(r, t, f, plek)}</span>
                  </button>
                ))}
              </div>
            </section>

            <section ref={universeRef} id="universe" style={{ scrollMarginTop: 80 }}>
              <div className="mi-sec-head"><div><h2>{t('all_title')}</h2><p>{t('all_sub')}</p></div></div>
              <div className="mi-card">
                <div className="mi-row head mi-grid-tbl"><span>{t('col_stock')}</span><span>{t('col_price')}</span><span>{t('col_52')}</span><span className="c-30">{t('col_30')}</span><span className="c-miss">{t('col_status')}</span></div>
                {visible.map((r) => (
                  <button key={r.ticker} className={`mi-row mi-grid-tbl${selected?.ticker === r.ticker ? ' sel' : ''}`} onClick={() => pick(r)}>
                    <span className="mi-stock"><Avatar ticker={r.ticker} /><span><b>{r.ticker}</b><small>{r.company_name}</small></span></span>
                    <span className="num">{f.usd(r.price)}</span>
                    <span className="num">{r.d52 == null ? '—' : f.signed(r.d52, 0)}</span>
                    <span className="num c-30">{r.dd30 == null ? '—' : f.signed(r.dd30, 0)}</span>
                    <span className="c-miss">{r.dip_signal ? <span className="mi-chip">{t('chip_signal')}</span> : <span className="mi-small">{whyNot(r, t, f, plek)}</span>}</span>
                  </button>
                ))}
                {universe.length > 25 && !query && (
                  <div className="mi-foot">
                    <span>{t('shown_of', { a: visible.length, b: universe.length })}</span>
                    <button className="mi-btn sm" onClick={() => setShowAll((v) => !v)}>{showAll ? t('show_top') : t('show_all', { n: universe.length })}</button>
                  </div>
                )}
              </div>
            </section>
          </div>
          <DetailPanel r={selected} t={t} f={f} lang={lang} whyNotText={selected ? whyNot(selected, t, f, plek) : ''} open={sheet} onClose={() => setSheet(false)} />
        </div>
      </div>
    </div>
  );
}
