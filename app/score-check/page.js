'use client';
import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { Activity, BarChart3, History, LayoutDashboard, Target, Gauge, AlertTriangle, CheckCircle2 } from 'lucide-react';

const HORIZONS = ['5d', '10d', '20d'];
const VIEWS = [
  { key: 'combined', label: 'Trader + technical', hint: 'zoals de score nu werkt' },
  { key: 'technical_only', label: 'Alleen technical', hint: 'dislocatie, uitputting, stabilisatie' },
  { key: 'trader_only', label: 'Alleen trader', hint: 'de tweede weging van dezelfde inputs' },
];

const pct = (v, digits = 2) => (v === null || v === undefined || Number.isNaN(Number(v)) ? '—' : `${Number(v) >= 0 ? '+' : ''}${Number(v).toFixed(digits)}%`);
const num = (v) => (v === null || v === undefined ? '—' : Number(v).toLocaleString('nl-NL'));

function Sidebar() {
  return <aside className="sidebar">
    <div className="sideBrand"><div className="brandMark"><Activity size={18} /></div><div><b>MARKET<span>INTEL</span></b><small>TRADER PATTERN SCANNER</small></div></div>
    <nav>
      <div className="navLabel">WORKSPACE</div>
      <Link href="/" className="navItem"><LayoutDashboard size={16} />Scanner</Link>
      <Link href="/history" className="navItem"><History size={16} />Alert history</Link>
      <Link href="/performance" className="navItem"><BarChart3 size={16} />Performance</Link>
      <Link href="/validation" className="navItem"><Target size={16} />Model validation</Link>
      <Link href="/score-check" className="navItem active"><Gauge size={16} />Score check</Link>
    </nav>
    <div className="sideBottom">
      <div className="liveStatus"><span className="liveDot" />VOORSPELLENDE KRACHT</div>
      <div className="sideStat"><span>METHODE</span><strong>DECIELEN</strong></div>
      <div className="sideStat"><span>HORIZON</span><strong>5/10/20D</strong></div>
    </div>
  </aside>;
}

/** Diverging bars around a zero baseline. Direction carries the sign, colour reinforces it. */
function DecileChart({ deciles, horizon }) {
  const values = deciles.map((d) => d[`avg_${horizon}`]).filter((v) => v !== null && v !== undefined);
  const reach = Math.max(0.01, ...values.map((v) => Math.abs(Number(v))));
  return <div className="decileChart" role="img" aria-label={`Gemiddeld rendement na ${horizon} per scoredeciel`}>
    {deciles.map((d) => {
      const raw = d[`avg_${horizon}`];
      const value = raw === null || raw === undefined ? null : Number(raw);
      // Half the track is 50%, but the value label sits just past the bar end, so
      // the longest bar stops short of the axis to keep the label off the column.
      const width = value === null ? 0 : (Math.abs(value) / reach) * 41;
      const positive = (value ?? 0) >= 0;
      return <div className="decileRow" key={d.decile} title={`Deciel ${d.decile} · score ${d.score_from}–${d.score_to} · ${num(d.n)} waarnemingen · ${pct(value)} na ${horizon} · ${d[`win_${horizon}`] ?? '—'}% positief`}>
        <div className="decileLabel"><b>{d.decile}</b><span>{d.score_from}–{d.score_to}</span></div>
        <div className="decileTrack">
          <i className="decileZero" />
          <i className={`decileBar ${positive ? 'up' : 'down'}`} style={positive ? { left: '50%', width: `${width}%` } : { right: '50%', width: `${width}%` }} />
          <span className={`decileValue ${positive ? 'up' : 'down'}`} style={positive ? { left: `calc(50% + ${width}% + 8px)` } : { right: `calc(50% + ${width}% + 8px)` }}>{pct(value)}</span>
        </div>
        <div className="decileWin">{d[`win_${horizon}`] === null || d[`win_${horizon}`] === undefined ? '—' : `${d[`win_${horizon}`]}%`}</div>
      </div>;
    })}
  </div>;
}

