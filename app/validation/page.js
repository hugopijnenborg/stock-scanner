'use client';
import Link from 'next/link';
import {Activity,BarChart3,History,LayoutDashboard,ShieldCheck,Target,TrendingUp,Wallet,AlertTriangle,FlaskConical,Layers,CheckCircle2} from 'lucide-react';

// Alle cijfers komen uit de historische simulatie (tabel scanner_bt_pos): 2020-2026, 232 aandelen,
// 8.711 dip-instappen en 23.232 willekeurige instappen, 126 handelsdagen (~6 maanden) vooruit gemeten.
const GREEN='#35e5a0', AMBER='#f2b84b', RED='#ff7a7a', MUTED='#8da0b2', DIM='#617487', TEXT='#e6eef5';
const cardStyle={padding:'18px 20px',border:'1px solid #1d2b38',borderRadius:12,background:'#0c141c'};
const num={fontFamily:"'Space Grotesk',sans-serif",fontWeight:700};

// 1. Waar vergelijken we mee? (zelfde 8.711 dip-instappen, vier manieren van beheren; laatste regel = willekeurige instap)
const CONFIGS=[
  {name:'Kopen en vasthouden',win:66,avg:'+19%',dd:'−16%',note:'Basislijn: kopen bij het dip-signaal en niets doen.'},
  {name:'Alleen winst nemen',win:70,avg:'+14%',dd:'−13%',note:'20% verkopen bij +10, +25, +50 en +100%.'},
  {name:'Winst nemen + bijkopen + terugkopen',win:79,avg:'+20%',dd:'−12%',note:'Het model dat de app gebruikt, altijd met een restpositie.',main:true},
  {name:'Zelfde beheer, willekeurig instappunt',win:78,avg:'+16%',dd:'−10%',note:'Controle zonder dip-signaal: 23.232 willekeurige instappen.'},
];
// 2. Per jaar (alle dip-instappen, en alleen de instappen die ook de live-filters halen)
const YEARS=[
  {y:'2020',n:877,win:96,ret:'+32%',nf:196,winf:95},
  {y:'2021',n:779,win:69,ret:'+11%',nf:311,winf:69},
  {y:'2022',n:2041,win:73,ret:'+10%',nf:1175,winf:72},
  {y:'2023',n:1066,win:84,ret:'+21%',nf:433,winf:88},
  {y:'2024',n:973,win:76,ret:'+21%',nf:327,winf:82},
  {y:'2025',n:1536,win:80,ret:'+27%',nf:565,winf:76},
  {y:'2026',n:584,win:82,ret:'+26%',nf:280,winf:85},
];
// 3. Live-filters getest op de historie (zelfde dip-instappen, gesplitst op fundamentals)
const FILTERS=[
  {name:'Alle dip-instappen',n:'8.711',win:79,ret:'+20,0%',dd:'−11,8%',bad:'−11%'},
  {name:'Live-filter: omzetgroei ≥10% en positieve kasstroom',n:'3.638',win:78,ret:'+20,4%',dd:'−11,7%',bad:'−13%',main:true},
  {name:'Omzetgroei onder 10% (live uitgesloten)',n:'3.660',win:83,ret:'+19,9%',dd:'−9,7%',bad:'−6%'},
  {name:'Negatieve kasstroom (live alleen bij sterke reden)',n:'1.470',win:75,ret:'+25,0%',dd:'−16,9%',bad:'−22%'},
  {name:'Top 5 per dag van het live-filter',n:'2.531',win:78,ret:'+20,2%',dd:'−12,0%',bad:'—'},
];
const FINDINGS=[
  ['Diepere dips: meer rendement, meer schommeling','Meer dan 50% onder de 52-wekentop: gemiddeld +28%, maar ook een diepste daling van gemiddeld −18%. Het winstpercentage verandert nauwelijks.'],
  ['Hoge omzetgroei','Bij meer dan 25% omzetgroei stond 75% van de posities in de plus, met meer schommeling. Reden voor het label “agressief”.'],
  ['Rode of groene dag maakt niet uit','Instappen op een rode of groene dag gaf geen ander resultaat. Daarom geen regel.'],
  ['Winst nemen: verder laten lopen','Na +10/25/50% steeg het aandeel gemiddeld nog +8,5/+9,9/+11,8% in drie maanden. Bij sterk momentum was dat +13 tot +15%.'],
  ['Bijkopen na −12%','Na −12% steeg het aandeel gemiddeld +13% in drie maanden. Opgeblazen, want alleen aandelen die nog bestaan zijn getest.'],
];
const CAVEATS=[
  ['Overlevingsbias','Alleen aandelen die nu nog bestaan. Failliet gegane of uit de lijst gevallen bedrijven ontbreken, dus de cijfers zijn te mooi.'],
  ['Stijgende markt','2020-2026 was grotendeels een stijgende markt. In een lange daling valt het winstpercentage lager uit.'],
  ['Overlappende instappen','De ~8.700 uitkomsten zijn niet onafhankelijk: dezelfde aandelen en dezelfde marktfases komen vaak terug.'],
  ['Geen echte test vooruit','De regels zijn bedacht nadat we de data hadden gezien. 2024-2026 is dus een controle op stabiliteit, geen blinde voorspelling.'],
  ['Nieuws en analisten niet getest','Dat is niet per datum beschikbaar. Ze staan in de app als context, niet als signaalregel.'],
  ['Verwachting','In een gewoon jaar: 70-75% van de posities in de plus, niet 79%.'],
];

