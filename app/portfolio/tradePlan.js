const finite = (value) => Number.isFinite(Number(value)) ? Number(value) : null;

function uniqueSorted(values, direction = 'asc') {
  return [...new Set(values.filter((value) => Number.isFinite(value)))].sort((a, b) => direction === 'asc' ? a - b : b - a);
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

  return {lows:uniqueSorted(lows,'desc'),highs:uniqueSorted(highs,'asc')};
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
  const pivotSupport = pivots.lows.filter((level) => level < price).sort((a,b) => b-a)[0] || null;
  if (pivotSupport && (!support || pivotSupport > support)) support = pivotSupport;

  const resistanceLevels = [
    ...pivots.highs.filter((level) => level > price * 1.01),
    ...(sma20 && sma20 > price * 1.01 ? [sma20] : []),
    ...(sma50 && sma50 > price * 1.01 ? [sma50] : []),
  ];
  const resistances = uniqueSorted(resistanceLevels,'asc');
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
  } else if (high52 && high52 > price * 1.02) {
    secondTarget = high52;
  }
  if (!secondTarget && analystTarget && analystTarget > price * 1.02 && analystTarget !== firstTarget) secondTarget = analystTarget;
  if (!firstTarget && secondTarget) firstTarget = secondTarget;

  const supportLevel = support || price * (1 - atrPct);
  const stop = Math.max(0.01, supportLevel - price * atrPct * 0.5);
  const riskPct = price > stop ? 1 - stop / price : null;

  const addLow = support ? Math.max(stop, support * 0.99) : stop;
  const addHigh = support ? support * 1.02 : price * Math.max(0.94, 1 - atrPct * 0.5);

  const target = secondTarget || firstTarget;
  const targetUpside = target && target > price ? target / price - 1 : null;
  const rewardRisk = targetUpside != null && riskPct > 0 ? targetUpside / riskPct : null;

  const score = finite(result?.overall_score);
  const technicalScore = finite(result?.technical_score);
  const entryScore = finite(position?.entryScore);
  const entryPrice = finite(position?.entryPrice);
  const gain = entryPrice && entryPrice > 0 ? price / entryPrice - 1 : null;
  const scoreChange = entryScore != null && score != null ? score - entryScore : null;

  let context = 'Geen duidelijke technische trigger. Positie volgen.';
  if (support && price <= addHigh * 1.01) context = 'Koers zit in of vlak boven de technische koopzone rond steun.';
  else if (firstTarget && price >= firstTarget * 0.97) context = 'Koers nadert de eerste technische weerstand. Nieuwe koop is hier minder aantrekkelijk.';
  else if (sma20 && sma50 && price > sma20 && price > sma50) context = 'Koers ligt boven de 20- en 50-daagse trend. Technisch beeld is sterk.';
  else if (sma20 && price > sma20) context = 'Koers ligt boven de 20-daagse trend. Korte trend is positief.';
  else if (sma20) context = 'Koers ligt onder de 20-daagse trend. Wacht op technische verbetering.';

  return {price,entryPrice,gain,score,technicalScore,entryScore,scoreChange,support,stop,riskPct,addLow,addHigh,firstTarget,secondTarget,targetUpside,rewardRisk,analystTarget,high52,sma20,sma50,atrPct,context};
}

export function getPortfolioAction(position,result,plan=buildTradePlan(position,result)) {
  if(!result||!plan)return{label:'GEEN DATA',tone:'neutral',reason:'De scanner heeft momenteel geen actuele data voor deze positie.'};

  const {price,gain,score,technicalScore,scoreChange,stop,firstTarget,secondTarget,targetUpside,rewardRisk,addLow,addHigh,analystTarget}=plan;
  const nearStop=price<=stop*1.01;
  const analystTargetReached=analystTarget>0&&price>=analystTarget*0.98;
  const secondTargetReached=secondTarget&&price>=secondTarget*0.98;
  const firstTargetReached=firstTarget&&price>=firstTarget*0.98;
  const inAddZone=price>=addLow*0.98&&price<=addHigh*1.02;

  if(nearStop)return{label:'SELL',tone:'sell',reason:'De koers heeft de vooraf bepaalde risicogrens bereikt. Bescherm het kapitaal.'};
  if(score!=null&&score<60)return{label:'SELL',tone:'sell',reason:'De totaalscore is onder 60 gezakt. De oorspronkelijke setup is te zwak geworden.'};
  if(scoreChange!=null&&scoreChange<=-10)return{label:'SELL',tone:'sell',reason:'De totaalscore is minimaal 10 punten verslechterd sinds aankoop.'};
  if(analystTargetReached&&(gain==null||gain>0.05))return{label:'SELL',tone:'sell',reason:'Het gemiddelde analistenkoersdoel is vrijwel bereikt. Winst nemen is nu rationeler dan verder bijkopen.'};
  if(secondTargetReached&&gain!=null&&gain>0.05)return{label:'SELL',tone:'sell',reason:'Het tweede koersdoel is bereikt. Overweeg winst te nemen of de positie gedeeltelijk af te bouwen.'};

  const strongSetup=score!=null&&score>=82&&technicalScore!=null&&technicalScore>=70;
  const enoughUpside=targetUpside==null||targetUpside>=0.08;
  const acceptableRiskReward=rewardRisk==null||rewardRisk>=2;
  const notTooCloseToTarget=!(firstTargetReached||(analystTarget>0&&price>=analystTarget*0.95));
  const scoreHealthy=scoreChange==null||scoreChange>=-3;

  if(strongSetup&&inAddZone&&enoughUpside&&acceptableRiskReward&&notTooCloseToTarget&&scoreHealthy)return{label:'ADD',tone:'add',reason:`Sterke score en technische bevestiging. De koers zit in de koopzone met ${rewardRisk?`${rewardRisk.toFixed(1)}x`:'voldoende'} risk/reward.`};
  if(firstTargetReached&&secondTarget&&secondTarget>price*1.03)return{label:'HOLD',tone:'hold',reason:'Eerste weerstand is bereikt. Geen nieuwe aankoop hier. Houd de positie voor het tweede koersdoel en overweeg eventueel gedeeltelijke winstneming.'};
  if(strongSetup&&!inAddZone)return{label:'HOLD',tone:'hold',reason:'De setup blijft sterk, maar de koers staat buiten de optimale koopzone. Wacht liever op een betere instap.'};
  return{label:'HOLD',tone:'hold',reason:'De positie blijft binnen de normale risicobandbreedte. Geen duidelijke ADD- of SELL-trigger.'};
}