function Verdict({ report, horizon }) {
  const spread = report?.[`spread_${horizon}`];
  if (spread === null || spread === undefined) return null;
  const strong = spread >= 1.0;
  const flat = Math.abs(spread) < 0.3;
  const wrong = spread <= -0.3;
  const Icon = strong ? CheckCircle2 : AlertTriangle;
  const text = wrong
    ? 'De laagste scores deden het béter dan de hoogste. De rangorde staat op zijn kop — dit model mag niet live.'
    : flat
      ? 'Hoge en lage scores presteren vrijwel gelijk. De rangorde voegt niets toe; de drempel verschuiven lost dat niet op.'
      : strong
        ? 'De hoogste scores deden het duidelijk beter dan de laagste. De rangorde voegt echte informatie toe.'
        : 'Er zit richting in, maar zwak. Bruikbaar als filter, niet als enige reden om te kopen.';
  return <div className={`verdictPanel ${wrong || flat ? 'bad' : strong ? 'good' : 'soft'}`}>
    <div className="verdictHead"><Icon size={15} /><span>OORDEEL · {horizon.toUpperCase()}</span></div>
    <strong>{pct(spread)}</strong>
    <small>verschil tussen het hoogste en het laagste deciel</small>
    <p>{text}</p>
  </div>;
}

