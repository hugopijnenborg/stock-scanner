'use client';
import Link from 'next/link';
import {Activity,BarChart3,History,LayoutDashboard,ShieldCheck,Target,TrendingUp,Wallet,AlertTriangle} from 'lucide-react';

// Resultaten van de historische simulatie (2020-2026, 232 aandelen, ~29.000 instappunten, 126 handelsdagen vooruit).
const CONFIGS=[
  {name:'Kopen en vasthouden',win:'66%',avg:'+19%',dd:'—',note:'Basislijn: je koopt bij het dip-signaal en doet niets.'},
  {name:'Alleen winst nemen',win:'70%',avg:'+14%',dd:'—',note:'Trapsgewijs 20% verkopen bij +10, +25, +50 en +100%.'},
  {name:'Winst nemen + bijkopen + terugkopen',win:'79%',avg:'+20%',dd:'−12%',note:'Het model dat de app gebruikt. Altijd een restpositie.',main:true},
  {name:'Zelfde beheer, willekeurig instappunt',win:'78%',avg:'+16%',dd:'—',note:'Bijna hetzelfde winstpercentage: het beheer doet veel van het werk. De dip-instap voegt vooral rendement toe (+20% tegen +16%).'},
];
const YEARS=[['2020','96%'],['2021','69%'],['2022','73%'],['2023','84%'],['2024','76%'],['2025','80%'],['2026','82%']];
const FINDINGS=[
  ['Diepere dips geven meer rendement en meer schommeling','Meer dan 50% onder de 52-wekentop: gemiddeld +28%, maar ook een diepste daling van gemiddeld −18%. Het winstpercentage verandert nauwelijks.'],
  ['Hoge omzetgroei','Bij meer dan 25% omzetgroei stond 75% van de posities in de plus, met meer schommeling. Dit is de reden voor het profiel “agressief”.'],
  ['Rode of groene dag maakt niet uit','Instappen op een rode dag gaf geen ander resultaat dan op een groene dag. Dit is daarom geen regel.'],
  ['Winst nemen: verder laten lopen','Na een winstniveau (+10/25/50%) steeg het aandeel gemiddeld nog +8,5/+9,9/+11,8% in drie maanden, ongeveer de normale groei. Bij sterk momentum (meer dan 12% boven het 20-daags gemiddelde) was dat +13 tot +15% tegen +4 tot +8%, met grote uitschieters.'],
  ['Bijkopen na −12%','Na een daling van 12% of meer steeg het aandeel gemiddeld +13% in drie maanden. Dit cijfer is opgeblazen omdat we alleen aandelen testen die nog bestaan.'],
];
const CAVEATS=[
  'Alleen aandelen die nu nog in de lijst staan. Bedrijven die zijn omgevallen of uit de lijst zijn gegaan ontbreken, dat maakt de cijfers te mooi.',
  '2020-2026 was grotendeels een stijgende markt. In een lange daling kan het winstpercentage lager uitvallen.',
  'De instappunten overlappen in de tijd, dus de ~29.000 uitkomsten zijn minder onafhankelijk dan het aantal doet vermoeden.',
  'De regels zijn bedacht nadat we de data hadden gezien. De test op de periode 2024-2026 (79%) is dezelfde uitkomst als op 2020-2023 (79%), maar blijft geen echte test vooruit.',
  'Cijfers, analisten en nieuws zijn niet historisch getoetst, omdat die data niet per datum beschikbaar is. Ze staan in de app als context en lossen geen signaal uit.',
  'Realistische verwachting in een gewoon jaar: 70-75% winstgevende posities, geen 79%.',
];

function Sidebar(){return <aside className="sidebar"><div className="sideBrand"><div className="brandMark"><Activity size={18}/></div><div><b>MARKET<span>INTEL</span></b><small>TRADER PATTERN SCANNER</small></div></div><nav><div className="navLabel">WORKSPACE</div><Link href="/" className="navItem"><LayoutDashboard size={16}/>Scanner</Link><Link href="/portfolio" className="navItem"><Wallet size={16}/>Portfolio</Link><Link href="/history" className="navItem"><History size={16}/>Alert history</Link><Link href="/performance" className="navItem"><BarChart3 size={16}/>Performance</Link><Link href="/validation" className="navItem active"><Target size={16}/>Model validation</Link></nav><div className="sideBottom"><div className="liveStatus"><span className="liveDot"/>MODEL 6.0 DIP</div><div className="sideStat"><span>TESTPERIODE</span><strong>2020-26</strong></div><div className="sideStat"><span>HORIZON</span><strong>126D</strong></div></div></aside>}

