'use client';
import Link from 'next/link';
import {Activity,BarChart3,History,LayoutDashboard,ShieldCheck,Target,Wallet,AlertTriangle} from 'lucide-react';

// Bron: historische simulatie (tabel scanner_bt_pos), 2020-2026, 232 aandelen, 8.711 dip-trades,
// elke trade 126 handelsdagen (~6 maanden) gevolgd met het positiebeheer van het model.
const GREEN='#35e5a0', AMBER='#f2b84b', RED='#ff7a7a', MUTED='#8da0b2', DIM='#617487', TEXT='#e6eef5';
const card={padding:'18px 20px',border:'1px solid #1d2b38',borderRadius:12,background:'#0c141c'};
const num={fontFamily:"'Space Grotesk',sans-serif",fontWeight:700};

const COMPARE=[
  {name:'Kopen en vasthouden',win:66,main:false},
  {name:'Alleen winst nemen',win:70,main:false},
  {name:'Ons model: winst nemen, bijkopen, terugkopen',win:79,main:true},
];
const YEARS=[['2020',96],['2021',69],['2022',73],['2023',84],['2024',76],['2025',80],['2026',82]];
const DISCLAIMERS=[
  ['Gunstige periode','2020-2026 was grotendeels een stijgende markt. In een lange daling valt het resultaat lager uit.'],
  ['Geen blinde test','De regels zijn bedacht nadat we de data zagen. De periode 2024-2026 is een controle op stabiliteit, geen echte voorspelling.'],
  ['Het beheer doet veel van het werk','Met hetzelfde beheer en een willekeurig instappunt was 78% van de trades in de plus. De dip-instap voegt vooral rendement toe (+20% per trade tegen +16%).'],
  ['Verwachting','In een gewoon jaar: ongeveer 70-75% van de trades in de plus, geen 79%. Geen garantie voor de toekomst.'],
  ['Geen financieel advies','Dit is geen financieel advies. Beleggen brengt risico met zich mee en je kunt je inleg verliezen. Beslis altijd zelf.'],
];

function Sidebar(){return <aside className="sidebar"><div className="sideBrand"><div className="brandMark"><Activity size={18}/></div><div><b>MARKET<span>INTEL</span></b><small>TRADER PATTERN SCANNER</small></div></div><nav><div className="navLabel">WORKSPACE</div><Link href="/" className="navItem"><LayoutDashboard size={16}/>Scanner</Link><Link href="/portfolio" className="navItem"><Wallet size={16}/>Portfolio</Link><Link href="/history" className="navItem"><History size={16}/>Alert history</Link><Link href="/performance" className="navItem"><BarChart3 size={16}/>Performance</Link><Link href="/validation" className="navItem active"><Target size={16}/>Model validation</Link></nav><div className="sideBottom"><div className="liveStatus"><span className="liveDot"/>ASCENT 6.0</div><div className="sideStat"><span>TESTPERIODE</span><strong>2020-26</strong></div><div className="sideStat"><span>HORIZON</span><strong>126D</strong></div></div></aside>}

function Bar({value,color=GREEN}){return <div style={{height:10,background:'#16222d',borderRadius:5,flex:1,minWidth:60}}><div style={{width:`${value}%`,height:'100%',background:color,borderRadius:5}}/></div>}
function Head({eyebrow,title,sub}){return <div className="sectionHeader"><div><div className="sectionEyebrow">{eyebrow}</div><h2>{title}</h2>{sub&&<p>{sub}</p>}</div></div>}