export default function ScoreCheckPage() {
  const [data, setData] = useState(null), [loading, setLoading] = useState(true), [error, setError] = useState('');
  const [horizon, setHorizon] = useState('20d'), [view, setView] = useState('combined');

  useEffect(() => {
    fetch('/data/score_validation.json?ts=' + Date.now(), { cache: 'no-store' })
      .then(async (r) => { if (!r.ok) throw Error('Nog geen validatie gedraaid.'); setData(await r.json()); })
      .catch((e) => setError(e.message)).finally(() => setLoading(false));
  }, []);

  const report = data?.[view];
  const deciles = report?.deciles || [];
  const spreads = useMemo(() => VIEWS.map((v) => ({ ...v, spread: data?.[v.key]?.[`spread_${horizon}`] })), [data, horizon]);
  const best = useMemo(() => spreads.filter((s) => s.spread !== null && s.spread !== undefined).sort((a, b) => b.spread - a.spread)[0], [spreads]);

  return <div className="appShell"><Sidebar /><main className="dashboard">
    <header className="topbar">
      <div>
        <div className="eyebrow">MODEL / VOORSPELLENDE KRACHT</div>
        <h1>Score check</h1>
        <p>Doen aandelen met een hoge score het daarna beter dan aandelen met een lage score? Elke waarneming is een scoremoment uit het verleden, afgezet tegen wat de koers daarna deed.</p>
      </div>
      <div className="topActions">
        <div className="scanMeta"><span className="liveDot" /> MODEL <b>{data?.model_version || '—'}</b></div>
        <Link href="/" className="refresh secondary"><LayoutDashboard size={15} /> Dashboard</Link>
      </div>
    </header>

    {loading ? <div className="emptyState">Validatie laden...</div>
      : error ? <div className="emptyState alertEmpty">
          <div className="emptyIcon"><Gauge size={20} /></div>
          <strong>Nog geen validatie gedraaid</strong>
          <span>Start <b>Score Validation</b> in GitHub Actions. De run duurt ongeveer een uur en publiceert het resultaat hier automatisch.</span>
        </div>
      : <>
        <section className="heroGrid">
          <div className="heroPanel">
            <div>
              <span className="sectionEyebrow">WAT HIER GEMETEN IS</span>
              <h2>Rangorde, niet rendement</h2>
              <p>Alle scoremomenten zijn op volgorde gelegd en in tien even grote groepen geknipt. Deciel 10 is de 10% hoogste scores, deciel 1 de laagste. Fundamentals doen niet mee: daarvan bestaat geen historische data, dus meetellen zou het resultaat mooier maken dan het is.</p>
            </div>
            <div className="heroStats">
              <div><span>WAARNEMINGEN</span><strong>{num(report?.observations)}</strong><small>scoremomenten</small></div>
              <div><span>VANAF</span><strong>{data?.start || '—'}</strong><small>elke {data?.step_days || '?'}e dag</small></div>
              <div><span>UNIVERSE GEM.</span><strong>{pct(report?.[`universe_avg_${horizon}`])}</strong><small>na {horizon}</small></div>
            </div>
          </div>
          <Verdict report={report} horizon={horizon} />
        </section>

        <section className="sectionBlock">
          <div className="sectionHeader">
            <div>
              <div className="sectionEyebrow">01 · RENDEMENT PER DECIEL</div>
              <h2>Loopt het rendement op met de score?</h2>
              <p>Als de score werkt, loopt deze reeks van boven naar beneden op. De balk wijst naar rechts bij winst, naar links bij verlies.</p>
            </div>
            <div className="chartFilters">
              {HORIZONS.map((h) => <button key={h} className={`filterChip ${horizon === h ? 'on' : ''}`} onClick={() => setHorizon(h)}>{h.toUpperCase()}</button>)}
            </div>
          </div>
          <div className="chartBody">
            <div className="decileHead"><span>DECIEL</span><span>GEMIDDELD RENDEMENT NA {horizon.toUpperCase()}</span><span>POSITIEF</span></div>
            {deciles.length ? <DecileChart deciles={[...deciles].reverse()} horizon={horizon} /> : <div className="emptyState">Geen decielen in dit rapport.</div>}
          </div>
        </section>

        <section className="sectionBlock">
          <div className="sectionHeader">
            <div>
              <div className="sectionEyebrow">02 · WELKE COMPONENT VOORSPELT</div>
              <h2>Trader of technical?</h2>
              <p>Beide meten hoe hard een aandeel is gedaald en correleren onderling 0.906. Als één van de twee alleen net zo goed voorspelt als beide samen, is de ander overbodig.</p>
            </div>
          </div>
          <div className="chartBody">
            <div className="compareGrid">
              {spreads.map((s) => <button key={s.key} className={`compareCard ${view === s.key ? 'on' : ''}`} onClick={() => setView(s.key)}>
                <span>{s.label}</span>
                <strong className={Number(s.spread) >= 0 ? 'up' : 'down'}>{pct(s.spread)}</strong>
                <small>{s.hint}</small>
                {best && s.key === best.key && <i className="bestTag">sterkste</i>}
              </button>)}
            </div>
            <p className="chartNote">Getoond is het verschil tussen het hoogste en het laagste deciel na {horizon}. Klik een kaart om de decieltabel van die component te bekijken.</p>
          </div>
        </section>

        <section className="sectionBlock">
          <div className="sectionHeader">
            <div><div className="sectionEyebrow">03 · ALLE CIJFERS</div><h2>Decieltabel</h2><p>Dezelfde data als de grafiek, met alle horizonnen naast elkaar.</p></div>
          </div>
          <div className="tablewrap"><table>
            <thead><tr><th>Deciel</th><th>Score</th><th>n</th>{HORIZONS.map((h) => <th key={h}>{h.toUpperCase()} gem.</th>)}{HORIZONS.map((h) => <th key={h}>{h.toUpperCase()} win</th>)}</tr></thead>
            <tbody>{[...deciles].reverse().map((d) => <tr key={d.decile}>
              <td className="score">{d.decile}</td>
              <td>{d.score_from}–{d.score_to}</td>
              <td>{num(d.n)}</td>
              {HORIZONS.map((h) => <td key={h} className={Number(d[`avg_${h}`]) >= 0 ? 'positive' : 'negative'}>{pct(d[`avg_${h}`])}</td>)}
              {HORIZONS.map((h) => <td key={h}>{d[`win_${h}`] === null || d[`win_${h}`] === undefined ? '—' : `${d[`win_${h}`]}%`}</td>)}
            </tr>)}</tbody>
          </table></div>
        </section>

        <footer>{data?.note} · model {data?.model_version} · dit is historie, geen belofte over de toekomst</footer>
      </>}

    {/* global: DecileChart and Verdict are separate components, and styled-jsx
        only scopes the JSX of the component that declares the block. */}
    <style jsx global>{`
      .chartBody{padding:18px 21px 22px}
      .chartFilters{display:flex;gap:6px}
      .filterChip{padding:7px 11px;border:1px solid var(--line2);border-radius:8px;background:#101820;color:#8a99a9;font-size:8px;font-weight:800;letter-spacing:.08em;cursor:pointer}
      .filterChip.on{color:var(--green);border-color:#2b664d;background:#0e1d17}
      .decileHead{display:grid;grid-template-columns:96px 1fr 62px;gap:12px;padding:0 0 10px;color:#5d6e80;font-size:7px;font-weight:800;letter-spacing:.14em}
      .decileHead span:last-child{text-align:right}
      .decileChart{display:flex;flex-direction:column;gap:2px}
      .decileRow{display:grid;grid-template-columns:96px 1fr 62px;gap:12px;align-items:center}
      .decileLabel{display:flex;align-items:baseline;gap:7px}
      .decileLabel b{font-family:'Space Grotesk',sans-serif;font-size:13px}
      .decileLabel span{color:#5d6e80;font-size:8px}
      .decileTrack{position:relative;height:22px}
      .decileZero{position:absolute;left:50%;top:0;bottom:0;width:1px;background:#2a3b4d}
      .decileBar{position:absolute;top:5px;height:12px;min-width:2px}
      .decileBar.up{background:#35e5a0;border-radius:0 4px 4px 0}
      .decileBar.down{background:#ff6f7d;border-radius:4px 0 0 4px}
      .decileValue{position:absolute;top:4px;font-family:'Space Grotesk',sans-serif;font-size:10px;white-space:nowrap}
      .decileValue.up{color:#7ef0c2}
      .decileValue.down{color:#ffa3ac}
      .decileWin{text-align:right;color:#8797aa;font-size:10px;font-family:'Space Grotesk',sans-serif}
      .verdictPanel{border:1px solid var(--line);border-radius:15px;padding:22px;background:linear-gradient(145deg,#101720,#0a1017);display:flex;flex-direction:column;justify-content:center;min-height:176px}
      .verdictPanel.good{border-color:#2b664d}
      .verdictPanel.bad{border-color:#6b3540}
      .verdictHead{display:flex;align-items:center;gap:7px;color:#65788d;font-size:7px;font-weight:800;letter-spacing:.14em}
      .verdictPanel.good .verdictHead svg{color:var(--green)}
      .verdictPanel.bad .verdictHead svg{color:var(--red)}
      .verdictPanel.soft .verdictHead svg{color:var(--amber)}
      .verdictPanel strong{font-family:'Space Grotesk',sans-serif;font-size:38px;letter-spacing:-.045em;margin-top:12px;line-height:1}
      .verdictPanel.good strong{color:#7ef0c2}
      .verdictPanel.bad strong{color:#ffa3ac}
      .verdictPanel small{color:#617487;font-size:8px;margin-top:7px}
      .verdictPanel p{margin:13px 0 0;color:#8fa0b2;font-size:10px;line-height:1.55}
      .compareGrid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:11px}
      .compareCard{position:relative;text-align:left;border:1px solid var(--line2);border-radius:11px;padding:16px;background:#0d141d;color:inherit;font:inherit;cursor:pointer;transition:.18s}
      .compareCard.on{border-color:#2b664d;background:#0e1d17}
      .compareCard:hover{transform:translateY(-2px)}
      .compareCard:focus-visible{outline:2px solid var(--cyan);outline-offset:2px}
      .compareCard>span{display:block;color:#8797aa;font-size:8px;font-weight:800;letter-spacing:.1em}
      .compareCard strong{display:block;margin-top:9px;font-family:'Space Grotesk',sans-serif;font-size:25px;letter-spacing:-.04em}
      .compareCard strong.up{color:#7ef0c2}
      .compareCard strong.down{color:#ffa3ac}
      .compareCard small{display:block;margin-top:6px;color:#5d6e80;font-size:8px}
      .bestTag{position:absolute;right:12px;top:12px;font-style:normal;font-size:7px;font-weight:800;letter-spacing:.09em;color:var(--green);border:1px solid #2b664d;background:#0e1d17;border-radius:5px;padding:3px 6px}
      .chartNote{margin:14px 0 0;color:#617487;font-size:9px}
      @media(max-width:860px){.compareGrid{grid-template-columns:1fr}.decileRow,.decileHead{grid-template-columns:78px 1fr 48px}}
    `}</style>
  </main></div>;
}