export default function ValidationPage(){
  return <div className="appShell"><Sidebar/><main className="dashboard">
    <header className="topbar"><div><div className="eyebrow">MODEL / VALIDATIE</div><h1>Model validation</h1><p>Hoe het dip-model en het positiebeheer presteerden op historische koersdata (2020-2026).</p></div><div className="topActions"><Link href="/" className="refresh secondary"><LayoutDashboard size={15}/> Dashboard</Link></div></header>

    <section className="heroGrid"><div className="heroPanel"><div><span className="sectionEyebrow">HISTORISCHE TEST</span><h2>79% van de posities in de plus</h2><p>Instappen op een dip volgens de regels van de scanner, daarna winst nemen in stappen, bijkopen, terugkopen en een restpositie houden. Zes maanden vooruit gemeten, bij ongeveer 29.000 instappunten.</p></div><div className="heroStats"><div><span>WINSTPERCENTAGE</span><strong>79%</strong><small>kopen en vasthouden: 66%</small></div><div><span>GEM. RENDEMENT</span><strong>+20%</strong><small>in 126 handelsdagen</small></div><div><span>DIEPSTE DALING</span><strong>−12%</strong><small>tussentijds, typisch</small></div></div></div>
    <div className="heroSignal"><div className="signalHeader"><span>TRAIN VERSUS TEST</span><ShieldCheck size={15}/></div><div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:12,padding:'18px 4px'}}>{[['2020-2023','training'],['2024-2026','test']].map(x=><div key={x[0]} style={{textAlign:'center'}}><div style={{fontFamily:"'Space Grotesk',sans-serif",fontSize:34,fontWeight:700,color:'#35e5a0'}}>79%</div><div style={{fontSize:11,color:'#8da0b2',marginTop:4}}>{x[0]}</div><div style={{fontSize:10,color:'#617487'}}>{x[1]}</div></div>)}</div></div></section>

    <section className="sectionBlock"><div className="sectionHeader"><div><div className="sectionEyebrow">01 · VERGELIJKING</div><h2>Welke aanpak werkt het best?</h2><p>Dezelfde instappunten, vier manieren van beheren.</p></div><TrendingUp size={18}/></div><div className="tablewrap"><table><thead><tr><th>Aanpak</th><th>In de plus</th><th>Gem. rendement</th><th>Diepste daling</th><th>Toelichting</th></tr></thead><tbody>{CONFIGS.map(c=><tr key={c.name} style={c.main?{background:'rgba(53,229,160,.07)'}:undefined}><td className="score">{c.name}</td><td>{c.win}</td><td>{c.avg}</td><td>{c.dd}</td><td style={{whiteSpace:'normal',minWidth:260}}>{c.note}</td></tr>)}</tbody></table></div></section>

    <section className="sectionBlock"><div className="sectionHeader"><div><div className="sectionEyebrow">02 · PER JAAR</div><h2>Winstpercentage per instapjaar</h2><p>Het beheermodel met dip-instap. Het slechtste jaar (2021) kwam uit op 69%.</p></div><BarChart3 size={18}/></div><div className="tablewrap"><table><thead><tr><th>Jaar</th>{YEARS.map(y=><th key={y[0]}>{y[0]}</th>)}</tr></thead><tbody><tr><td className="score">In de plus</td>{YEARS.map(y=><td key={y[0]}>{y[1]}</td>)}</tr></tbody></table></div></section>

    <section className="sectionBlock"><div className="sectionHeader"><div><div className="sectionEyebrow">03 · BEVINDINGEN</div><h2>Wat we over de regels leerden</h2></div><Target size={18}/></div><div className="signalRules" style={{gridTemplateColumns:'repeat(auto-fit,minmax(260px,1fr))'}}>{FINDINGS.map(f=><div key={f[0]} style={{padding:20}}><b style={{color:'#e6eef5',fontSize:13}}>{f[0]}</b><p style={{margin:'10px 0 0',color:'#8da0b2',fontSize:12,lineHeight:1.65}}>{f[1]}</p></div>)}</div></section>

    <section className="sectionBlock"><div className="sectionHeader"><div><div className="sectionEyebrow">04 · BEPERKINGEN</div><h2>Lees dit voor je op de cijfers vertrouwt</h2></div><AlertTriangle size={18}/></div><div style={{padding:'6px 22px 22px'}}><ul style={{margin:0,paddingLeft:18,color:'#9fb0bf',fontSize:13,lineHeight:1.8}}>{CAVEATS.map(c=><li key={c}>{c}</li>)}</ul></div></section>

    <footer>Model validation · dip-model 6.0 · historische simulatie, geen garantie voor de toekomst. Echte resultaten staan op de pagina’s Alert history en Performance.</footer>
  </main></div>
}
