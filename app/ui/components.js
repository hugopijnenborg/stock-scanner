'use client';
import { useState } from 'react';
import Link from 'next/link';
import { BarChart3, Bell, ChevronRight, History, Moon, RefreshCw, Search, Sun, Target, Wallet, X } from 'lucide-react';
import { addPosition } from '../portfolio/addPosition';
import { earningsText, supportList, watchList } from './dipText';

export function Logo() {
  return (
    <svg width="30" height="30" viewBox="0 0 30 30" aria-hidden="true">
      <rect width="30" height="30" rx="8" fill="var(--mi-accent)" />
      <rect x="7" y="15" width="3.6" height="8" rx="1" fill="#fff" />
      <rect x="13.2" y="10" width="3.6" height="13" rx="1" fill="#fff" />
      <rect x="19.4" y="6" width="3.6" height="17" rx="1" fill="#fff" />
    </svg>
  );
}

export function Sidebar({ t, counts }) {
  const items = [
    { href: '/', icon: Bell, label: t('nav_signals'), on: true },
    { href: '/portfolio', icon: Wallet, label: t('nav_portfolio') },
    { href: '/history', icon: History, label: t('nav_history') },
    { href: '/performance', icon: BarChart3, label: t('nav_performance') },
    { href: '/validation', icon: Target, label: t('nav_validation') },
  ];
  return (
    <aside className="mi-side sidebar">
      <div className="mi-brand"><Logo /><div><b>{t('brand')}</b><small>{t('brandSub')}</small></div></div>
      <nav>
        {items.map((it) => {
          const Icon = it.icon;
          return <Link key={it.href} href={it.href} className={`mi-nav${it.on ? ' on' : ''}`} aria-current={it.on ? 'page' : undefined}><Icon size={18} /><span>{it.label}</span></Link>;
        })}
      </nav>
      <div className="mi-side-foot">
        <div className="mi-live"><i />{t('status_active')}</div>
        <div className="mi-side-stat"><span>{t('side_signals')}</span><b className="num">{counts.signals}</b></div>
        <div className="mi-side-stat"><span>{t('side_close')}</span><b className="num">{counts.near}</b></div>
      </div>
    </aside>
  );
}

export function TopBar({ t, f, query, setQuery, generatedAt, loading, onScan, theme, setTheme, lang, setLang }) {
  const time = generatedAt ? new Date(generatedAt).toLocaleTimeString(lang === 'en' ? 'en-GB' : 'nl-NL', { hour: '2-digit', minute: '2-digit' }) : '—';
  return (
    <header className="mi-top">
      <label className="mi-search">
        <Search size={16} />
        <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder={t('search')} aria-label={t('search')} />
      </label>
      <div className="mi-top-right">
        <div className="mi-scanmeta"><i />{t('last_scan')} <b className="num">{time}</b></div>
        <div className="mi-seg" role="group" aria-label={t('language')}>
          <button aria-pressed={lang === 'nl'} onClick={() => setLang('nl')}>NL</button>
          <button aria-pressed={lang === 'en'} onClick={() => setLang('en')}>EN</button>
        </div>
        <button className="mi-btn mi-iconbtn" onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')} aria-label={theme === 'dark' ? t('theme_light') : t('theme_dark')} title={theme === 'dark' ? t('theme_light') : t('theme_dark')}>
          {theme === 'dark' ? <Sun size={17} /> : <Moon size={17} />}
        </button>
        <button className="mi-btn primary" onClick={onScan} disabled={loading}><RefreshCw size={15} />{loading ? t('loading') : t('run_scan')}</button>
      </div>
    </header>
  );
}

