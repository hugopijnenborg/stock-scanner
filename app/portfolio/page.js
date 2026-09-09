'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import {
  Activity,
  BarChart3,
  Bell,
  History,
  LayoutDashboard,
  Plus,
  RefreshCw,
  Target,
  TrendingDown,
  Wallet,
  X,
} from 'lucide-react';
import './portfolio.css';
import { buildTradePlan, getPortfolioAction } from './tradePlan';

const KEY = 'marketintel_portfolio';

const money = (v, d = 2) => {
  if (v == null || !Number.isFinite(Number(v))) return '—';
  return `$${Number(v).toLocaleString('en-US', {
    minimumFractionDigits: d,
    maximumFractionDigits: d,
  })}`;
};

const pct = (v) => {
  if (v == null || !Number.isFinite(Number(v))) return '—';
  return `${Number(v) >= 0 ? '+' : ''}${(Number(v) * 100).toFixed(1)}%`;
};

const score = (v) => {
  if (v == null || !Number.isFinite(Number(v))) return '—';
  return Number(v).toFixed(0);
};

const read = () => {
  try {
    return JSON.parse(localStorage.getItem(KEY) || '[]');
  } catch {
    return [];
  }
};

function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="sideBrand">
        <div className="brandMark"><Activity size={18} /></div>
        <div>
          <b>MARKET<span>INTEL</span></b>
          <small>TRADER PATTERN SCANNER</small>
        </div>
      </div>
      <nav>
        <div className="navLabel">WORKSPACE</div>
        <Link href="/" className="navItem"><LayoutDashboard size={16} />Scanner</Link>
        <Link href="/portfolio" className="navItem active"><Wallet size={16} />Portfolio</Link>
        <Link href="/history" className="navItem"><History size={16} />Alert history</Link>
        <Link href="/performance" className="navItem"><BarChart3 size={16} />Performance</Link>
        <Link href="/validation" className="navItem"><Target size={16} />Model validation</Link>
      </nav>
      <div className="sideBottom">
        <div className="liveStatus"><span className="liveDot" />PORTFOLIO ACTIEF</div>
      </div>
    </aside>
  );
}

function TradePlan({ plan, action }) {
  if (!plan) return null;

  const level = (v) => money(v);
  const addZone = plan.addLow != null && plan.addHigh != null
    ? `${level(plan.addLow)} – ${level(plan.addHigh)}`
    : level(plan.addHigh);

  return (
    <div className="tradePlan">
      <div className="tradePlanTitle">
        <div>
          <span>PERSONEEL TRADEPLAN</span>
          <strong>{action.label}</strong>
        </div>
        <small>LIVE</small>
      </div>

      <div className="tradePlanGrid">
        <div className="tradePlanRow"><span>1e koersdoel</span><b>{level(plan.firstTarget)}</b></div>
        <div className="tradePlanRow"><span>2e koersdoel</span><b>{level(plan.secondTarget)}</b></div>
        <div className="tradePlanRow"><span>ADD-zone</span><b className="tradeAdd">{addZone}</b></div>
        <div className="tradePlanRow"><span>Risk / stop</span><b className="tradeRisk">{level(plan.stop)}</b></div>
        <div className="tradePlanRow">
          <span>Potentieel</span>
          <b className={plan.targetUpside > 0 ? 'tradePositive' : 'tradeRisk'}>{pct(plan.targetUpside)}</b>
        </div>
        <div className="tradePlanRow">
          <span>Risk / reward</span>
          <b>{plan.rewardRisk ? `${plan.rewardRisk.toFixed(1)}x` : '—'}</b>
        </div>
      </div>

      <div className="tradePlanNote">
        <b>{action.label}</b> · {action.reason}
      </div>

      <div className="tradePlanContext">
        <span>TECHNISCHE CONTEXT</span>
        {plan.context}
      </div>

      <div className="tradePlanLevels">
        <span>Steun <b>{level(plan.support)}</b></span>
        <span>20D <b>{level(plan.sma20)}</b></span>
        <span>50D <b>{level(plan.sma50)}</b></span>
        <span>ATR <b>{pct(plan.atrPct)}</b></span>
      </div>

      <div className="tradePlanSource">
        Gebaseerd op actuele koers, technische steun/weerstand, trend, volatiliteit en beschikbare koersdoelen. De actie en niveaus worden uit dezelfde berekening afgeleid.
      </div>
    </div>
  );
}

