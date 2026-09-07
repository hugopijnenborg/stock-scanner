import { NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

function n(v) {
  return v == null || !Number.isFinite(Number(v)) ? null : Number(v);
}
function pct(v) {
  const x = n(v);
  return x == null ? 'niet beschikbaar' : `${(x * 100).toFixed(1)}%`;
}
function money(v) {
  const x = n(v);
  return x == null || x <= 0 ? 'niet beschikbaar' : `$${x.toFixed(2)}`;
}
function signedPct(v) {
  const x = n(v);
  return x == null ? 'niet beschikbaar' : `${x >= 0 ? '+' : ''}${(x * 100).toFixed(1)}%`;
}
function daysUntil(value) {
  if (!value) return null;
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return null;
  return Math.round((d.getTime() - Date.now()) / 86400000);
}
function riskLabel(r) {
  const score = n(r.overall_score);
  const technical = n(r.technical_score);
  const drawdown = n(r.distance_52w_high);
  if ((drawdown != null && drawdown <= -0.35) || (technical != null && technical < 70)) return 'hoog';
  if ((drawdown != null && drawdown <= -0.20) || (score != null && score < 88)) return 'medium-hoog';
  return 'gemiddeld';
}
function confidence(r) {
  const score = n(r.overall_score);
  const trader = n(r.trader_similarity_score);
  const technical = n(r.technical_score);
  const analyst = n(r.analyst_consensus_score);
  const values = [score, trader, technical].filter(x => x != null);
  const base = values.length ? values.reduce((a, b) => a + b, 0) / values.length : 0;
  const analystBoost = analyst != null ? Math.min(0.6, Math.max(-0.4, (analyst - 70) / 50)) : -0.2;
  return Math.max(4.5, Math.min(9.5, 5 + (base - 70) / 12 + analystBoost));
}

function fallback(r) {
  const price = n(r.price);
  const score = n(r.overall_score);
  const trader = n(r.trader_similarity_score);
  const technical = n(r.technical_score);
  const drawdown = n(r.distance_52w_high);
  const r1 = n(r.return_1d);
  const r5 = n(r.return_5d);
  const r20 = n(r.return_20d);
  const rsi = n(r.rsi_14);
  const volume = n(r.volume_ratio);
  const revenueGrowth = n(r.revenue_growth);
  const epsGrowth = n(r.eps_growth);
  const margin = n(r.net_margin);
  const fcf = n(r.fcf);
  const roe = n(r.roe);
  const debtEquity = n(r.debt_equity);
  const pe = n(r.pe);
  const forwardPe = n(r.forward_pe);
  const peg = n(r.peg);
  const target = n(r.analyst_target_mean);
  const targetUpside = n(r.analyst_target_upside);
  const analystCount = n(r.analyst_count);
  const recommendation = r.analyst_recommendation;
  const strongBuy = n(r.analyst_strong_buy) || 0;
  const buy = n(r.analyst_buy) || 0;
  const hold = n(r.analyst_hold) || 0;
  const sell = n(r.analyst_sell) || 0;
  const strongSell = n(r.analyst_strong_sell) || 0;
  const bullishChanges = n(r.analyst_bullish_changes_30d) || 0;
  const bearishChanges = n(r.analyst_bearish_changes_30d) || 0;
  const targetChanges = n(r.analyst_target_changes_30d) || 0;
  const nextEarningsDays = daysUntil(r.next_earnings_date);
  const risk = riskLabel(r);
  const conf = confidence(r);

  const target25 = price != null ? price * 1.25 : null;
  const target50 = price != null ? price * 1.50 : null;

  const setupReasons = [];
  if (drawdown != null && drawdown <= -0.15) setupReasons.push(`de koers staat ${Math.abs(drawdown * 100).toFixed(1)}% onder de 52-weken high`);
  if (rsi != null && rsi <= 40) setupReasons.push(`RSI 14 staat op ${rsi.toFixed(1)}, wat wijst op een sterk afgekoelde koers`);
  if (volume != null && volume >= 1.5) setupReasons.push(`het volume ligt ${volume.toFixed(1)}x boven het normale niveau`);
  if (trader != null && trader >= 85) setupReasons.push(`de trader pattern match is sterk met ${trader.toFixed(0)}/100`);
  if (technical != null && technical >= 80) setupReasons.push(`de technische setup scoort ${technical.toFixed(0)}/100`);

  const fundamentalReasons = [];
  if (revenueGrowth != null && revenueGrowth > 0.10) fundamentalReasons.push(`omzet groeit met ${signedPct(revenueGrowth)}`);
  if (epsGrowth != null && epsGrowth > 0.10) fundamentalReasons.push(`EPS groeit met ${signedPct(epsGrowth)}`);
  if (margin != null) fundamentalReasons.push(`nettomarge bedraagt ${pct(margin)}`);
  if (fcf != null) fundamentalReasons.push(`vrije kasstroom is ${fcf > 0 ? 'positief' : 'negatief'}`);
  if (roe != null) fundamentalReasons.push(`ROE bedraagt ${pct(roe)}`);
  if (debtEquity != null) fundamentalReasons.push(`debt/equity is ${debtEquity.toFixed(2)}`);

  let fundamentalConclusion = 'De fundamentele onderbouwing is beperkt omdat niet alle kerngegevens beschikbaar zijn.';
  if (fundamentalReasons.length >= 2) {
    const clearlyStrong = (revenueGrowth != null && revenueGrowth > 0.10) && (fcf == null || fcf > 0) && (margin == null || margin > 0.05);
    fundamentalConclusion = clearlyStrong
      ? `De fundamentals ondersteunen de setup. ${fundamentalReasons.slice(0, 4).join(', ')}. De koersdaling staat daarmee niet automatisch gelijk aan een verslechtering van het bedrijf.`
      : `De fundamentals geven een gemengd beeld. ${fundamentalReasons.slice(0, 4).join(', ')}. De koersdaling moet daarom niet uitsluitend als een koopkans worden geïnterpreteerd.`;
  }

  let analystText = 'Er is onvoldoende analyst consensus beschikbaar om hier een sterke bevestiging aan te koppelen.';
  if (target != null || recommendation || analystCount != null) {
    const pieces = [];
    if (recommendation) pieces.push(`consensus ${String(recommendation).replaceAll('_', ' ')}`);
    if (analystCount != null) pieces.push(`${analystCount} analisten`);
    if (target != null) pieces.push(`gemiddeld koersdoel ${money(target)}`);
    if (targetUpside != null) pieces.push(`impliceert ${signedPct(targetUpside)} upside`);
    if (strongBuy + buy + hold + sell + strongSell > 0) pieces.push(`verdeling ${strongBuy + buy} buy vs ${hold} hold vs ${sell + strongSell} sell`);
    analystText = `De analistenbevestiging is ${pieces.join(', ')}.`;
    if (bullishChanges > bearishChanges && targetChanges > 0) analystText += ` In de afgelopen 30 dagen zijn er meer positieve dan negatieve wijzigingen geweest (${bullishChanges} vs ${bearishChanges}), wat de setup extra ondersteunt.`;
    if (bearishChanges > bullishChanges && targetChanges > 0) analystText += ` De recente wijzigingen zijn echter vaker negatief (${bearishChanges} vs ${bullishChanges}), wat een belangrijk waarschuwingssignaal is.`;
  }

  let catalyst = 'Er is geen concrete katalysator binnen de beschikbare scan-data die de timing sterk ondersteunt.';
  if (nextEarningsDays != null && nextEarningsDays >= 0 && nextEarningsDays <= 60) {
    catalyst = `De volgende earnings staan over ongeveer ${nextEarningsDays} dagen gepland. Dat is de duidelijkste concrete katalysator binnen de huidige horizon.`;
  } else if (Array.isArray(r.recent_news) && r.recent_news.length) {
    const titles = r.recent_news.slice(0, 2).map(x => x?.title).filter(Boolean);
    if (titles.length) catalyst = `Recente nieuwsitems die de timing kunnen beïnvloeden: ${titles.join(' | ')}.`;
  }

  const returnText = price != null
    ? `Vanaf ${money(price)} ligt +25% rond ${money(target25)} en +50% rond ${money(target50)}. ${target != null ? `Het gemiddelde analistenkoersdoel van ${money(target)} ligt ${target > price ? 'boven' : 'onder'} de huidige koers en impliceert ${signedPct(targetUpside)}.` : 'Er is geen betrouwbaar gemiddeld analistenkoersdoel beschikbaar, waardoor deze targets alleen als scenario en niet als consensusdoel moeten worden gezien.'}`
    : 'De huidige koers is niet beschikbaar, waardoor concrete targets niet betrouwbaar kunnen worden berekend.';

  let tradingPlan = 'Wacht op bevestiging van bodemvorming voordat je agressief bijkoopt. De setup wordt zwakker bij verdere neerwaartse prijsactie gecombineerd met verslechterende fundamentals.';
  if (price != null && rsi != null && rsi <= 40 && technical != null && technical >= 80) {
    tradingPlan = `De huidige koers ${money(price)} kan als eerste referentie dienen. Een sterkere entry ontstaat bij bevestiging van een reversal, terwijl verdere neerwaartse prijsactie de setup ongeldig kan maken. +25% ligt rond ${money(target25)} en +50% rond ${money(target50)}.`;
  }

  const riskText = [
    drawdown != null && drawdown <= -0.25 ? `de forse drawdown van ${Math.abs(drawdown * 100).toFixed(1)}% kan betekenen dat de neerwaartse trend nog niet voorbij is` : null,
    rsi != null && rsi <= 35 ? 'een lage RSI garandeert geen bodem en een aandeel kan langer oversold blijven' : null,
    bearishChanges > bullishChanges ? 'recente negatieve analyst wijzigingen verhogen het risico' : null,
    pe != null && forwardPe != null && forwardPe > pe ? 'de forward waardering vraagt om aanhoudende winstgroei' : null,
  ].filter(Boolean);

  return [
    `STOCK OPPORTUNITY ALERT — ${r.ticker}: BUY`,
    `Opportunity Score ${score?.toFixed(0) ?? '—'}/100 | koers ${money(price)} | confidence ${conf.toFixed(1)}/10 | risk ${risk}`,
    '',
    `WAAROM NU?`,
    setupReasons.length
      ? `${r.company_name || r.ticker} valt op omdat ${setupReasons.slice(0, 4).join(', ')}. De combinatie is interessanter dan één losse indicator: de scanner ziet hier een setup waarin een forse correctie mogelijk samenvalt met een technisch herstelpunt${fundamentalReasons.length ? ' terwijl de fundamentals nog steun bieden' : ''}.`
      : `${r.company_name || r.ticker} heeft een sterke scanner-score, maar de beschikbare data geeft onvoldoende specifieke signalen om de timing verder te onderbouwen.`,
    '',
    `1. TECHNISCHE SETUP`,
    `Trader pattern ${trader?.toFixed(0) ?? '—'}/100 en technical ${technical?.toFixed(0) ?? '—'}/100. 1D ${signedPct(r1)}, 5D ${signedPct(r5)}, 20D ${signedPct(r20)}, RSI ${rsi?.toFixed(1) ?? '—'}, volume ${volume?.toFixed(1) ?? '—'}x en ${drawdown != null ? `${Math.abs(drawdown * 100).toFixed(1)}% onder de 52-weken high` : 'afstand tot de 52-weken high niet beschikbaar'}.`,
    `De technische case is vooral interessant als de huidige sell-off stabiliseert. Oversold-condities zijn op zichzelf geen kooptrigger. Een reversal en verbetering van momentum zijn de belangrijkste bevestiging.`,
    '',
    `2. FUNDAMENTALS`,
    fundamentalConclusion,
    '',
    `3. ANALISTENBEVESTIGING`,
    analystText,
    '',
    `4. KATALYSATOR / TIMING`,
    catalyst,
    '',
    `5. RETURN-POTENTIEEL`,
    returnText,
    '',
    `6. BELANGRIJKSTE RISICO`,
    riskText.length ? `Het grootste risico is dat ${riskText.join('; ')}.` : 'Het grootste risico is dat de technische setup niet doorzet en de neerwaartse trend opnieuw versnelt.',
    '',
    `7. HANDELSPLAN`,
    tradingPlan,
    '',
    `MIJN OORDEEL`,
    `${r.ticker} is interessant omdat de scanner een sterke combinatie van trader- en technische signalen ziet. ${fundamentalReasons.length ? 'De fundamentals geven extra onderbouwing, maar ze veranderen niets aan het risico van een verdere correctie.' : 'De belangrijkste ontbrekende bevestiging zit in de fundamentele en analyst-data.'} Dit is daarom een setup om actief te volgen en op technische bevestiging te handelen, niet om blind op de score te kopen.`,
  ].join('\n');
}

function promptFor(r) {
  const compact = {
    ticker: r.ticker,
    company: r.company_name,
    price: r.price,
    score: r.overall_score,
    trader_match: r.trader_similarity_score,
    technical_score: r.technical_score,
    analyst_score: r.analyst_consensus_score,
    returns: { one_day: r.return_1d, three_day: r.return_3d, five_day: r.return_5d, twenty_day: r.return_20d },
    technical: { rsi: r.rsi_14, volume_ratio: r.volume_ratio, distance_sma20: r.distance_sma20, distance_sma50: r.distance_sma50, distance_52w_high: r.distance_52w_high, macd_histogram: r.macd_histogram },
    fundamentals: { revenue_growth: r.revenue_growth, eps_growth: r.eps_growth, net_margin: r.net_margin, fcf: r.fcf, roe: r.roe, debt_equity: r.debt_equity, pe: r.pe, forward_pe: r.forward_pe, peg: r.peg },
    analysts: { recommendation: r.analyst_recommendation, count: r.analyst_count, strong_buy: r.analyst_strong_buy, buy: r.analyst_buy, hold: r.analyst_hold, sell: r.analyst_sell, strong_sell: r.analyst_strong_sell, target_mean: r.analyst_target_mean, target_median: r.analyst_target_median, target_low: r.analyst_target_low, target_high: r.analyst_target_high, target_upside: r.analyst_target_upside, bullish_changes_30d: r.analyst_bullish_changes_30d, bearish_changes_30d: r.analyst_bearish_changes_30d, target_changes_30d: r.analyst_target_changes_30d },
    earnings: { last_date: r.last_earnings_date, surprise_pct: r.last_earnings_surprise_pct, next_date: r.next_earnings_date },
    recent_news: Array.isArray(r.recent_news) ? r.recent_news.slice(0, 5) : [],
  };
  return `Schrijf een professionele Nederlandse STOCK OPPORTUNITY ALERT voor een swing-trading dashboard. Gebruik uitsluitend de aangeleverde data. Verzin geen cijfers, koersdoelen, nieuws, katalysatoren, scenario's of kansen. Als data ontbreekt, zeg dat expliciet. Houd het concreet en kritisch. De stijl moet lijken op een professionele equity-research alert, niet op marketingtekst.

Structuur:
Eerste regel: "${r.ticker}: BUY | Opportunity Score ... | koers ... | risico: ..."
Daarna één korte conclusie waarom deze setup nu interessant is.

Gebruik daarna exact deze onderdelen:
1. Technische setup
2. Fundamentals
3. Analistenbevestiging
4. Katalysator / timing
5. Return-potentieel
6. Belangrijkste risico
7. Handelsplan

Sluit af met een korte "Mijn oordeel" van maximaal 3 zinnen. Benoem alleen een entry, add, invalidatie en targets als de beschikbare data daar een redelijke basis voor geeft. Gebruik geen schijnprecisie. Leg vooral uit waarom het aandeel nu interessant is en wat de setup ongeldig maakt.

DATA:
${JSON.stringify(compact, null, 2)}`;
}

export async function POST(request) {
  try {
    const body = await request.json();
    const stock = body?.stock;
    if (!stock?.ticker) return NextResponse.json({ error: 'Geen aandeel ontvangen.' }, { status: 400 });

    const apiKey = process.env.ANTHROPIC_API_KEY;
    if (!apiKey) return NextResponse.json({ summary: fallback(stock), provider: 'rule-based' });

    const model = process.env.ANTHROPIC_MODEL || 'claude-3-5-haiku-latest';
    const response = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: { 'content-type': 'application/json', 'x-api-key': apiKey, 'anthropic-version': '2023-06-01' },
      body: JSON.stringify({ model, max_tokens: 1800, temperature: 0.2, messages: [{ role: 'user', content: promptFor(stock) }] }),
      cache: 'no-store',
    });
    const data = await response.json();
    if (!response.ok) return NextResponse.json({ summary: fallback(stock), provider: 'rule-based', error: data?.error?.message || 'AI request failed' });
    const summary = Array.isArray(data.content) ? data.content.filter(x => x.type === 'text').map(x => x.text).join('\n').trim() : '';
    return NextResponse.json({ summary: summary || fallback(stock), provider: 'anthropic' });
  } catch (error) {
    return NextResponse.json({ summary: fallback({ ticker: 'ONBEKEND', company_name: 'Aandeel' }), provider: 'rule-based', error: error?.message || 'Onbekende fout.' });
  }
}