export function Spark({ data, up }) {
  if (!Array.isArray(data) || data.length < 3) return null;
  const w = 360, h = 56, pad = 3;
  const min = Math.min(...data), max = Math.max(...data), span = max - min || 1;
  const pts = data.map((v, i) => [pad + (i * (w - 2 * pad)) / (data.length - 1), h - pad - ((v - min) / span) * (h - 2 * pad)]);
  const d = pts.map((p, i) => `${i ? 'L' : 'M'}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(' ');
  const color = up ? 'var(--mi-pos)' : 'var(--mi-neg)';
  return (
    <svg className="mi-spark" viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" role="img" aria-label="">
      <path d={`${d} L${pts[pts.length - 1][0]},${h} L${pts[0][0]},${h} Z`} fill={color} opacity=".08" />
      <path d={d} fill="none" stroke={color} strokeWidth="1.8" vectorEffect="non-scaling-stroke" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

function AddToPortfolio({ r, t }) {
  const [open, setOpen] = useState(false);
  const [qty, setQty] = useState('1');
  const [price, setPrice] = useState(String(Number(r.price).toFixed(2)));
  const [busy, setBusy] = useState(false);
  if (!open) return <button className="mi-btn primary sm" onClick={() => { setPrice(String(Number(r.price).toFixed(2))); setOpen(true); }}><Wallet size={15} />{t('add_portfolio')}</button>;
  const save = () => {
    const q = Number(qty), p = Number(price);
    if (!(q > 0 && p > 0)) return;
    setBusy(true);
    addPosition(r, q, p);
    window.location.href = '/portfolio';
  };
  return (
    <div className="mi-form">
      <label>{t('quantity')}<input type="number" min="0.0001" step="any" value={qty} onChange={(e) => setQty(e.target.value)} /></label>
      <label>{t('entry_price')}<input type="number" min="0.01" step="0.01" value={price} onChange={(e) => setPrice(e.target.value)} /></label>
      <button className="mi-btn primary sm" onClick={save} disabled={busy}>{busy ? t('saving') : t('save')}</button>
      <button className="mi-btn sm" onClick={() => setOpen(false)}>{t('cancel')}</button>
    </div>
  );
}

export function DetailPanel({ r, t, f, lang, whyNotText, open, onClose }) {
  if (!r) return <aside className={`mi-detail${open ? ' open' : ''}`}><div className="mi-d-empty">{t('pick_hint')}</div></aside>;
  const c = r.dip_context || {};
  const info = r.company_info, ai = r.alert_info, p = info?.profile;
  const days = ai?.since ? Math.max(0, Math.floor((Date.now() - new Date(ai.since).getTime()) / 86400000)) : null;
  const sinceMove = ai?.price && r.price ? r.price / ai.price - 1 : null;
  const supports = supportList(r, t, f), watch = watchList(r, t, f);
  const dsrc = lang === 'nl' ? (p?.description_nl || p?.description) : p?.description;
  const desc = dsrc ? (dsrc.length > 520 ? dsrc.slice(0, 520).replace(/\s+\S*$/, '') + '…' : dsrc) : null;
  const industry = lang === 'nl' ? (p?.industry_nl || p?.industry) : p?.industry;
  const KIND = { analist: t('k_analyst'), cijfers: t('k_earnings'), nieuws: t('k_news'), persbericht: t('k_press') };
  const items = info ? [...(info.news || []), ...(info.press || [])].sort((x, y) => String(y.date).localeCompare(String(x.date))) : [];
  const ch = r.return_1d;
  const activeLine = days != null && (days <= 0 ? t('active_today') : days === 1 ? t('active_days_one') : t('active_days', { n: days })) + (ai.price ? t('active_price', { p: f.usd(ai.price) }) + (sinceMove != null ? t('active_now', { m: f.signed(sinceMove, 1) }) : '') : '') + '.';
  const sparkUp = Array.isArray(r.spark) && r.spark.length > 2 ? r.spark[r.spark.length - 1] >= r.spark[0] : true;
  const target = c.pt_upside != null && r.price ? r.price * (1 + c.pt_upside) : null;
  return (
    <aside className={`mi-detail${open ? ' open' : ''}`} aria-label={r.ticker}>
      <div className="mi-d-head">
        <div className="mi-d-title">
          <div>
            <h2>{r.ticker}</h2>
            <p>{r.company_name || r.ticker}</p>
            <small>{[r.sector, industry].filter(Boolean).join(' · ')}</small>
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            {r.dip_signal ? <span className="mi-chip">{t('chip_active')}</span> : null}
            <button className="mi-btn mi-iconbtn mi-d-close sm" style={{ width: 34 }} onClick={onClose} aria-label={t('close')}><X size={16} /></button>
          </div>
        </div>
        <div className="mi-d-price num"><b>{f.usd(r.price)}</b>{ch != null && <span className={ch >= 0 ? 'pos' : 'neg'}>{f.signed(ch, 1)}</span>}</div>
        <Spark data={r.spark} up={sparkUp} />
        {!r.dip_signal && whyNotText ? <p className="mi-small" style={{ marginTop: 10 }}>{whyNotText}</p> : null}
        {r.dip_signal ? <div className="mi-d-actions"><AddToPortfolio r={r} t={t} /></div> : null}
      </div>
      {r.earnings_warning ? <div className="mi-warnbox" style={{ margin: '16px 22px 0' }}>{t('l_earn', { e: earningsText(r, t) })}</div> : null}
      <div className="mi-tiles">
        <div className="mi-tile"><span>{t('t_below52')}</span><b className="num">{f.signed(r.d52, 0)}</b></div>
        <div className="mi-tile"><span>{t('t_below30')}</span><b className="num">{f.signed(r.dd30, 0)}</b></div>
        <div className="mi-tile"><span>{t('t_rsi')}</span><b className="num">{f.num(c.rsi ?? r.rsi_14, 0)}</b></div>
        <div className="mi-tile"><span>{t('t_target')}</span><b className="num">{target ? f.usd(target, 0) : '—'}</b>{c.pt_upside != null && <small className="num">{f.signed(c.pt_upside, 0)}</small>}</div>
      </div>
      <section className="mi-d-sec">
        <h3>{t('h_why')}</h3>
        {activeLine ? <p style={{ marginBottom: 6 }}>{activeLine}</p> : null}
        <h4>{t('h_supports')}</h4>
        <ul className="mi-list">{supports.map((x, i) => <li key={i}>{x}</li>)}</ul>
        <h4>{t('h_watch')}</h4>
        {watch.length ? <ul className="mi-list watch">{watch.map((x, i) => <li key={i}>{x}</li>)}</ul> : <p>{t('l_none')}</p>}
      </section>
      <section className="mi-d-sec">
        <h3>{t('h_company')}</h3>
        {desc ? <><p>{desc}</p><p className="mi-small" style={{ marginTop: 8 }}>{[p.ceo && `CEO ${p.ceo}`, p.employees && `${f.int(p.employees)} ${t('employees')}`, p.country, t('source_fmp')].filter(Boolean).join(' · ')}</p></> : <p>{t('no_desc')}</p>}
      </section>
      <section className="mi-d-sec">
        <h3>{t('h_news')}</h3>
        {items.length ? (
          <>
            <ul className="mi-news">
              {items.map((x, i) => (
                <li key={i}>
                  <time className="num">{String(x.date || '').split('-').reverse().join('-')}</time>
                  <div><span className="k">{KIND[x.kind] || t('k_news')}</span><br /><a href={x.url} target="_blank" rel="noreferrer">{lang === 'nl' ? (x.title_nl || x.title) : x.title}</a> <span className="pub">· {x.publisher}</span></div>
                </li>
              ))}
            </ul>
            <p className="mi-small" style={{ marginTop: 8 }}>{t('news_note')}</p>
          </>
        ) : <p>{info ? t('news_none') : t('news_pending')}</p>}
      </section>
      <section className="mi-d-sec">
        <h3>{t('h_figures')}</h3>
        <dl className="mi-dl num">
          <div><dt>{t('f_below52')}</dt><dd>{f.signed(r.d52, 0)}</dd></div>
          <div><dt>{t('f_below30')}</dt><dd>{f.signed(r.dd30, 0)}</dd></div>
          <div><dt>{t('f_rsi')}</dt><dd>{f.num(c.rsi ?? r.rsi_14, 0)}</dd></div>
          <div><dt>{t('f_target')}</dt><dd>{target ? `${f.usd(target)} (${f.signed(c.pt_upside, 0)})` : '—'}</dd></div>
          <div><dt>{t('f_consensus')}</dt><dd>{c.grades_consensus || '—'}</dd></div>
          <div><dt>{t('f_earn')}</dt><dd>{c.next_earnings ? f.date(c.next_earnings) : '—'}</dd></div>
          <div><dt>{t('f_margins')}</dt><dd>{f.pct(c.gross_margin, 0)} / {f.pct(c.fcf_margin, 0)}</dd></div>
        </dl>
      </section>
    </aside>
  );
}