function Sidebar(){return <aside className="sidebar"><div className="sideBrand"><div className="brandMark"><Activity size={18}/></div><div><b>MARKET<span>INTEL</span></b><small>TRADER PATTERN SCANNER</small></div></div><nav><div className="navLabel">WORKSPACE</div><Link href="/" className="navItem"><LayoutDashboard size={16}/>Scanner</Link><Link href="/portfolio" className="navItem"><Wallet size={16}/>Portfolio</Link><Link href="/history" className="navItem"><History size={16}/>Alert history</Link><Link href="/performance" className="navItem"><BarChart3 size={16}/>Performance</Link><Link href="/validation" className="navItem active"><Target size={16}/>Model validation</Link></nav><div className="sideBottom"><div className="liveStatus"><span className="liveDot"/>MODEL 6.0 DIP</div><div className="sideStat"><span>TESTPERIODE</span><strong>2020-26</strong></div><div className="sideStat"><span>HORIZON</span><strong>126D</strong></div></div></aside>}

function Bar({value,max=100,color=GREEN,mark}){return <div style={{position:'relative',height:10,background:'#16222d',borderRadius:5,minWidth:90}}><div style={{width:`${Math.min(100,value/max*100)}%`,height:'100%',background:color,borderRadius:5}}/>{mark!=null&&<div title="50%" style={{position:'absolute',left:`${mark/max*100}%`,top:-2,bottom:-2,width:1,background:'#3b4d5e'}}/>}</div>}
function Head({eyebrow,title,sub,icon}){return <div className="sectionHeader"><div><div className="sectionEyebrow">{eyebrow}</div><h2>{title}</h2>{sub&&<p>{sub}</p>}</div>{icon}</div>}
function Step({n,title,children}){return <div style={cardStyle}><div style={{display:'flex',alignItems:'center',gap:10,marginBottom:8}}><span style={{...num,width:24,height:24,borderRadius:12,display:'grid',placeItems:'center',background:'#113425',color:GREEN,fontSize:12}}>{n}</span><b style={{color:TEXT,fontSize:13}}>{title}</b></div><div style={{color:MUTED,fontSize:12,lineHeight:1.65}}>{children}</div></div>}
function Kpi({label,value,sub,color=GREEN}){return <div style={cardStyle}><div style={{fontSize:10,letterSpacing:'.08em',color:DIM}}>{label}</div><div style={{...num,fontSize:30,color,marginTop:6}}>{value}</div><div style={{fontSize:11,color:MUTED,marginTop:4}}>{sub}</div></div>}

