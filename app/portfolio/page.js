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

const KEY = 'marketintel_portfolio';

const money = (value, decimals = 2) => {
  const number = Number(value);
  if (!Number.isFinite(number)) return '—';
  return `$${number.toLocaleString('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })}`;
};

const pct = (value) => {
  const number = Number(value);
  if (!Number.isFinite(number)) return '—';
  return `${number >= 0 ? '+' : ''}${(number * 100).toFixed(1)}%`;
};

const score = (value) => {
  const number = Number(value);
  if (!Number.isFinite(number)) return '—';
  return number.toFixed(0);
};

const read = () => {
  try {
    return JSON.parse(localStorage.getItem(KEY) || '[]');
  } catch {
    return [];
  }
};

function actionFor(position, result) {
  if (!result) {
    return {
      label: 'GEEN DATA',
      tone: 'neutral',
      reason: 'De scanner heeft momenteel geen actuele data voor deze positie.',
    };
  }

  const currentScore = Number(result.overall_score);
  const technicalScore = Number(result.technical_score);
  const entryScore = Number(position.entryScore);
  const price = Number(result.price);
  const entry = Number(position.entryPrice);
  const target = Number(result.analyst_target_mean);
  const gain = entry > 0 && price > 0 ? price / entry - 1 : null;
  const scoreChange =
    Number.isFinite(entryScore) && Number.isFinite(currentScore)
      ? currentScore - entryScore
      : null;

  if (
    (target > 0 && price >= target * 0.98 && gain != null && gain > 0.05) ||
    currentScore < 60 ||
    (scoreChange != null && scoreChange <= -10)
  ) {
    return {
      label: 'SELL',
      tone: 'sell',
      reason:
        target > 0 && price >= target * 0.98
          ? 'Koers zit rond het gemiddelde analistenkoersdoel.'
          : currentScore < 60
            ? 'De totaalscore is onder 60 gezakt.'
            : 'De totaalscore is minimaal 10 punten verslechterd sinds aankoop.',
    };
  }

  if (
    currentScore >= 82 &&
    technicalScore >= 70 &&
    (target <= 0 || price < target * 0.95) &&
    (scoreChange == null || scoreChange >= 3)
  ) {
    return {
      label: 'ADD',
      tone: 'add',
      reason:
        'Sterke actuele score, technische bevestiging en nog voldoende ruimte richting het koersdoel.',
    };
  }

  return {
    label: 'HOLD',
    tone: 'hold',
    reason:
      'De positie blijft binnen de normale bandbreedte. Geen sterke reden om nu bij te kopen of te verkopen.',
  };
}

function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="sideBrand">
        <div className="brandMark">
          <Activity size={18} />
        </div>
        <div>
          <b>
            MARKET<span>INTEL</span>
          </b>
          <small>TRADER PATTERN SCANNER</small>
        </div>
      </div>

      <nav>
        <div className="navLabel">WORKSPACE</div>
        <Link href="/" className="navItem">
          <LayoutDashboard size={16} />
          Scanner
        </Link>
        <Link href="/portfolio" className="navItem active">
          <Wallet size={16} />
          Portfolio
        </Link>
        <Link href="/history" className="navItem">
          <History size={16} />
          Alert history
        </Link>
        <Link href="/performance" className="navItem">
          <BarChart3 size={16} />
          Performance
        </Link>
        <Link href="/validation" className="navItem">
          <Target size={16} />
          Model validation
        </Link>
      </nav>

      <div className="sideBottom">
        <div className="liveStatus">
          <span className="liveDot" />
          PORTFOLIO ACTIEF
        </div>
      </div>
    </aside>
  );
}