function PositionCard({ position, r, onRemove }) {
  const price = Number(r?.price);
  const entry = Number(position.entryPrice);
  const qty = Number(position.quantity);
  const value = Number.isFinite(price) ? price * qty : null;
  const cost = entry * qty;
  const gain = value != null && cost > 0 ? value - cost : null;
  const gainPct = gain != null && cost > 0 ? gain / cost : null;
  const plan = buildTradePlan(position, r);
  const action = getPortfolioAction(position, r, plan);
  const target = Number(r?.analyst_target_mean);
  const targetUpside = target > 0 && price > 0 ? target / price - 1 : null;

  return (
    <div className="positionCard">
      <div className="positionTop">
        <div>
          <span className="positionTicker">{position.ticker}</span>
          <span className="positionCompany">{position.company}</span>
        </div>
        <span className={`positionAction ${action.tone}`}>{action.label}</span>
      </div>

      <div className="positionMain">
        <div><span>HUIDIGE KOERS</span><strong>{money(price)}</strong></div>
        <div><span>AANKOOPPRIJS</span><strong>{money(entry)}</strong></div>
        <div><span>AANTAL</span><strong>{qty}</strong></div>
        <div><span>POSITIE</span><strong>{money(value)}</strong></div>
        <div>
          <span>RENDEMENT</span>
          <strong className={gain == null || gain >= 0 ? 'positive' : 'negative'}>
            {gain == null ? '—' : `${gain >= 0 ? '+' : ''}${money(gain)} (${pct(gainPct)})`}
          </strong>
        </div>
      </div>

      <div className={`positionAlert ${action.tone}`}>
        <div>
          {action.tone === 'sell' ? (
            <TrendingDown size={16} />
          ) : action.tone === 'add' ? (
            <Plus size={16} />
          ) : (
            <Bell size={16} />
          )}
          <div>
            <b>
              {action.label === 'ADD'
                ? 'BIJKOOPMOGELIJKHEID'
                : action.label === 'SELL'
                  ? 'VERKOOPSIGNAL'
                  : 'POSITIE BEHOUDEN'}
            </b>
            <span>{action.reason}</span>
          </div>
        </div>
      </div>

      <TradePlan plan={plan} action={action} />

      <div className="positionMeta">
        <span>Scanner score <b>{score(r?.overall_score)}</b></span>
        <span>Technisch <b>{score(r?.technical_score)}</b></span>
        <span>Analisten <b>{targetUpside == null ? '—' : pct(targetUpside)}</b></span>
        <span>Koersdoel <b>{target > 0 ? money(target) : '—'}</b></span>
        <button onClick={() => onRemove(position.ticker)} title="Verwijder positie"><X size={14} /></button>
      </div>
    </div>
  );
}