export default function ValidationPage(){
  return <div className="appShell"><Sidebar/><main className="dashboard">
    <header className="topbar"><div><div className="eyebrow">MODEL / VALIDATIE</div><h1>Model validation</h1><p>Zo is het Ascent-model getest op historische koersdata.</p></div><div className="topActions"><Link href="/" className="refresh secondary"><LayoutDashboard size={15}/> Dashboard</Link></div></header>

    <section className="heroGrid"><div className="heroPanel"><div><span className="sectionEyebrow">HISTORISCHE TEST · 2020-2026</span><h2>79% van de trades eindigde in winst</h2><p>Van de 8.711 testtrades stond 79% na zes maanden in de plus. Dit zijn percentages van losse trades, geen rendement op je portfolio. Vergelijking: kopen en vasthouden haalde 66%.</p></div><div className="heroStats"><div><span>TRADES IN WINST</span><strong>79%</strong><small>van 8.711 trades</small></div><div><span>GEM. RESULTAAT PER TRADE</span><strong>+20%</strong><small>na zes maanden</small></div><div><span>TYPISCHE TUSSENTIJDSE DALING</span><strong>−12%</strong><small>per trade</small></div></div></div>
    <div className="heroSignal"><div className="signalHeader"><span>STABIEL OVER TIJD</span><ShieldCheck size={15}/></div><div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:12,padding:'18px 4px'}}>{[['2020-2023','4.763 trades'],['2024-2026','3.948 trades']].map(x=><div key={x[0]} style={{textAlign:'center'}}><div style={{...num,fontSize:34,color:GREEN}}>79%</div><div style={{fontSize:11,color:MUTED,marginTop:4}}>{x[0]}</div><div style={{fontSize:10,color:DIM}}>{x[1]}</div></div>)}</div></div></section>

    <section className="sectionBlock">
      <Head eyebrow="01 · METHODE" title="Hoe is dit getest?"/>
      <div style={{padding:'0 22px 22px',color:MUTED,fontSize:13,lineHeight:1.75}}>Per dag keken we welke van 232 aandelen aan de Ascent-regels voldeden, op basis van koersen tot en met die dag. Elke keer dat dat gebeurde telde als één trade (8.711 in totaal). Elke trade volgden we 126 handelsdagen (~6 maanden) met het positiebeheer van het model: 20% verkopen bij +10, +25, +50 en +100%, bijkopen bij −12%, terugkopen en altijd een restpositie houden. <b style={{color:TEXT}}>In winst</b> betekent: de trade staat na zes maanden in de plus.</div>
    </section>

    <section className="sectionBlock">
      <Head eyebrow="02 · VERGELIJKING" title="Beter dan alleen kopen en vasthouden" sub="Percentage trades in winst na zes maanden, voor dezelfde instappunten."/>
      <div style={{padding:'4px 22px 22px',display:'grid',gap:14}}>{COMPARE.map(c=><div key={c.name} style={{display:'grid',gridTemplateColumns:'minmax(150px,1.2fr) 3fr 50px',alignItems:'center',gap:12}}><span style={{color:c.main?TEXT:MUTED,fontSize:13,fontWeight:c.main?700:400}}>{c.name}</span><Bar value={c.win} color={c.main?GREEN:'#4f6b82'}/><b style={{...num,color:c.main?GREEN:TEXT,textAlign:'right'}}>{c.win}%</b></div>)}</div>
    </section>

    <section className="sectionBlock">
      <Head eyebrow="03 · PER JAAR" title="In elk jaar de meeste trades in winst" sub="Percentage trades in winst, per jaar van instap. Zwakste jaar: 2021 met 69%."/>
      <div style={{padding:'4px 22px 22px',display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(110px,1fr))',gap:12}}>{YEARS.map(y=><div key={y[0]} style={card}><div style={{fontSize:11,color:DIM}}>{y[0]}</div><div style={{...num,fontSize:24,color:y[1]<70?AMBER:GREEN,margin:'4px 0 8px'}}>{y[1]}%</div><Bar value={y[1]} color={y[1]<70?AMBER:GREEN}/></div>)}</div>
    </section>

    <section className="sectionBlock">
      <Head eyebrow="04 · DISCLAIMERS" title="Lees dit voor je op de cijfers vertrouwt"/>
      <div className="signalRules" style={{gridTemplateColumns:'repeat(auto-fit,minmax(240px,1fr))'}}>{DISCLAIMERS.map(d=><div key={d[0]} style={{padding:20}}><b style={{color:AMBER,fontSize:13}}>{d[0]}</b><p style={{margin:'10px 0 0',color:MUTED,fontSize:12,lineHeight:1.65}}>{d[1]}</p></div>)}</div>
    </section>

    <footer>Model validation · Ascent-model 6.0 · historische simulatie. Dit is geen financieel advies. Echte resultaten staan op <Link href="/history" style={{color:MUTED}}>Alert history</Link> en <Link href="/performance" style={{color:MUTED}}>Performance</Link>.</footer>
  </main></div>
}
