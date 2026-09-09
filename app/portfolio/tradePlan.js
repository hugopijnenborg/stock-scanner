const finite = (value) => Number.isFinite(Number(value)) ? Number(value) : null;

const SCORE_WEIGHTS = { trader: 0.35, technical: 0.30, fundamental: 0.20, analyst: 0.15 };

function uniqueSorted(values, direction = 'asc') {
  return [...new Set(values.filter((value) => Number.isFinite(value)))].sort((a, b) => direction === 'asc' ? a - b : b - a);
}

function scoreValue(value) {
  const n = finite(value);
  return n != null && n > 0 ? n : null;
}

function weightedScore(scores) {
  const parts = [
    [scoreValue(scores?.trader), SCORE_WEIGHTS.trader],
    [scoreValue(scores?.technical), SCORE_WEIGHTS.technical],
    [scoreValue(scores?.fundamental), SCORE_WEIGHTS.fundamental],
    [scoreValue(scores?.analyst), SCORE_WEIGHTS.analyst],
  ].filter(([value]) => value != null);
  if (!parts.length) return null;
  const weightSum = parts.reduce((sum, [, weight]) => sum + weight, 0);
  return parts.reduce((sum, [value, weight]) => sum + value * weight, 0) / weightSum;
}

function hasCompleteScoreSet(scores) {
  return [scores?.trader, scores?.technical, scores?.fundamental, scores?.analyst].every((value) => scoreValue(value) != null);
}

export function getPivots(history = []) {
  const rows = history.filter((row) => finite(row?.close) !== null);
  const lows = [];
  const highs = [];
  for (let i = 2; i < rows.length - 2; i += 1) {
    const price = Number(rows[i].close);
    const around = rows.slice(i - 2, i + 3).map((row) => Number(row.close));
    if (price === Math.min(...around) && price < around[0] && price < around[4]) lows.push(price);
    if (price === Math.max(...around) && price > around[0] && price > around[4]) highs.push(price);
  }
  return { lows: uniqueSorted(lows, 'desc'), highs: uniqueSorted(highs, 'asc') };
}

function reconstructAverage(price, distance) {
  const d = finite(distance);
  if (d == null || d <= -0.95) return null;
  return price / (1 + d);
}