export default function PortfolioPage() {
  const [positions, setPositions] = useState([]);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setPositions(read());
    setLoading(true);
    try {
      const res = await fetch(`/api/scan?ts=${Date.now()}`, { cache: 'no-store' });
      if (res.ok) setData(await res.json());
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    const onChange = () => setPositions(read());
    window.addEventListener('marketintel-portfolio-change', onChange);
    const timer = setInterval(load, 30000);
    return () => {
      window.removeEventListener('marketintel-portfolio-change', onChange);
      clearInterval(timer);
    };
  }, []);

  const map = useMemo(
    () => Object.fromEntries((data?.results || []).map((r) => [r.ticker, r])),
    [data]
  );

  const stats = useMemo(() => {
    let cost = 0;
    let value = 0;
    for (const p of positions) {
      const q = Number(p.quantity);
      const e = Number(p.entryPrice);
      const r = map[p.ticker];
      const price = Number(r?.price);
      cost += q * e;
      if (Number.isFinite(price)) value += q * price;
    }
    return { cost, value, pnl: value - cost, pnlPct: cost ? value / cost - 1 : null };
  }, [positions, map]);

  const remove = (ticker) => {
    const next = positions.filter((x) => x.ticker !== ticker);
    localStorage.setItem(KEY, JSON.stringify(next));
    setPositions(next);
  };

  const actionCounts = useMemo(() => {
    const counts = { add: 0, hold: 0, sell: 0 };
    positions.forEach((p) => {
      const r = map[p.ticker];
      const action = getPortfolioAction(p, r, buildTradePlan(p, r));
      if (counts[action.tone] != null) counts[action.tone] += 1;
    });
    return counts;
  }, [positions, map]);

  return (
    <div className="appShell">
      <Sidebar />
      <main className="dashboard">
        <header className="topbar">
          <div>
            <div className="eyebrow">PORTFOLIO / LIVE POSITION MANAGEMENT</div>
            <h1>Mijn portfolio</h1>
            <p>Posities die je vanuit een BUY ALERT hebt toegevoegd, gekoppeld aan de actuele scannerdata.</p>
          </div>
          <div className="topActions">
            <div className="scanMeta">
              <span className="liveDot" /> SCANNER <b>{data?.generated_at ? new Date(data.generated_at).toLocaleTimeString('nl-NL', { hour: '2-digit', minute: '2-digit' }) : '—'}</b>
            </div>
            <Link href="/" className="refresh secondary"><LayoutDashboard size={15} /> Scanner</Link>
            <button className="refresh primary" onClick={load}><RefreshCw size={15} /> Vernieuwen</button>
          </div>
        </header>

        <section className="heroGrid">
          <div className="heroPanel">
            <div>
              <span className="sectionEyebrow">PORTFOLIO OVERVIEW</span>
              <h2>Je posities in één overzicht</h2>
              <p>De scanner beoordeelt iedere positie opnieuw. ADD, HOLD en SELL komen uit één tradeplan met score, technische bevestiging, steun, weerstand, risico en koersdoelen.</p>
            </div>
            <div className="heroStats">
              <div><span>POSITIES</span><strong>{positions.length}</strong><small>aandelen</small></div>
              <div><span>GEÏNVESTEERD</span><strong>{money(stats.cost, 0)}</strong><small>totale inleg</small></div>
              <div>
                <span>RENDEMENT</span>
                <strong className={stats.pnl >= 0 ? 'positive' : 'negative'}>{stats.pnl == null ? '—' : pct(stats.pnlPct)}</strong>
                <small>{stats.pnl == null ? 'geen actuele koers' : money(stats.pnl, 0)}</small>
              </div>
            </div>
          </div>
          <div className="heroSignal">
            <div className="signalHeader"><span>PORTFOLIO SIGNALS</span><Wallet size={15} /></div>
            <div className="portfolioSignalSummary">
              <div><strong>{actionCounts.add}</strong><span>ADD</span></div>
              <div><strong>{actionCounts.hold}</strong><span>HOLD</span></div>
              <div><strong>{actionCounts.sell}</strong><span>SELL</span></div>
            </div>
          </div>
        </section>

        <section className="sectionBlock">
          <div className="sectionHeader">
            <div>
              <div className="sectionEyebrow">01 · POSITIES</div>
              <h2>Actieve posities</h2>
              <p>Iedere positie krijgt actuele niveaus en één consistente actie. De signalen zijn richtinggevend en vervangen geen eigen risicobeoordeling.</p>
            </div>
            <div className="statusPill live"><Activity size={13} />{positions.length} actief</div>
          </div>

          {loading && !positions.length ? (
            <div className="emptyState">Portfolio laden...</div>
          ) : positions.length === 0 ? (
            <div className="emptyState alertEmpty">
              <div className="emptyIcon"><Wallet size={20} /></div>
              <strong>Nog geen posities</strong>
              <span>Open een BUY ALERT en klik op “Voeg toe aan portfolio” om een positie toe te voegen.</span>
              <Link href="/" className="refresh primary"><Bell size={14} /> Bekijk BUY ALERTS</Link>
            </div>
          ) : (
            <div className="positionGrid">
              {positions.map((p) => (
                <PositionCard key={p.ticker} position={p} r={map[p.ticker]} onRemove={remove} />
              ))}
            </div>
          )}
        </section>

        <section className="sectionBlock">
          <div className="sectionHeader">
            <div>
              <div className="sectionEyebrow">02 · SIGNAL LOGICA</div>
              <h2>Hoe ADD / HOLD / SELL werkt</h2>
              <p>De actie wordt uit hetzelfde tradeplan berekend als de koersniveaus.</p>
            </div>
            <Target size={18} />
          </div>
          <div className="signalRules">
            <div>
              <span className="positionAction add">ADD</span>
              <p>Sterke score, technische bevestiging, voldoende opwaarts potentieel en minimaal circa 2x risk/reward. De koers moet bovendien in de berekende koopzone rond steun liggen.</p>
            </div>
            <div>
              <span className="positionAction hold">HOLD</span>
              <p>De setup blijft gezond, maar de koers staat buiten de optimale koopzone of heeft de eerste weerstand bereikt. Dan wachten we liever op een betere instap.</p>
            </div>
            <div>
              <span className="positionAction sell">SELL</span>
              <p>De stop wordt geraakt, de score valt onder 60, de score verslechtert minimaal 10 punten, of een belangrijk koersdoel is vrijwel bereikt en er staat winst op de positie.</p>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
