'use client';
import {useEffect,useMemo,useState} from 'react';
import Link from 'next/link';
import {Activity,BarChart3,Database,History,LayoutDashboard,ShieldCheck,Target,TrendingUp,ArrowUpRight} from 'lucide-react';

const pct=v=>v==null||!Number.isFinite(Number(v))?'—':`${(Number(v)*100).toFixed(1)}%`;
const ret=v=>v==null||!Number.isFinite(Number(v))?'—':`${Number(v)>=0?'+':''}${(Number(v)*100).toFixed(2)}%`;
const bands=['80-84','85-89','90+'];
const horizons=['1d','5d','10d','20d','30d','60d'];

const stat=(obj,h)=>{
  const n=obj?.[`n_${h}`];
  const v=obj?.[`winrate_${h}`];
  return n==null&&v==null?'—':`${n??'—'} · ${pct(v)}`;
};

const returnStat=(obj,h)=>{
  const n=obj?.[`n_${h}`];
  const v=obj?.[`avg_return_${h}`];
  return n==null&&v==null?'—':`${n??'—'} · ${ret(v)}`;
};

function rankValues(items){
  const valid=items.filter(x=>x.value!=null&&Number.isFinite(Number(x.value))).sort((a,b)=>Number(b.value)-Number(a.value));
  const ranks={};
  valid.forEach((x,i)=>{if(i<6)ranks[x.key]=i===0?'best':'top';});
  return ranks;
}

function cellStyle(rank){
  if(rank==='best'){
    return {background:'rgba(53,229,160,.16)',border:'1px solid rgba(53,229,160,.55)',color:'#8ff5c2',boxShadow:'inset 0 0 18px rgba(53,229,160,.05)'};
  }
  if(rank==='top'){
    return {background:'rgba(255,189,102,.12)',border:'1px solid rgba(255,189,102,.42)',color:'#ffd08d',boxShadow:'inset 0 0 18px rgba(255,189,102,.035)'};
  }
  return {};
}

function RankedCell({rank,children}){
  return <td style={{...cellStyle(rank),transition:'background .18s,border-color .18s'}}>{children}</td>;
}

function Legend(){return <div style={{display:'flex',alignItems:'center',gap:14,marginTop:10,color:'#6f8092',fontSize:8,fontWeight:700,letterSpacing:'.04em'}}><span style={{display:'inline-flex',alignItems:'center',gap:5}}><i style={{width:8,height:8,borderRadius:2,background:'rgba(53,229,160,.65)',border:'1px solid rgba(53,229,160,.8)'}}/> Beste resultaat</span><span style={{display:'inline-flex',alignItems:'center',gap:5}}><i style={{width:8,height:8,borderRadius:2,background:'rgba(255,189,102,.58)',border:'1px solid rgba(255,189,102,.72)'}}/> Volgende 5</span></div>}

function Sidebar(){return <aside className="sidebar"><div className="sideBrand"><div className="brandMark"><Activity size={18}/></div><div><b>MARKET<span>INTEL</span></b><small>TRADER PATTERN SCANNER</small></div></div><nav><div className="navLabel">WORKSPACE</div><Link href="/" className="navItem"><LayoutDashboard size={16}/>Scanner</Link><Link href="/history" className="navItem"><History size={16}/>Alert history</Link><Link href="/performance" className="navItem"><BarChart3 size={16}/>Performance</Link><Link href="/validation" className="navItem active"><Target size={16}/>Model validation</Link></nav><div className="sideBottom"><div className="liveStatus"><span className="liveDot"/>MODEL CHECK ACTIEF</div><div className="sideStat"><span>VALIDATIETYPE</span><strong>OOS</strong></div><div className="sideStat"><span>HORIZON</span><strong>60D</strong></div></div></aside>}

function ReturnTable({thresholds}){
  const ranks=useMemo(()=>rankValues(['80','85','90'].flatMap(k=>horizons.map(h=>({key:`${k}:${h}`,value:thresholds[k]?.[`avg_return_${h}`]})))),[thresholds]);
  return <section className="sectionBlock"><div className="sectionHeader"><div><div className="sectionEyebrow">02 · RENDEMENT</div><h2>Werkelijk rendement per signaal</h2><p>Gemiddeld rendement per afzonderlijk signaal, inclusief winnaars en verliezers. Per cel staat eerst het aantal complete observaties en daarna het gemiddelde rendement.</p><Legend/></div><TrendingUp size={18}/></div><div className="tablewrap"><table><thead><tr><th>Drempel</th><th>Signalen</th>{horizons.map(h=><th key={h}>N · Gem. {h.toUpperCase()}</th>)}</tr></thead><tbody>{['80','85','90'].map(k=><tr key={k}><td className="score">{k}+</td><td>{thresholds[k]?.alerts??'—'}</td>{horizons.map(h=><RankedCell key={h} rank={ranks[`${k}:${h}`]}>{returnStat(thresholds[k],h)}</RankedCell>)}</tr>)}</tbody></table></div></section>
}