export function buildTradePlan(position, result) {
  const price = finite(result?.price);
  if (!(price > 0)) return null;

  const atrPct = Math.max(finite(result?.atr_pct) || 0, 0.03);
  const pivots = getPivots(result?.history_6m || []);
  const sma20 = reconstructAverage(price, result?.distance_sma20);
  const sma50 = reconstructAverage(price, result?.distance_sma50);

  const supportDistance = finite(result?.distance_support_20d);
  let support = supportDistance != null && supportDistance > 0 && supportDistance < 0.45 ? price * (1 - supportDistance) : null;
  const pivotSupport = pivots.lows.filter((level) => level < price).sort((a, b) => b - a)[0] || null;
  if (pivotSupport && (!support || pivotSupport > support)) support = pivotSupport;

  const resistanceLevels = [
    ...pivots.highs.filter((level) => level > price * 1.01),
    ...(sma20 && sma20 > price * 1.01 ? [sma20] : []),
    ...(sma50 && sma50 > price * 1.01 ? [sma50] : []),
  ];
  const resistances = uniqueSorted(resistanceLevels, 'asc');
  const analystTarget = finite(result?.analyst_target_mean);
  const high52 = finite(result?.high_52w);

  let firstTarget = resistances[0] || null;
  let secondTarget = null;
  if (!firstTarget && analystTarget && analystTarget > price * 1.02) firstTarget = analystTarget;
  if (firstTarget) {
    secondTarget = analystTarget && analystTarget > firstTarget * 1.03 ? analystTarget : null;
    if (!secondTarget) {
      const nextResistance = resistances.find((level) => level > firstTarget * 1.03);
      secondTarget = nextResistance || (high52 && high52 > firstTarget * 1.03 ? high52 : null);
    }
  } else if (high52 && high52 > price * 1.02) secondTarget = high52;
  if (!secondTarget && analystTarget && analystTarget > price * 1.02 && analystTarget !== firstTarget) secondTarget = analystTarget;
  if (!firstTarget && secondTarget) firstTarget = secondTarget;

  const supportLevel = support || price * (1 - atrPct);
  const stop = Math.max(0.01, supportLevel - price * atrPct * 0.5);
  const riskPct = price > stop ? 1 - stop / price : null;

  const entryPrice = finite(position?.entryPrice);
  const gain = entryPrice && entryPrice > 0 ? price / entryPrice - 1 : null;

  // ADD is position-based: it can never trigger before the position is at least 7.5% below its weighted entry price.
  const addTrigger = entryPrice && entryPrice > 0 ? entryPrice * 0.925 : null;
  const addHigh = addTrigger != null ? addTrigger : (support ? support * 1.02 : price * Math.max(0.94, 1 - atrPct * 0.5));
  const addLow = addTrigger != null ? addTrigger * 0.98 : stop;

  const target = secondTarget || firstTarget;
  const targetUpside = target && target > price ? target / price - 1 : null;
  const rewardRisk = targetUpside != null && riskPct > 0 ? targetUpside / riskPct : null;

  const scores = {
    trader: finite(result?.trader_score ?? result?.trader_similarity_score),
    technical: finite(result?.technical_score),
    fundamental: finite(result?.fundamental_score),
    analyst: finite(result?.analyst_score ?? result?.analyst_consensus_score),
  };
  const entryScores = {
    trader: finite(position?.entryTraderScore),
    technical: finite(position?.entryTechnicalScore),
    fundamental: finite(position?.entryFundamentalScore),
    analyst: finite(position?.entryAnalystScore),
  };
  const comparableCurrentScore = hasCompleteScoreSet(scores) ? weightedScore(scores) : null;
  const comparableEntryScore = hasCompleteScoreSet(entryScores) ? weightedScore(entryScores) : null;
  const scoreChange = comparableCurrentScore != null && comparableEntryScore != null
    ? comparableCurrentScore - comparableEntryScore
    : null;

  let context = 'Geen duidelijke technische trigger. Positie volgen.';
  if (addTrigger != null && price <= addTrigger) context = 'Koers staat minimaal 7,5% onder de aankoopprijs. Alleen bij voldoende bevestiging van Trader, Technical, Fundamentals en Analyst komt ADD in beeld.';
  else if (support && price <= support * 1.01) context = 'Koers zit in of vlak boven de technische koopzone rond steun, maar de 7,5%-drempel voor ADD is leidend.';
  else if (firstTarget && price >= firstTarget * 0.97) context = 'Koers nadert de eerste technische weerstand. Nieuwe koop is hier minder aantrekkelijk.';
  else if (sma20 && sma50 && price > sma20 && price > sma50) context = 'Koers ligt boven de 20- en 50-daagse trend. Technisch beeld is sterk.';
  else if (sma20 && price > sma20) context = 'Koers ligt boven de 20-daagse trend. Korte trend is positief.';
  else if (sma20) context = 'Koers ligt onder de 20-daagse trend. Wacht op technische verbetering.';

  return {
    price, entryPrice, gain,
    traderScore: scores.trader,
    technicalScore: scores.technical,
    fundamentalScore: scores.fundamental,
    analystScore: scores.analyst,
    comparableCurrentScore, comparableEntryScore, scoreChange,
    support, resistance: firstTarget, stop, riskPct, addLow, addHigh, addTrigger,
    firstTarget, secondTarget, targetUpside, rewardRisk, analystTarget, high52, sma20, sma50, atrPct, context,
  };
}

