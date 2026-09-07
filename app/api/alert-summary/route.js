import { NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

function n(v) {
  return v == null || !Number.isFinite(Number(v)) ? null : Number(v);
}
function pct(v) {
  const x = n(v);
  return x == null ? 'n.v.t.' : `${(x * 100).toFixed(1)}%`;
}
function money(v) {
  const x = n(v);
  return x == null || x <= 0 ? 'n.v.t.' : `$${x.toFixed(0)}`;
}

function fallback(r) {
  const target = n(r.analyst_target_mean);
  const upside = n(r.analyst_target_upside);
  const recentNews = Array.isArray(r.recent_news) ? r.recent_news.slice(0, 3).map(x => x?.title).filter(Boolean) : [];
  return [
    `${r.ticker}: BUY | Opportunity Score ${n(r.overall_score)?.toFixed(0) ?? '—'}/100 | koers ${money(r.price)}`,
    '',
    `${r.company_name || r.ticker} heeft een trader match van ${n(r.trader_similarity_score)?.toFixed(0) ?? '—'}/100 en een technische score van ${n(r.technical_score)?.toFixed(0) ?? '—'}/100. De score wordt dus niet door één indicator gedragen.`,
    '',
    `1. Technische setup. De koers staat ${pct(r.distance_52w_high)} onder de 52-weeks high. De 5-daagse beweging is ${pct(r.return_5d)}, RSI 14 staat op ${n(r.rsi_14)?.toFixed(1) ?? '—'} en het volume ligt op ${n(r.volume_ratio)?.toFixed(1) ?? '—'}x het normale niveau.`,
    `2. Fundamentals. Omzetgroei ${pct(r.revenue_growth)}, EPS-groei ${pct(r.eps_growth)}, nettomarge ${pct(r.net_margin)} en vrije kasstroom ${n(r.fcf) > 0 ? 'positief' : 'niet positief of niet beschikbaar'}.`,
    `3. Analisten. Consensus: ${r.analyst_recommendation || 'niet beschikbaar'}. Gemiddeld koersdoel: ${money(target)}. Dat impliceert ${pct(upside)} vanaf de huidige koers.`,
    `4. Katalysator / timing. ${recentNews.length ? recentNews.join(' | ') : 'Er is geen concrete nieuws-katalysator beschikbaar in de scan-data.'}`,
    `5. Return-potentieel. Een herstel naar het gemiddelde analistenkoersdoel zou ongeveer ${pct(upside)} betekenen. Dit is een referentiepunt, geen voorspelling.`,
    `6. Risico. De technische trend kan verder verslechteren. Een lage RSI kan lang oversold blijven en de huidige setup kan ongeldig worden bij verdere neerwaartse prijsactie.`,
    `7. Handelsplan. Gebruik de huidige koers als eerste referentie. Een add hoort pas bij bevestiging van een technische reversal of een gecontroleerde terugval zonder fundamentele verslechtering.`,
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
    if (!apiKey) return NextResponse.json({ summary: fallback(stock), provider: 'fallback' });

    const model = process.env.ANTHROPIC_MODEL || 'claude-3-5-haiku-latest';
    const response = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: { 'content-type': 'application/json', 'x-api-key': apiKey, 'anthropic-version': '2023-06-01' },
      body: JSON.stringify({ model, max_tokens: 1800, temperature: 0.2, messages: [{ role: 'user', content: promptFor(stock) }] }),
      cache: 'no-store',
    });
    const data = await response.json();
    if (!response.ok) return NextResponse.json({ summary: fallback(stock), provider: 'fallback', error: data?.error?.message || 'AI request failed' });
    const summary = Array.isArray(data.content) ? data.content.filter(x => x.type === 'text').map(x => x.text).join('\n').trim() : '';
    return NextResponse.json({ summary: summary || fallback(stock), provider: 'anthropic' });
  } catch (error) {
    return NextResponse.json({ error: error?.message || 'Onbekende fout.' }, { status: 500 });
  }
}