export default function ValidationPage(){
  const[data,setData]=useState(null),[loading,setLoading]=useState(true),[error,setError]=useState('');
  useEffect(()=>{fetch('/data/walk_forward_validation.json?ts='+Date.now(),{cache:'no-store'}).then(async r=>{if(!r.ok)throw Error('Nog geen walk-forward validatieresultaat gepubliceerd. Start een handmatige GitHub Actions-run.');setData(await r.json())}).catch(e=>setError(e.message)).finally(()=>setLoading(false))},[]);
  const thresholds=data?.thresholds||{};
  const scoreBands=data?.score_bands||{};

  const thresholdWinRanks=useMemo(()=>rankValues(['80','85','90'].flatMap(k=>horizons.map(h=>({key:`${k}:${h}`,value:thresholds[k]?.[`winrate_${h}`]})))),[thresholds]);
  const bandWinRanks=useMemo(()=>Object.fromEntries(['5d','20d','30d','60d'].map(h=>[h,rankValues(bands.map(k=>({key:k,value:scoreBands[k]?.[`winrate_${h}`]})))])),[scoreBands]);
  const bandReturnRanks=useMemo(()=>rankValues(bands.map(k=>({key:k,value:scoreBands[k]?.avg_return_60d}))),[scoreBands]);
  const bandMedianRanks=useMemo(()=>rankValues(bands.map(k=>({key:k,value:scoreBands[k]?.median_return_60d}))),[scoreBands]);

  return <div className="appShell"><Sidebar/><main className="dashboard"><header className="topbar"><div><div className="eyebrow">MODEL / OUT-OF-SAMPLE VALIDATION</div><h1>Model validation</h1><p>Historische controle van het trader-pattern model. Elke evaluatiedag wordt alleen getraind met informatie die op dat moment beschikbaar was.</p></div><div className="topActions"><div className="scanMeta"><span className="liveDot"/> MODEL <b>{data?'GEVALIDEERD':'WACHT OP DATA'}</b></div><Link href="/" className="refresh secondary"><LayoutDashboard size={15}/> Dashboard</Link></div></header>{loading?<div className="emptyState">Validatie laden...</div>:error?<div className="error">{error}</div>:<>
    <section className="heroGrid"><div className="heroPanel"><div><span className="sectionEyebrow">OUT-OF-SAMPLE CONTROL</span><h2>Hoe betrouwbaar is de score?</h2><p>We testen iedere beschikbare markt-dag zodra er genoeg eerdere trader-observaties zijn om een model te trainen. Vervolgens wordt de volledige beschikbare aandelenlijst gescoord. Alle scenario's worden bewaard voor analyse.</p></div><div className="heroStats"><div><span>SCENARIO'S</span><strong>{data.scenarios??data.observations}</strong><small>aandeel × evaluatiedag</small></div><div><span>80+ SIGNALEN</span><strong>{data.alerts_80_plus??data.observations}</strong><small>historische alerts</small></div><div><span>OOS DAGEN</span><strong>{data.evaluated_dates??data.unique_dates}</strong><small>met getraind model</small></div></div></div><div className="heroSignal"><div className="signalHeader"><span>VALIDATION STATUS</span><ShieldCheck size={15}/></div><div className="convictionBody"><div className="performanceBig"><strong>OOS</strong><span>walk-forward</span></div><div><strong>{Math.round(data.average_positive_training_observations||0)}</strong><span>gem. positieve voorbeelden</span><small>per evaluatiedag</small></div></div></div></section>
    <section className="kpiGrid"><div className="kpiCard"><div className="kpiIcon"><Database size={17}/></div><div><span>SCENARIO'S</span><strong>{data.scenarios??data.observations}</strong><small>volledig opgeslagen</small></div><ArrowUpRight size={15}/></div><div className="kpiCard"><div className="kpiIcon blue"><Target size={17}/></div><div><span>OOS DAGEN</span><strong>{data.evaluated_dates??data.unique_dates}</strong><small>dagelijkse validatie</small></div><ArrowUpRight size={15}/></div><div className="kpiCard"><div className="kpiIcon purple"><TrendingUp size={17}/></div><div><span>TICKERS</span><strong>{data.unique_tickers}</strong><small>geteste bedrijven</small></div><ArrowUpRight size={15}/div><div className="kpiCard"><div className="kpiIcon"><ShieldCheck size={17}/></div><div><span>TRAINING</span><strong>{Math.round(data.average_positive_training_observations||0)}</strong><small>gem. positieve voorbeelden</small></div><ArrowUpRight size={15}/></div></section>
    <section className="sectionBlock"><div className="sectionHeader"><div><div className="sectionEyebrow">01 · DREMPELTEST</div><h2>Winrate per alertdrempel</h2><p>Percentage signalen met een positief rendement op elk meetmoment. 1D t/m 30D zijn handelsdagen. 60D is 60 kalenderdagen. Per cel staat <strong>N · winrate</strong>, zodat kleine steekproeven zichtbaar blijven.</p><Legend/></div><ShieldCheck size={18}/></div><div className="tablewrap"><table><thead><tr><th>Drempel</th><th>Signalen</th>{horizons.map(h=><th key={h}>N · {h.toUpperCase()}</th>)}</tr></thead><tbody>{['80','85','90'].map(k=><tr key={k}><td className="score">{k}+</td><td>{thresholds[k]?.alerts??'—'}</td>{horizons.map(h=><RankedCell key={h} rank={thresholdWinRanks[`${k}:${h}`]}>{stat(thresholds[k],h)}</RankedCell>)}</tr>)}</tbody></table></div></section>
    <ReturnTable thresholds={thresholds}/>
    <section className="sectionBlock"><div className="sectionHeader"><div><div className="sectionEyebrow">03 · SCOREKALIBRATIE</div><h2>Score versus werkelijk rendement</h2><p>Alleen scores vanaf 80 zijn relevant voor een trade. Per uitkomstkolom is de beste score groen en zijn de volgende twee oranje. Elke cel toont eerst het aantal complete observaties en daarna de uitkomst.</p><Legend/></div><BarChart3 size={18}/></div><div className="tablewrap"><table><thead><tr><th>Score</th><th>Scenario's</th><th>N · 5D winrate</th><th>N · 20D winrate</th><th>N · 30D winrate</th><th>N · 60D winrate</th><th>N · Gem. 60D</th><th>N · Mediaan 60D</th></tr></thead><tbody>{bands.map(k=><tr key={k}><td className="score">{k}</td><td>{scoreBands[k]?.scenarios??'—'}</td><RankedCell rank={bandWinRanks['5d']?.[k]}>{stat(scoreBands[k],'5d')}</RankedCell><RankedCell rank={bandWinRanks['20d']?.[k]}>{stat(scoreBands[k],'20d')}</RankedCell><RankedCell rank={bandWinRanks['30d']?.[k]}>{stat(scoreBands[k],'30d')}</RankedCell><RankedCell rank={bandWinRanks['60d']?.[k]}>{stat(scoreBands[k],'60d')}</RankedCell><RankedCell rank={bandReturnRanks[k]}>{returnStat(scoreBands[k],'60d')}</RankedCell><RankedCell rank={bandMedianRanks[k]}>{scoreBands[k]?.n_60d==null||scoreBands[k]?.median_return_60d==null?'—':`${scoreBands[k].n_60d} · ${ret(scoreBands[k].median_return_60d)}`}</RankedCell></tr>)}</tbody></table></div></section>
    <section className="sectionBlock"><div className="sectionHeader"><div><div className="sectionEyebrow">04 · DATAVEILIGHEID</div><h2>Wat is wel en niet gevalideerd?</h2><p>De trader-pattern en technische componenten zijn out-of-sample getest. Fundamentals worden niet gebruikt in deze historische score, omdat betrouwbare point-in-time fundamentele data niet beschikbaar is. Daardoor valideert deze pagina niet één-op-één de volledige live score van 45% trader, 25% techniek en 30% fundamentals.</p></div><Target size={18}/></div></section>
    <section className="sectionBlock"><div className="sectionHeader"><div><div className="sectionEyebrow">05 · METHODOLOGIE</div><h2>Hoe de validatie werkt</h2><p>{data.method}</p></div><Target size={18}/></div></section>
  </>}</main></div>
}