export function getPortfolioAction(position, result, plan = buildTradePlan(position, result)) {
  if (!result || !plan) return { label: 'GEEN DATA', tone: 'neutral', reason: 'De scanner heeft momenteel geen actuele data voor deze positie.' };

  const {
    price, gain, comparableCurrentScore, scoreChange, stop, firstTarget, secondTarget,
    targetUpside, rewardRisk, addTrigger, analystTarget, technicalScore,
    fundamentalScore, traderScore, analystScore,
  } = plan;
  const profitable = gain != null && gain > 0;
  const nearStop = price <= stop * 1.01;
  const analystTargetReached = analystTarget > 0 && price >= analystTarget * 0.98;
  const secondTargetReached = secondTarget && price >= secondTarget * 0.98;
  const firstTargetReached = firstTarget && price >= firstTarget * 0.98;
  const belowAddTrigger = addTrigger != null && price <= addTrigger;

  // A losing position is never converted into SELL. SELL is only available while the position is profitable.
  if (profitable && nearStop) return { label: 'SELL', tone: 'sell', reason: 'De koers heeft de vooraf bepaalde risicogrens bereikt terwijl de positie winstgevend is. Winst beschermen.' };
  if (profitable && comparableCurrentScore != null && comparableCurrentScore < 60) return { label: 'SELL', tone: 'sell', reason: 'De vier scannercomponenten geven samen een totaalscore onder 60. De setup is verzwakt terwijl de positie winstgevend is.' };
  if (profitable && scoreChange != null && scoreChange <= -10) return { label: 'SELL', tone: 'sell', reason: 'De gewogen score van Trader, Technical, Fundamentals en Analyst is minimaal 10 punten verslechterd sinds aankoop.' };
  if (profitable && analystTargetReached) return { label: 'SELL', tone: 'sell', reason: 'Het gemiddelde analistenkoersdoel is vrijwel bereikt en de positie staat op winst. Winst nemen is nu rationeler dan verder bijkopen.' };
  if (profitable && secondTargetReached) return { label: 'SELL', tone: 'sell', reason: 'Het tweede koersdoel is bereikt en de positie staat op winst. Overweeg winst te nemen of de positie gedeeltelijk af te bouwen.' };

  const strongSetup = comparableCurrentScore != null && comparableCurrentScore >= 82
    && traderScore != null && traderScore >= 70
    && technicalScore != null && technicalScore >= 70
    && fundamentalScore != null && fundamentalScore >= 60
    && analystScore != null && analystScore > 0;
  const enoughUpside = targetUpside != null && targetUpside >= 0.08;
  const acceptableRiskReward = rewardRisk != null && rewardRisk >= 2;
  const notTooCloseToTarget = !(firstTargetReached || (analystTarget > 0 && price >= analystTarget * 0.95));

  if (strongSetup && belowAddTrigger && enoughUpside && acceptableRiskReward && notTooCloseToTarget) {
    return { label: 'ADD', tone: 'add', reason: `Sterke scanner-score over Trader, Technical, Fundamentals en Analyst. De positie staat minimaal 7,5% onder aankoop en biedt ${rewardRisk.toFixed(1)}x risk/reward.` };
  }
  if (firstTargetReached && secondTarget && secondTarget > price * 1.03) {
    return { label: 'HOLD', tone: 'hold', reason: 'Eerste weerstand is bereikt. Geen nieuwe aankoop hier. Houd de positie voor het tweede koersdoel en overweeg eventueel gedeeltelijke winstneming.' };
  }
  if (strongSetup && addTrigger != null && price > addTrigger) {
    return { label: 'HOLD', tone: 'hold', reason: 'De scanner-score is sterk, maar ADD verschijnt pas wanneer de positie minimaal 7,5% onder de aankoopprijs staat.' };
  }
  return {
    label: 'HOLD',
    tone: 'hold',
    reason: profitable
      ? 'De positie staat op winst, maar er is geen duidelijke SELL-trigger. De scanner-score en technische niveaus rechtvaardigen aanhouden.'
      : 'De positie staat niet op winst. Daarom wordt geen SELL-signaal gegeven. Wacht op herstel of een duidelijke ADD-trigger.',
  };
}
