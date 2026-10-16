'use client';
import Link from 'next/link';
import {Activity,BarChart3,History,LayoutDashboard,ShieldCheck,Target,Wallet,AlertTriangle} from 'lucide-react';

// Bron: historische simulatie (tabellen scanner_bt2 en scanner_bt4), 2020-2026, S&P 500 + Nasdaq-100 zoals samengesteld op de dag zelf,
// 322 aandelen, 30.917 dip-signalen (model 6.1-regels), elke trade 126 handelsdagen gevolgd, netto na 0,15% kosten per kant.
// Cijfers uit de database, per 16-10-2026. Eigen lijst (168 aandelen) is hier bewust niet in verwerkt (achteraf samengesteld).
const GREEN='#35e5a0', AMBER='#f2b84b', RED='#ff7a7a', MUTED='#8da0b2', DIM='#617487', TEXT='#e6eef5';
const card={padding:'18px 20px',border:'1px solid #1d2b38',borderRadius:12,background:'#0c141c'};
const num={fontFamily:"'Space Grotesk',sans-serif",fontWeight:700};

const YEARS=[['2020',93],['2021',52],['2022',65],['2023',76],['2024',80],['2025',71],['2026',74]];
const DISCLAIMERS=[
  ['Dit is een simulatie','Het zijn historische berekeningen, geen echte trades. Echte resultaten staan vanaf 16-10-2026 op Alert history en Performance en worden daar per maand getoond.'],
  ['Gunstige periode','2020-2026 was grotendeels een stijgende markt, met een zeer sterk 2020. In een lange daling valt het resultaat lager uit. Zonder 2020 ligt het winstpercentage lager dan 70%.'],
  ['Signalen komen in clusters','De 30.917 signalen komen vooral op dagen dat de hele markt daalt. Het zijn dus veel minder onafhankelijke metingen dan het aantal doet vermoeden. Beoordeel resultaten per maand en niet per signaal.'],
  ['Geen blinde test','De regels zijn bedacht nadat we de data zagen. De periode 2024-2026 is een controle, geen echte voorspelling.'],
  ['Het beheer doet veel van het werk','Met hetzelfde beheer en een willekeurig instappunt stond ook ongeveer 73% van de trades in de plus. De dip-instap voegt vooral wat rendement toe (ongeveer +2 tot +4 procentpunt), nauwelijks winstkans.'],
  ['Verlies kan groot zijn','De slechtste 10% van de trades verloor 16% of meer na zes maanden. Er zijn geen stops: het model houdt een dalend aandeel vast en koopt bij. Een aandeel kan veel verder dalen.'],
  ['Alleen grote indexaandelen','Getest op aandelen uit de S&P 500 en Nasdaq-100 zoals die op dat moment waren, inclusief aandelen die later zijn verdwenen. Kleinere of volatielere aandelen kunnen anders uitvallen.'],
  ['Geen financieel advies','Dit is geen financieel advies en geen garantie. Beleggen brengt risico met zich mee en je kunt je inleg verliezen. Beslis altijd zelf.'],
];

function Sidebar(){return <aside className="sidebar"><div className="sideBrand"><div className="brandMark"><Activity size={18}/></div><div><b>MARKET<span>INTEL</span></b><small>TRADER PATTERN SCANNER</small></div></div><nav><div className="navLabel">WORKSPACE</div><Link href="/" className="navItem"><LayoutDashboard size={16}/>Scanner</Link><Link href="/portfolio" className="navItem"><Wallet size={16}/>Portfolio</Link><Link href="/history" className="navItem"><History size={16}/>Alert history</Link><Link href="/performance" className="navItem"><BarChart3 size={16}/>Performance</Link><Link href="/validation" className="navItem active"><Target size={16}/>Model validation</Link></nav><div className="sideBottom"><div className="liveStatus"><span className="liveDot"/>MODEL 6.2</div><div className="sideStat"><span>TESTPERIODE</span><strong>2020-26</strong></div><div className="sideStat"><span>HORIZON</span><strong>126D</strong></div></div></aside>}

function Bar({value,color=GREEN}){return <div style={{height:10,background:'#16222d',borderRadius:5,flex:1,minWidth:60}}><div style={{width:`${value}%`,height:'100%',background:color,borderRadius:5}}/></div>}
function Head({eyebrow,title,sub}){return <div className="sectionHeader"><div><div className="sectionEyebrow">{eyebrow}</div><h2>{title}</h2>{sub&&<p>{sub}</p>}</div></div>}

