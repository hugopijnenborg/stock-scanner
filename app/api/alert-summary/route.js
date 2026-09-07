import { NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

function n(v) { return v == null || !Number.isFinite(Number(v)) ? null : Number(v); }
function pct(v) { const x = n(v); return x == null ? 'niet beschikbaar' : `${(x * 100).toFixed(1)}%`; }
function money(v) { const x = n(v); return x == null || x <= 0 ? 'niet beschikbaar' : `$${x.toFixed(2)}`; }
function signedPct(v) { const x = n(v); return x == null ? 'niet beschikbaar' : `${x >= 0 ? '+' : ''}${(x * 100).toFixed(1)}%`; }
function daysUntil(value) { if (!value) return null; const d = new Date(value); if (Number.isNaN(d.getTime())) return null; return Math.round((d.getTime() - Date.now()) / 86400000); }
function riskLabel(r) { const s=n(r.overall_score), t=n(r.technical_score), d=n(r.distance_52w_high); if ((d!=null&&d<=-.35)||(t!=null&&t<70)) return 'hoog'; if ((d!=null&&d<=-.20)||(s!=null&&s<88)) return 'medium-hoog'; return 'gemiddeld'; }
function confidence(r) { const values=[n(r.overall_score),n(r.trader_similarity_score),n(r.technical_score)].filter(x=>x!=null); const base=values.length?values.reduce((a,b)=>a+b,0)/values.length:0; const analyst=n(r.analyst_consensus_score); const boost=analyst!=null?Math.min(.6,Math.max(-.4,(analyst-70)/50)):-.2; return Math.max(4.5,Math.min(9.5,5+(base-70)/12+boost)); }

function fallback(r) {
  const price=n(r.price), score=n(r.overall_score), trader=n(r.trader_similarity_score), technical=n(r.technical_score), drawdown=n(r.distance_52w_high), r1=n(r.return_1d), r5=n(r.return_5d), r20=n(r.return_20d), rsi=n(r.rsi_14), volume=n(r.volume_ratio), revenueGrowth=n(r.revenue_growth), epsGrowth=n(r.eps_growth), margin=n(r.net_margin), fcf=n(r.fcf), roe=n(r.roe), debtEquity=n(r.debt_equity), pe=n(r.pe), forwardPe=n(r.forward_pe), target=n(r.analyst_target_mean), targetUpside=n(r.analyst_target_upside), analystCount=n(r.analyst_count), recommendation=r.analyst_recommendation;
  const strongBuy=n(r.analyst_strong_buy)||0, buy=n(r.analyst_buy)||0, hold=n(r.analyst_hold)||0, sell=n(r.analyst_sell)||0, strongSell=n(r.analyst_strong_sell)||0;
  const bullish=n(r.analyst_bullish_changes_30d)||0, bearish=n(r.analyst_bearish_changes_30d)||0, targetChanges=n(r.analyst_target_changes_30d)||0;
  const nextEarnings=daysUntil(r.next_earnings_date), risk=riskLabel(r), conf=confidence(r);
  const target25=price!=null?price*1.25:null, target50=price!=null?price*1.5:null;
  const setup=[];
  if(drawdown!=null&&drawdown<=-.15) setup.push(`de koers staat ${Math.abs(drawdown*100).toFixed(1)}% onder de 52-weken high`);
  if(rsi!=null&&rsi<=40) setup.push(`RSI 14 staat op ${rsi.toFixed(1)}, wat wijst op een sterk afgekoelde koers`);
  if(volume!=null&&volume>=1.5) setup.push(`het volume ligt ${volume.toFixed(1)}x boven het normale niveau`);
  if(trader!=null&&trader>=85) setup.push(`de trader pattern match is sterk met ${trader.toFixed(0)}/100`);
  if(technical!=null&&technical>=80) setup.push(`de technische setup scoort ${technical.toFixed(0)}/100`);
  const fund=[];
  if(revenueGrowth!=null&&revenueGrowth>.10) fund.push(`omzet groeit met ${signedPct(revenueGrowth)}`);
  if(epsGrowth!=null&&epsGrowth>.10) fund.push(`EPS groeit met ${signedPct(epsGrowth)}`);
  if(margin!=null) fund.push(`nettomarge bedraagt ${pct(margin)}`);
  if(fcf!=null) fund.push(`vrije kasstroom is ${fcf>0?'positief':'negatief'}`);
  if(roe!=null) fund.push(`ROE bedraagt ${pct(roe)}`);
  if(debtEquity!=null) fund.push(`debt/equity is ${debtEquity.toFixed(2)}`);
  const fundamentalConclusion=fund.length>=2 ? ((revenueGrowth!=null&&revenueGrowth>.10)&&(fcf==null||fcf>0)&&(margin==null||margin>.05) ? `De fundamentals ondersteunen de setup. ${fund.slice(0,4).join(', ')}. De koersdaling staat daarmee niet automatisch gelijk aan een verslechtering van het bedrijf.` : `De fundamentals geven een gemengd beeld. ${fund.slice(0,4).join(', ')}. De koersdaling moet daarom niet uitsluitend als een koopkans worden geïnterpreteerd.`) : 'De fundamentele onderbouwing is beperkt omdat niet alle kerngegevens beschikbaar zijn.';
  let analystText='Er is onvoldoende analyst consensus beschikbaar om hier een sterke bevestiging aan te koppelen.';
  if(target!=null||recommendation||analystCount!=null){ const pieces=[]; if(recommendation)pieces.push(`consensus ${String(recommendation).replaceAll('_',' ')}`); if(analystCount!=null)pieces.push(`${analystCount} analisten`); if(target!=null)pieces.push(`gemiddeld koersdoel ${money(target)}`); if(targetUpside!=null)pieces.push(`impliceert ${signedPct(targetUpside)} upside`); if(strongBuy+buy+hold+sell+strongSell>0)pieces.push(`verdeling ${strongBuy+buy} buy vs ${hold} hold vs ${sell+strongSell} sell`); analystText=`De analistenbevestiging is ${pieces.join(', ')}.`; if(bullish>bearish&&targetChanges>0)analystText+=` In de afgelopen 30 dagen zijn er meer positieve dan negatieve wijzigingen geweest (${bullish} vs ${bearish}), wat de setup extra ondersteunt.`; if(bearish>bullish&&targetChanges>0)analystText+=` De recente wijzigingen zijn echter vaker negatief (${bearish} vs ${bullish}), wat een belangrijk waarschuwingssignaal is.`; }
  let catalyst='Er is geen concrete katalysator binnen de beschikbare scan-data die de timing sterk ondersteunt.';
  if(nextEarnings!=null&&nextEarnings>=0&&nextEarnings<=60)catalyst=`De volgende earnings staan over ongeveer ${nextEarnings} dagen gepland. Dat is de duidelijkste concrete katalysator binnen de huidige horizon.`;
  else if(Array.isArray(r.recent_news)&&r.recent_news.length){const titles=r.recent_news.slice(0,2).map(x=>x?.title).filter(Boolean);if(titles.length)catalyst=`Recente nieuwsitems die de timing kunnen beïnvloeden: ${titles.join(' | ')}.`;}
  const returnText=price!=null?`Vanaf ${money(price)} ligt +25% rond ${money(target25)} en +50% rond ${money(target50)}. ${target!=null?`Het gemiddelde analistenkoersdoel van ${money(target)} ligt ${target>price?'boven':'onder'} de huidige koers en impliceert ${signedPct(targetUpside)}.`:'Er is geen betrouwbaar gemiddeld analistenkoersdoel beschikbaar, waardoor deze targets alleen als scenario en niet als consensusdoel moeten worden gezien.'}`:'De huidige koers is niet beschikbaar, waardoor concrete targets niet betrouwbaar kunnen worden berekend.';
  const riskText=[drawdown!=null&&drawdown<=-.25?`de forse drawdown van ${Math.abs(drawdown*100).toFixed(1)}% kan betekenen dat de neerwaartse trend nog niet voorbij is`:null,rsi!=null&&rsi<=35?'een lage RSI garandeert geen bodem en een aandeel kan langer oversold blijven':null,bearish>bullish?'recente negatieve analyst wijzigingen verhogen het risico':null,pe!=null&&forwardPe!=null&&forwardPe>pe?'de forward waardering vraagt om aanhoudende winstgroei':null].filter(Boolean);
  let tradingPlan='Wacht op bevestiging van bodemvorming voordat je agressief bijkoopt. De setup wordt zwakker bij verdere neerwaartse prijsactie gecombineerd met verslechterende fundamentals.';
  if(price!=null&&rsi!=null&&rsi<=40&&technical!=null&&technical>=80)tradingPlan=`De huidige koers ${money(price)} kan als eerste referentie dienen. Een sterkere entry ontstaat bij bevestiging van een reversal, terwijl verdere neerwaartse prijsactie de setup ongeldig kan maken. +25% ligt rond ${money(target25)} en +50% rond ${money(target50)}.`;
  return [
    'WAAROM NU?',
    setup.length?`${r.company_name||r.ticker} valt op omdat ${setup.slice(0,4).join(', ')}. De combinatie is interessanter dan één losse indicator: de scanner ziet hier een setup waarin een forse correctie mogelijk samenvalt met een technisch herstelpunt${fund.length?' terwijl de fundamentals nog steun bieden':''}.`:`${r.company_name||r.ticker} heeft een sterke scanner-score, maar de beschikbare data geeft onvoldoende specifieke signalen om de timing verder te onderbouwen.`,
    '',
    '1. TECHNISCHE SETUP',
    `Trader pattern ${trader?.toFixed(0)??'—'}/100 en technical ${technical?.toFixed(0)??'—'}/100. 1D ${signedPct(r1)}, 5D ${signedPct(r5)}, 20D ${signedPct(r20)}, RSI ${rsi?.toFixed(1)??'—'}, volume ${volume?.toFixed(1)??'—'}x en ${drawdown!=null?`${Math.abs(drawdown*100).toFixed(1)}% onder de 52-weken high`:'afstand tot de 52-weken high niet beschikbaar'}.`,
    'De technische case is vooral interessant als de huidige sell-off stabiliseert. Oversold-condities zijn op zichzelf geen kooptrigger. Een reversal en verbetering van momentum zijn de belangrijkste bevestiging.',
    '',
    '2. FUNDAMENTALS', fundamentalConclusion,
    '',
    '3. ANALISTENBEVESTIGING', analystText,
    '',
    '4. KATALYSATOR / TIMING', catalyst,
    '',
    '5. RETURN-POTENTIEEL', returnText,
    '',
    '6. BELANGRIJKSTE RISICO', riskText.length?`Het grootste risico is dat ${riskText.join('; ')}.`:'Het grootste risico is dat de technische setup niet doorzet en de neerwaartse trend opnieuw versnelt.',
    '',
    '7. HANDELSPLAN', tradingPlan,
    '',
    'MIJN OORDEEL',
    `${r.ticker} is interessant omdat de scanner een sterke combinatie van trader- en technische signalen ziet. ${fund.length?'De fundamentals geven extra onderbouwing, maar ze veranderen niets aan het risico van een verdere correctie.':'De belangrijkste ontbrekende bevestiging zit in de fundamentele en analyst-data.'} Dit is daarom een setup om actief te volgen en op technische bevestiging te handelen, niet om blind op de score te kopen.`
  ].join('\n');
}

function promptFor(r) {
  const compact={ticker:r.ticker,company:r.company_name,price:r.price,score:r.overall_score,trader_match:r.trader_similarity_score,technical_score:r.technical_score,analyst_score:r.analyst_consensus_score,returns:{one_day:r.return_1d,three_day:r.return_3d,five_day:r.return_5d,twenty_day:r.return_20d},technical:{rsi:r.rsi_14,volume_ratio:r.volume_ratio,distance_sma20:r.distance_sma20,distance_sma50:r.distance_sma50,distance_52w_high:r.distance_52w_high,macd_histogram:r.macd_histogram},fundamentals:{revenue_growth:r.revenue_growth,eps_growth:r.eps_growth,net_margin:r.net_margin,fcf:r.fcf,roe:r.roe,debt_equity:r.debt_equity,pe:r.pe,forward_pe:r.forward_pe,peg:r.peg},analysts:{recommendation:r.analyst_recommendation,count:r.analyst_count,strong_buy:r.analyst_strong_buy,buy:r.analyst_buy,hold:r.analyst_hold,sell:r.analyst_sell,strong_sell:r.analyst_strong_sell,target_mean:r.analyst_target_mean,target_median:r.analyst_target_median,target_low:r.analyst_target_low,target_high:r.analyst_target_high,target_upside:r.analyst_target_upside,bullish_changes_30d:r.analyst_bullish_changes_30d,bearish_changes_30d:r.analyst_bearish_changes_30d,target_changes_30d:r.analyst_target_changes_30d},earnings:{last_date:r.last_earnings_date,surprise_pct:r.last_earnings_surprise_pct,next_date:r.next_earnings_date},recent_news:Array.isArray(r.recent_news)?r.recent_news.slice(0,5):[]};
  return `Schrijf alleen de inhoud van een professionele Nederlandse AI Opportunity Analysis voor ${r.ticker}. Geef GEEN titel met STOCK OPPORTUNITY ALERT, GEEN opportunity score-regel en GEEN dubbele introductie. Begin met "WAAROM NU?" en gebruik daarna exact: 1. TECHNISCHE SETUP, 2. FUNDAMENTALS, 3. ANALISTENBEVESTIGING, 4. KATALYSATOR / TIMING, 5. RETURN-POTENTIEEL, 6. BELANGRIJKSTE RISICO, 7. HANDELSPLAN en MIJN OORDEEL. Gebruik uitsluitend de data hieronder. Verzin niets en benoem ontbrekende data expliciet.\n\nDATA:\n${JSON.stringify(compact,null,2)}`;
}

export async function POST(request) {
  try {
    const body=await request.json(); const stock=body?.stock;
    if(!stock?.ticker)return NextResponse.json({error:'Geen aandeel ontvangen.'},{status:400});
    const apiKey=process.env.ANTHROPIC_API_KEY;
    if(!apiKey)return NextResponse.json({summary:fallback(stock),provider:'rule-based'});
    const model=process.env.ANTHROPIC_MODEL||'claude-3-5-haiku-latest';
    const response=await fetch('https://api.anthropic.com/v1/messages',{method:'POST',headers:{'content-type':'application/json','x-api-key':apiKey,'anthropic-version':'2023-06-01'},body:JSON.stringify({model,max_tokens:1800,temperature:.2,messages:[{role:'user',content:promptFor(stock)}]}),cache:'no-store'});
    const data=await response.json();
    if(!response.ok)return NextResponse.json({summary:fallback(stock),provider:'rule-based',error:data?.error?.message||'AI request failed'});
    const summary=Array.isArray(data.content)?data.content.filter(x=>x.type==='text').map(x=>x.text).join('\n').trim():'';
    return NextResponse.json({summary:summary||fallback(stock),provider:'anthropic'});
  } catch(error) { return NextResponse.json({summary:fallback({ticker:'ONBEKEND',company_name:'Aandeel'}),provider:'rule-based',error:error?.message||'Onbekende fout.'}); }
}
