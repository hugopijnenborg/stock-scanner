'use client';

import { useEffect, useRef, useState } from 'react';
import { usePathname } from 'next/navigation';
import Link from 'next/link';
import { Bell, X } from 'lucide-react';
import './meldingen.css';
import { buildNotifications, KIND_LABEL } from './notifications';

const KEY = 'marketintel_portfolio';
const PREF = 'marketintel_browser_notif';
const SENT = 'marketintel_notified';
const lsGet = (k, d) => { try { const v = localStorage.getItem(k); return v == null ? d : JSON.parse(v); } catch { return d; } };
const lsSet = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* opslag niet beschikbaar */ } };

// Zwevende meldingenknop op elke pagina + teller bij "Portfolio" in het menu.
export default function MeldingenWidget() {
  const path = usePathname() || '';
  const [notifs, setNotifs] = useState([]);
  const [open, setOpen] = useState(false);
  const [updated, setUpdated] = useState(null);
  const [pref, setPref] = useState(false);
  const [perm, setPerm] = useState('default');
  const prefRef = useRef(false);
  prefRef.current = pref;

  const run = async () => {
    const positions = lsGet(KEY, []);
    if (!Array.isArray(positions) || !positions.length) { setNotifs([]); return; }
    try {
      const tickers = [...new Set(positions.map((p) => p.ticker).filter(Boolean))].join(',');
      const res = await fetch(`/api/positions-market?tickers=${encodeURIComponent(tickers)}&ts=${Date.now()}`, { cache: 'no-store' });
      if (!res.ok) return;
      const body = await res.json();
      const map = Object.fromEntries((body.results || []).map((r) => [r.ticker, r]));
      const list = buildNotifications(positions, map);
      setNotifs(list);
      setUpdated(body.generated_at || null);
      if (prefRef.current && typeof Notification !== 'undefined' && Notification.permission === 'granted') {
        const sent = new Set(lsGet(SENT, []));
        for (const n of list.filter((x) => x.level !== 'info' && !sent.has(x.key))) {
          try { new Notification(`${n.ticker}: ${n.title}`, { body: n.detail || n.text, tag: n.key }); } catch { /* niet ondersteund */ }
          sent.add(n.key);
        }
        lsSet(SENT, [...sent].slice(-200));
      }
    } catch { /* tijdelijk geen verbinding: oude stand blijft staan */ }
  };

  useEffect(() => {
    setPref(!!lsGet(PREF, false));
    if (typeof Notification !== 'undefined') setPerm(Notification.permission);
    run();
    const timer = setInterval(run, 120000);
    const onChange = () => run();
    const onVisible = () => { if (document.visibilityState === 'visible') run(); };
    window.addEventListener('marketintel-portfolio-change', onChange);
    document.addEventListener('visibilitychange', onVisible);
    return () => { clearInterval(timer); window.removeEventListener('marketintel-portfolio-change', onChange); document.removeEventListener('visibilitychange', onVisible); };
  }, []);

  const count = notifs.filter((n) => n.level !== 'info').length;
  useEffect(() => {
    window.__miNotifCount = count;
    window.dispatchEvent(new Event('marketintel-notif-count'));
  }, [count]);

  const togglePref = async () => {
    if (pref) { setPref(false); lsSet(PREF, false); return; }
    if (typeof Notification === 'undefined') return;
    const p = Notification.permission === 'granted' ? 'granted' : await Notification.requestPermission();
    setPerm(p);
    if (p === 'granted') {
      lsSet(SENT, notifs.filter((n) => n.level !== 'info').map((n) => n.key)); // alleen nieuwe meldingen vanaf nu
      setPref(true); lsSet(PREF, true);
    }
  };

  if (path.startsWith('/portfolio') || !notifs.length) return null;
  const hhmm = updated ? new Date(updated).toLocaleTimeString('nl-NL', { hour: '2-digit', minute: '2-digit' }) : null;

  return (
    <div className="miNotifWrap">
      {open && (
        <div className="miNotifPanel" role="dialog" aria-label="Meldingen bij je posities">
          <div className="miNotifHead"><b>Meldingen bij je posities</b><button onClick={() => setOpen(false)} aria-label="Sluiten"><X size={14} /></button></div>
          <div className="miNotifList">
            {notifs.map((n) => (
              <Link key={n.key} href={`/portfolio#pos-${n.ticker}`} className={`miNotifItem ${n.level}`} onClick={() => setOpen(false)}>
                <span className={`miNotifTag ${n.kind}`}>{KIND_LABEL[n.kind]}</span>
                <strong>{n.ticker}</strong> <small>{n.company}</small>
                <p>{n.title}{n.detail ? ` · ${n.detail}` : ''}</p>
              </Link>
            ))}
          </div>
          <div className="miNotifFoot">
            <label><input type="checkbox" checked={pref} onChange={togglePref} disabled={typeof Notification === 'undefined' || perm === 'denied'} /> Ook een melding van de browser</label>
            <small>{perm === 'denied' ? 'Meldingen zijn in je browser geblokkeerd. ' : ''}Werkt alleen zolang de app open staat in je browser.{hhmm ? ` Laatste koersen: ${hhmm}.` : ''}</small>
          </div>
        </div>
      )}
      <button className={`miNotifBtn ${count ? 'hot' : ''}`} onClick={() => setOpen((v) => !v)}>
        <Bell size={15} /> {count ? `${count} ${count === 1 ? 'melding' : 'meldingen'} bij je posities` : `${notifs.length} info`}
      </button>
    </div>
  );
}