export default function ValidationPage(){
  return <div className="appShell"><Sidebar/><main className="dashboard">
    <header className="topbar"><div><div className="eyebrow">MODEL / VALIDATIE</div><h1>Model validation</h1><p>Zo is het model getest op historische koersdata.</p></div><div className="topActions"><Link href="/" className="refresh secondary"><LayoutDashboard size={15}/> Dashboard</Link></div></header>

    <section className="heroGrid"><div className="heroPanel"><div><span className="sectionEyebrow">HISTORISCHE SIMULATIE · 2020-2026</span><h2>Ongeveer 70% van de simulatie-trades stond na zes maanden in de plus</h2><p>Van 30.917 gesimuleerde signalen op aandelen uit de S&amp;P 500 en Nasdaq-100 stond 69,8% na zes maanden in de plus, netto na kosten. Dit zijn percentages van losse trades, geen rendement op je portfolio en geen belofte.</p></div><div className="heroStats"><div><span>TRADES IN WINST</span><strong>70%</strong><small>van 30.917 signalen</small></div><div><span>GEM. RESULTAAT PER TRADE</span><strong>+13,7%</strong><small>na zes maanden, na kosten</small></div><div><span>SLECHTSTE 10% VAN DE TRADES</span><strong>−16%</strong><small>of slechter na zes maanden</small></div></div></div>
    <div className="heroSignal"><div className="signalHeader"><span>EERSTE HELFT VS TWEEDE HELFT</span><ShieldCheck size={15}/></div><div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:12,padding:'18px 4px'}}>{[['2020-2023','68%','23.452 signalen'],['2024-2026','74%','7.465 signalen']].map(x=><div key={x[0]} style={{textAlign:'center'}}><div style={{...num,fontSize:34,color:GREEN}}>{x[1]}</div><div style={{fontSize:11,color:MUTED,marginTop:4}}>{x[0]}</div><div style={{fontSize:10,color:DIM}}>{x[2]}</div></div>)}</div></div></section>

    <section className="sectionBlock">
      <Head eyebrow="01 · METHODE" title="Hoe is dit getest?"/>
      <div style={{padding:'0 22px 22px',color:MUTED,fontSize:13,lineHeight:1.75}}>Per dag keken we welke aandelen uit de S&P 500 en Nasdaq-100 (zoals de indexen er op die dag uitzagen, dus inclusief aandelen die later verdwenen) aan de regels voldeden, op basis van koersen tot en met die dag. Elke keer dat dat gebeurde telde als één trade (30.917 in totaal, 322 aandelen, 76 maanden). Instap op de openingskoers van de volgende dag. Elke trade volgden we 126 handelsdagen (~6 maanden) met het positiebeheer van model 6.2: 10% verkopen bij +15, +30, +60 en +120%, bijkopen bij −12%, terugkopen en altijd een restpositie houden. Alle cijfers zijn netto na 0,15% kosten per kant. <b style={{color:TEXT}}>In winst</b> betekent: de trade staat na zes maanden in de plus, inclusief het nog openstaande deel tegen de slotkoers.</div>
    </section>

    <section className="sectionBlock">
      <Head eyebrow="02 · PER JAAR" title="Per jaar sterk wisselend" sub="Percentage trades in winst, per jaar van instap. Zwakste jaar: 2021 met 52%, sterkste 2020 met 93%."/>
      <div style={{padding:'4px 22px 22px',display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(110px,1fr))',gap:12}}>{YEARS.map(y=><div key={y[0]} style={card}><div style={{fontSize:11,color:DIM}}>{y[0]}</div><div style={{...num,fontSize:24,color:y[1]<65?AMBER:GREEN,margin:'4px 0 8px'}}>{y[1]}%</div><Bar value={y[1]} color={y[1]<65?AMBER:GREEN}/></div>)}</div>
    </section>

    <section className="sectionBlock">
      <Head eyebrow="03 · DISCLAIMERS" title="Lees dit voor je op de cijfers vertrouwt"/>
      <div className="signalRules" style={{gridTemplateColumns:'repeat(auto-fit,minmax(260px,1fr))'}}>{DISCLAIMERS.map(d=><div key={d[0]} style={{padding:20}}><b style={{color:AMBER,fontSize:13}}>{d[0]}</b><p style={{margin:'10px 0 0',color:MUTED,fontSize:12,lineHeight:1.65}}>{d[1]}</p></div>)}</div>
    </section>

    <footer>Model validation · model 6.2 · historische simulatie. Dit is geen financieel advies. Echte resultaten staan op <Link href="/history" style={{color:MUTED}}>Alert history</Link> en <Link href="/performance" style={{color:MUTED}}>Performance</Link>.</footer>
  </main></div>
}