export default function ValidationPage(){
  return <div className="appShell"><Sidebar/><main className="dashboard">
    <header className="topbar"><div><div className="eyebrow">MODEL / VALIDATIE</div><h1>Model validation</h1><p>Hoe we het model testen op historische koersdata, en wat daar uitkomt.</p></div><div className="topActions"><Link href="/" className="refresh secondary"><LayoutDashboard size={15}/> Dashboard</Link></div></header>

    <section className="sectionBlock">
      <Head eyebrow="SAMENVATTING" title="Het kort" sub="Wat de test zegt, en wat niet." icon={<CheckCircle2 size={18}/>}/>
      <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(200px,1fr))',gap:14,padding:'4px 22px 8px'}}>
        <Kpi label="IN DE PLUS NA 6 MND" value="79%" sub="kopen en vasthouden: 66%"/>
        <Kpi label="GEM. RENDEMENT" value="+20%" sub="in 126 handelsdagen"/>
        <Kpi label="TYPISCHE DIEPSTE DALING" value="−12%" sub="tussentijds, daarna herstel"/>
        <Kpi label="TEST 2024-26 (APART)" value="79%" sub="2020-23: ook 79%"/>
      </div>
      <div style={{padding:'6px 22px 22px',color:MUTED,fontSize:12.5,lineHeight:1.75}}>
        <b style={{color:TEXT}}>Wat bewezen is:</b> het positiebeheer (winst nemen, bijkopen, terugkopen) verbetert het winstpercentage van 66% naar 79%.<br/>
        <b style={{color:AMBER}}>Wat niet bewezen is:</b> dat de dip-instap zelf een betere kans op winst geeft. Willekeurig instappen met hetzelfde beheer geeft 78%; de dip voegt vooral rendement toe (+20% tegen +16%). En de live-kwaliteitsfilters (omzetgroei ≥10%, positieve kasstroom) verbeteren het winstpercentage in de historie niet (zie stap 3).
      </div>
    </section>

    <section className="sectionBlock">
      <Head eyebrow="01 · OPZET" title="Hoe valideren we?" sub="Vier stappen, steeds met dezelfde data." icon={<FlaskConical size={18}/>}/>
      <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(230px,1fr))',gap:14,padding:'4px 22px 22px'}}>
        <Step n="1" title="Data">Dagkoersen van 232 aandelen, 2020 tot oktober 2026. Voor elke dag weten we wat het dip-model toen zou hebben gezien (alleen koersen tot en met die dag).</Step>
        <Step n="2" title="Instappen">Elke dag dat een aandeel de dip-regels haalt, telt als instap: 8.711 stuks. Ter controle ook 23.232 willekeurige instappen zonder signaal.</Step>
        <Step n="3" title="Meten">Per instap volgen we 126 handelsdagen (~6 maanden) met het beheer: 20% verkopen bij +10/25/50/100%, bijkopen bij −12%, terugkopen, altijd een restpositie. Win = positie na 6 maanden in de plus.</Step>
        <Step n="4" title="Vergelijken">Tegen kopen en vasthouden, tegen alleen winst nemen en tegen willekeurige instap. Daarnaast: per jaar en 2020-23 tegenover 2024-26.</Step>
      </div>
    </section>

    <section className="sectionBlock">
      <Head eyebrow="02 · RESULTAAT" title="Welke aanpak werkt het best?" sub="Dezelfde instappunten, vier manieren van beheren. Staaf = deel van de posities in de plus." icon={<TrendingUp size={18}/>}/>
      <div className="tablewrap"><table><thead><tr><th>Aanpak</th><th style={{minWidth:200}}>In de plus</th><th>Gem. rendement</th><th>Gem. diepste daling</th><th>Toelichting</th></tr></thead><tbody>{CONFIGS.map(c=><tr key={c.name} style={c.main?{background:'rgba(53,229,160,.07)'}:undefined}><td className="score">{c.name}</td><td><div style={{display:'flex',alignItems:'center',gap:10}}><b style={{...num,color:c.main?GREEN:TEXT,width:38}}>{c.win}%</b><Bar value={c.win} color={c.main?GREEN:'#4f6b82'} mark={50}/></div></td><td>{c.avg}</td><td>{c.dd}</td><td style={{whiteSpace:'normal',minWidth:240}}>{c.note}</td></tr>)}</tbody></table></div>
    </section>

    <section className="sectionBlock">
      <Head eyebrow="03 · LIVE-REGELS" title="Werken de kwaliteitsfilters van de app?" sub="Dezelfde dip-instappen, gesplitst op omzetgroei en kasstroom op het moment van instap." icon={<Layers size={18}/>}/>
      <div className="tablewrap"><table><thead><tr><th>Groep</th><th>Instappen</th><th style={{minWidth:200}}>In de plus</th><th>Gem. rendement</th><th>Gem. diepste daling</th><th>Slechtste 10%</th></tr></thead><tbody>{FILTERS.map(f=><tr key={f.name} style={f.main?{background:'rgba(53,229,160,.07)'}:undefined}><td className="score" style={{whiteSpace:'normal',minWidth:240}}>{f.name}</td><td>{f.n}</td><td><div style={{display:'flex',alignItems:'center',gap:10}}><b style={{...num,color:f.main?GREEN:TEXT,width:38}}>{f.win}%</b><Bar value={f.win} color={f.main?GREEN:'#4f6b82'} mark={50}/></div></td><td>{f.ret}</td><td>{f.dd}</td><td>{f.bad}</td></tr>)}</tbody></table></div>
      <div style={{padding:'6px 22px 22px',color:MUTED,fontSize:12.5,lineHeight:1.75}}><b style={{color:AMBER}}>Eerlijk gezegd:</b> in de historie is het winstpercentage met het live-filter niet hoger (78% tegen 79%), en aandelen met lage omzetgroei deden het zelfs beter en rustiger (83%, kleinere dalingen). Ook de top 5 per dag scoort niet beter dan de rest. We houden de filters omdat jij geen verouderde of verliesgevende bedrijven wilt, niet omdat de test dat aantoont. Negatieve kasstroom geeft juist hoger rendement (+25%) maar met veel grotere dalingen.</div>
    </section>

    <section className="sectionBlock">
      <Head eyebrow="04 · STABILITEIT" title="Hoe stabiel is het resultaat?" sub="Per instapjaar en gesplitst in 2020-23 en 2024-26." icon={<BarChart3 size={18}/>}/>
      <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(240px,1fr))',gap:14,padding:'4px 22px 14px'}}>
        {[['2020-2023','4.763 instappen','79%','+16,8%','−11,2%','77% met live-filter'],['2024-2026','3.948 instappen','79%','+25,0%','−12,5%','80% met live-filter']].map(p=><div key={p[0]} style={cardStyle}><div style={{fontSize:10,letterSpacing:'.08em',color:DIM}}>{p[0]} · {p[1]}</div><div style={{display:'flex',alignItems:'baseline',gap:12,marginTop:6}}><span style={{...num,fontSize:30,color:GREEN}}>{p[2]}</span><span style={{color:MUTED,fontSize:12}}>in de plus</span></div><div style={{color:MUTED,fontSize:12,marginTop:6}}>Rendement {p[3]} · diepste daling {p[4]}<br/>{p[5]}</div></div>)}
      </div>
      <div className="tablewrap"><table><thead><tr><th>Jaar</th><th>Instappen</th><th style={{minWidth:200}}>In de plus</th><th>Gem. rendement</th><th>In de plus met live-filter</th></tr></thead><tbody>{YEARS.map(r=><tr key={r.y}><td className="score">{r.y}</td><td>{r.n.toLocaleString('nl-NL')}</td><td><div style={{display:'flex',alignItems:'center',gap:10}}><b style={{...num,color:r.win<70?RED:TEXT,width:38}}>{r.win}%</b><Bar value={r.win} color={r.win<70?RED:r.win<75?AMBER:GREEN} mark={50}/></div></td><td>{r.ret}</td><td>{r.winf}% <span style={{color:DIM}}>({r.nf.toLocaleString('nl-NL')})</span></td></tr>)}</tbody></table></div>
      <div style={{padding:'6px 22px 22px',color:MUTED,fontSize:12.5,lineHeight:1.75}}>Het slechtste jaar (2021) kwam uit op 69%, 2022 op 73%. Rendement in 2024-26 is veel hoger dan in 2020-23 door de sterke markt, het winstpercentage is gelijk gebleven.</div>
    </section>

    <section className="sectionBlock">
      <Head eyebrow="05 · BEVINDINGEN" title="Wat we over de regels leerden" icon={<Target size={18}/>}/>
      <div className="signalRules" style={{gridTemplateColumns:'repeat(auto-fit,minmax(260px,1fr))'}}>{FINDINGS.map(f=><div key={f[0]} style={{padding:20}}><b style={{color:TEXT,fontSize:13}}>{f[0]}</b><p style={{margin:'10px 0 0',color:MUTED,fontSize:12,lineHeight:1.65}}>{f[1]}</p></div>)}</div>
    </section>

    <section className="sectionBlock">
      <Head eyebrow="06 · BEPERKINGEN" title="Lees dit voor je op de cijfers vertrouwt" icon={<AlertTriangle size={18}/>}/>
      <div className="signalRules" style={{gridTemplateColumns:'repeat(auto-fit,minmax(260px,1fr))'}}>{CAVEATS.map(c=><div key={c[0]} style={{padding:20}}><b style={{color:AMBER,fontSize:13}}>{c[0]}</b><p style={{margin:'10px 0 0',color:MUTED,fontSize:12,lineHeight:1.65}}>{c[1]}</p></div>)}</div>
    </section>

    <section className="sectionBlock">
      <Head eyebrow="07 · ECHTE RESULTATEN" title="Live volgen" sub="Alerts van model 6.0 worden automatisch gemonitord (1 tot 60 dagen) op Alert history en Performance. Pas na 60 dagen wordt een alert definitief winst of verlies." icon={<ShieldCheck size={18}/>}/>
      <div style={{padding:'0 22px 22px',display:'flex',gap:10,flexWrap:'wrap'}}><Link href="/history" className="refresh secondary"><History size={15}/> Alert history</Link><Link href="/performance" className="refresh secondary"><BarChart3 size={15}/> Performance</Link></div>
    </section>

    <footer>Model validation · dip-model 6.0 · historische simulatie, geen garantie voor de toekomst.</footer>
  </main></div>
}