function PositionCard({ position, result, onRemove }) {
  const price = Number(result?.price);
  const entry = Number(position.entryPrice);
  const quantity = Number(position.quantity);
  const value = Number.isFinite(price) ? price * quantity : null;
  const cost = entry * quantity;
  const gain = value != null && cost > 0 ? value - cost : null;
  const gainPct = gain != null && cost > 0 ? gain / cost : null;
  const action = actionFor(position, result);
  const target = Number(result?.analyst_target_mean);
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
        <div>
          <span>HUIDIGE KOERS</span>
          <strong>{money(price)}</strong>
        </div>
        <div>
          <span>AANKOOPPRIJS</span>
          <strong>{money(entry)}</strong>
        </div>
        <div>
          <span>AANTAL</span>
          <strong>{quantity}</strong>
        </div>
        <div>
          <span>POSITIE</span>
          <strong>{money(value)}</strong>
        </div>
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

      <div className="positionMeta">
        <span>
          Scanner score <b>{score(result?.overall_score)}</b>
        </span>
        <span>
          Technisch <b>{score(result?.technical_score)}</b>
        </span>
        <span>
          Analisten <b>{targetUpside == null ? '—' : pct(targetUpside)}</b>
        </span>
        <span>
          Koersdoel <b>{target > 0 ? money(target) : '—'}</b>
        </span>
        <button onClick={() => onRemove(position.ticker)} title="Verwijder positie">
          <X size={14} />
        </button>
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
      const response = await fetch(`/api/scan?ts=${Date.now()}`, {
        cache: 'no-store',
      });
      if (response.ok) {
        setData(await response.json());
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    const onChange = () => setPositions(read());
    window.addEventListener('marketintel-portfolio-change', onChange);
    return () => window.removeEventListener('marketintel-portfolio-change', onChange);
  }, []);

  const map = useMemo(
    () => Object.fromEntries((data?.results || []).map((result) => [result.ticker, result])),
    [data]
  );

  const stats = useMemo(() => {
    let cost = 0;
    let value = 0;

    for (const position of positions) {
      const quantity = Number(position.quantity);
      const entry = Number(position.entryPrice);
      const result = map[position.ticker];
      const price = Number(result?.price);

      cost += quantity * entry;
      if (Number.isFinite(price)) value += quantity * price;
    }

    return {
      cost,
      value,
      pnl: value - cost,
      pnlPct: cost ? value / cost - 1 : null,
    };
  }, [positions, map]);

  const remove = (ticker) => {
    const next = positions.filter((position) => position.ticker !== ticker);
    localStorage.setItem(KEY, JSON.stringify(next));
    setPositions(next);
  };

  const addCount = positions.filter(
    (position) => actionFor(position, map[position.ticker]).tone === 'add'
  ).length;
  const holdCount = positions.filter(
    (position) => actionFor(position, map[position.ticker]).tone === 'hold'
  ).length;
  const sellCount = positions.filter(
    (position) => actionFor(position, map[position.ticker]).tone === 'sell'
  ).length;

  return (
    <div className="appShell">
      <Sidebar />

      <main className="dashboard">
        <header className="topbar">
          <div>
            <div className="eyebrow">PORTFOLIO / LIVE POSITION MANAGEMENT</div>
            <h1>Mijn portfolio</h1>
            <p>
              Posities die je vanuit een BUY ALERT hebt toegevoegd, gekoppeld aan de actuele scannerdata.
            </p>
          </div>

          <div className="topActions">
            <div className="scanMeta">
              <span className="liveDot" /> SCANNER{' '}
              <b>
                {data?.generated_at
                  ? new Date(data.generated_at).toLocaleTimeString('nl-NL', {
                      hour: '2-digit',
                      minute: '2-digit',
                    })
                  : '—'}
              </b>
            </div>
            <Link href="/" className="refresh secondary">
              <LayoutDashboard size={15} /> Scanner
            </Link>
            <button className="refresh primary" onClick={load}>
              <RefreshCw size={15} /> Vernieuwen
            </button>
          </div>
        </header>

        <section className="heroGrid">
          <div className="heroPanel">
            <div>
              <span className="sectionEyebrow">PORTFOLIO OVERVIEW</span>
              <h2>Je posities in één overzicht</h2>
              <p>
                De scanner beoordeelt iedere positie opnieuw bij iedere nieuwe scan. ADD, HOLD en SELL zijn gebaseerd op scoreontwikkeling, technische sterkte en koersdoel.
              </p>
            </div>

            <div className="heroStats">
              <div>
                <span>POSITIES</span>
                <strong>{positions.length}</strong>
                <small>aandelen</small>
              </div>
              <div>
                <span>GEÏNVESTEERD</span>
                <strong>{money(stats.cost, 0)}</strong>
                <small>totale inleg</small>
              </div>
              <div>
                <span>RENDEMENT</span>
                <strong className={stats.pnl >= 0 ? 'positive' : 'negative'}>
                  {stats.pnl == null ? '—' : pct(stats.pnlPct)}
                </strong>
                <small>{stats.pnl == null ? 'geen actuele koers' : money(stats.pnl, 0)}</small>
              </div>
            </div>
          </div>

          <div className="heroSignal">
            <div className="signalHeader">
              <span>PORTFOLIO SIGNALS</span>
              <Wallet size={15} />
            </div>
            <div className="portfolioSignalSummary">
              <div>
                <strong>{addCount}</strong>
                <span>ADD</span>
              </div>
              <div>
                <strong>{holdCount}</strong>
                <span>HOLD</span>
              </div>
              <div>
                <strong>{sellCount}</strong>
                <span>SELL</span>
              </div>
            </div>
          </div>
        </section>

        <section className="sectionBlock">
          <div className="sectionHeader">
            <div>
              <div className="sectionEyebrow">01 · POSITIES</div>
              <h2>Actieve posities</h2>
              <p>De signalen zijn richtinggevend. Ze vervangen geen eigen risicobeoordeling.</p>
            </div>
            <div className="statusPill live">
              <Activity size={13} />
              {positions.length} actief
            </div>
          </div>

          {loading && !positions.length ? (
            <div className="emptyState">Portfolio laden...</div>
          ) : positions.length === 0 ? (
            <div className="emptyState alertEmpty">
              <div className="emptyIcon">
                <Wallet size={20} />
              </div>
              <strong>Nog geen posities</strong>
              <span>Open een BUY ALERT en klik op “Voeg toe aan portfolio” om een positie toe te voegen.</span>
              <Link href="/" className="refresh primary">
                <Bell size={14} /> Bekijk BUY ALERTS
              </Link>
            </div>
          ) : (
            <div className="positionGrid">
              {positions.map((position) => (
                <PositionCard
                  key={position.ticker}
                  position={position}
                  result={map[position.ticker]}
                  onRemove={remove}
                />
              ))}
            </div>
          )}
        </section>

        <section className="sectionBlock">
          <div className="sectionHeader">
            <div>
              <div className="sectionEyebrow">02 · SIGNAL LOGICA</div>
              <h2>Hoe ADD / HOLD / SELL werkt</h2>
              <p>De regels zijn bewust simpel en controleerbaar gehouden.</p>
            </div>
            <Target size={18} />
          </div>

          <div className="signalRules">
            <div>
              <span className="positionAction add">ADD</span>
              <p>
                Score ≥82, technische score ≥70 en voldoende ruimte richting het analistenkoersdoel. De score mag sinds aankoop niet fors verslechterd zijn.
              </p>
            </div>
            <div>
              <span className="positionAction hold">HOLD</span>
              <p>
                De positie blijft tussen de twee uitersten. Er is geen duidelijke reden om actief bij te kopen of te verkopen.
              </p>
            </div>
            <div>
              <span className="positionAction sell">SELL</span>
              <p>
                Score &lt;60, score minimaal 10 punten lager dan bij aankoop, of de koers zit rond het gemiddelde analistenkoersdoel terwijl je winst hebt.
              </p>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
