from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
import json, math
from pathlib import Path
import numpy as np
import pandas as pd

ENGINE_VERSION = 4
WEIGHTS = {"technical":30,"fundamentals":20,"valuation":10,"analysts":15,"catalysts":10,"institutional":5,"macro_sector":5,"liquidity_risk":5}
NEW_BUY_SCORE_PREFERRED = 85.0
MATERIAL_SCORE_DELTA = 4.0
MATERIAL_PRICE_DELTA = 0.05
PATH_RULES = {"25pct_1m":{"min_upside":.25,"max_days":31,"min_probability":.35},"50pct_3m":{"min_upside":.50,"max_days":93,"min_probability":.35},"100pct_12m":{"min_upside":1.00,"max_days":365,"min_probability":.30}}

class Action(str,Enum):
    BUY="BUY"; ADD="ADD"; HOLD="HOLD"; HOLD_CHANGE="HOLD-CHANGE"; PARTIAL_TAKE_PROFIT="PARTIAL TAKE PROFIT"; TAKE_PROFIT="TAKE PROFIT"; EXIT="EXIT"; NONE="NONE"
class SetupType(str,Enum):
    HIGH_BETA_MEAN_REVERSION="high-beta mean reversion"; QUALITY_VALUE_PULLBACK="quality/value pullback"; STRUCTURAL_GROWTH="structural growth"; VALUE_TRAP="structural deterioration / value trap"

@dataclass
class TechnicalData:
    change_1d:float=0.; change_5d:float=0.; rsi14:float|None=None; volume_ratio_20d:float|None=None; atr_percent:float|None=None; close_position_in_day_range:float|None=None; drawdown_from_recent_high:float|None=None; distance_to_support:float|None=None; above_ma20:bool|None=None; above_ma50:bool|None=None; above_ma200:bool|None=None; reversal_confirmation:float=0.; trend_structure:float=.5
@dataclass
class Fundamentals:
    revenue_growth:float=0.; eps_growth:float|None=None; gross_margin_quality:float=.5; free_cash_flow_quality:float=.5; balance_sheet_quality:float=.5; cash_runway_quality:float=.5; leverage_risk:float=.5; dilution_risk:float=0.; thesis_broken:bool=False
@dataclass
class ValuationData:
    discount_to_history:float=0.; discount_to_peers:float=0.; independent_fair_value_upside:float=0.
@dataclass
class AnalystData:
    consensus_score:float=.5; avg_target_upside:float=0.; target_revision_direction:float=0.; earnings_revision_direction:float=0.; revenue_revision_direction:float=0.; fresh_target_count:int=0; stale_target_penalty:float=0.
@dataclass
class CatalystData:
    one_month_strength:float=0.; three_month_strength:float=0.; twelve_month_strength:float=0.; nearest_days:int|None=None; description:list[str]=field(default_factory=list)
@dataclass
class MarketContext:
    institutional_sentiment:float=.5; insider_signal:float=.5; short_interest_risk:float=0.; sector_strength:float=.5; macro_support:float=.5; liquidity_quality:float=1.; spread_quality:float=1.
@dataclass
class Scenario:
    name:str; return_pct:float; probability:float; horizon_days:int
@dataclass
class TradingPlan:
    entry_low:float|None=None; entry_high:float|None=None; add_low:float|None=None; add_high:float|None=None; invalidation:float|None=None; tp1:float|None=None; tp2:float|None=None
@dataclass
class StockSnapshot:
    ticker:str; company:str; price:float; is_existing_position:bool=False; was_previously_signaled:bool=False; setup_type:SetupType=SetupType.QUALITY_VALUE_PULLBACK; technical:TechnicalData=field(default_factory=TechnicalData); fundamentals:Fundamentals=field(default_factory=Fundamentals); valuation:ValuationData=field(default_factory=ValuationData); analysts:AnalystData=field(default_factory=AnalystData); catalysts:CatalystData=field(default_factory=CatalystData); context:MarketContext=field(default_factory=MarketContext); scenarios:list[Scenario]=field(default_factory=list); plan:TradingPlan=field(default_factory=TradingPlan); data_quality:float=1.; notes:list[str]=field(default_factory=list)
@dataclass
class PreviousAlert:
    ticker:str; action:Action; score:float; price:float; thesis_version:str=""; catalyst_version:str=""; analyst_revision_version:str=""
@dataclass
class Evaluation:
    ticker:str; score:float; score_label:str; component_scores:dict[str,float]; action:Action; qualifies_new_buy:bool; qualifying_paths:list[str]; expected_return:float; risk_reward:float|None; confidence:float; reasons:list[str]; warnings:list[str]; should_alert:bool

def clamp(x,lo=0.,hi=1.): return max(lo,min(hi,float(x)))
def scale(x,low,high): return 0. if high==low else clamp((x-low)/(high-low))
def score_label(s): return "uitzonderlijk sterk" if s>=90 else "zeer sterk" if s>=85 else "sterk maar niet uitzonderlijk" if s>=80 else "redelijk/interessant, onvoldoende voor nieuw BUY-signaal" if s>=70 else "zwak/onvoldoende"

def score_technical(t):
    reasons=[]; d=0.
    d += .15*scale(-t.change_1d,.03,.12)+.15*scale(-t.change_5d,.08,.25)
    if t.drawdown_from_recent_high is not None: d += .15*scale(t.drawdown_from_recent_high,.15,.50)
    if t.rsi14 is not None:
        if t.rsi14<35: d += .10*scale(35-t.rsi14,0,20); reasons.append(f"RSI14 laag ({t.rsi14:.1f})")
        elif t.rsi14<=50: d += .05
    if t.volume_ratio_20d is not None:
        d += .10*scale(t.volume_ratio_20d,1.2,3.0)
        if t.volume_ratio_20d>=1.5: reasons.append(f"volume {t.volume_ratio_20d:.1f}x 20d")
    d += .25*clamp(t.reversal_confirmation)
    if t.reversal_confirmation>=.7: reasons.append("duidelijke reversalbevestiging")
    d += .05*clamp(t.trend_structure)
    if t.distance_to_support is not None: d += .05*(1-scale(t.distance_to_support,.02,.12))
    return clamp(d),reasons

def score_fundamentals(f):
    if f.thesis_broken:return 0.
    growth=.25*scale(f.revenue_growth,0,.60)
    eps=.05 if f.eps_growth is None else .10*scale(f.eps_growth,-.20,.60)
    quality=.15*clamp(f.gross_margin_quality)+.15*clamp(f.free_cash_flow_quality)+.15*clamp(f.balance_sheet_quality)+.10*clamp(f.cash_runway_quality)
    return clamp(growth+eps+quality-.05*clamp(f.leverage_risk)-.05*clamp(f.dilution_risk))

def score_valuation(v): return clamp(.30*scale(v.discount_to_history,-.20,.40)+.25*scale(v.discount_to_peers,-.20,.40)+.45*scale(v.independent_fair_value_upside,0,1))
def score_analysts(a): return clamp(.25*clamp(a.consensus_score)+.20*scale(a.avg_target_upside,0,1)+.20*scale(a.target_revision_direction,-1,1)+.20*scale(a.earnings_revision_direction,-1,1)+.10*scale(a.revenue_revision_direction,-1,1)+.05*scale(a.fresh_target_count,0,6)-.15*clamp(a.stale_target_penalty))
def score_catalysts(c):
    near=0. if c.nearest_days is None else .10*(1-scale(c.nearest_days,7,180))
    return clamp(.35*clamp(c.one_month_strength)+.30*clamp(c.three_month_strength)+.25*clamp(c.twelve_month_strength)+near)
def score_institutional(c): return clamp(.70*clamp(c.institutional_sentiment)+.30*clamp(c.insider_signal))
def score_macro_sector(c): return clamp(.60*clamp(c.sector_strength)+.40*clamp(c.macro_support))
def score_liquidity_risk(c,f): return clamp(.45*clamp(c.liquidity_quality)+.25*clamp(c.spread_quality)-.15*clamp(c.short_interest_risk)-.10*clamp(f.dilution_risk)-.05*clamp(f.leverage_risk))
def calculate_opportunity_score(s):
    tech,reasons=score_technical(s.technical)
    n={"technical":tech,"fundamentals":score_fundamentals(s.fundamentals),"valuation":score_valuation(s.valuation),"analysts":score_analysts(s.analysts),"catalysts":score_catalysts(s.catalysts),"institutional":score_institutional(s.context),"macro_sector":score_macro_sector(s.context),"liquidity_risk":score_liquidity_risk(s.context,s.fundamentals)}
    score=sum(n[k]*WEIGHTS[k] for k in WEIGHTS)*(0.90+0.10*clamp(s.data_quality))
    if s.fundamentals.thesis_broken: score=min(score,55); reasons.append("fundamentele thesis gebroken")
    return round(score,1),n,reasons

def scenario_expected_return(ss):
    if not ss:return 0.
    p=sum(x.probability for x in ss); return 0. if p<=0 else sum(x.return_pct*x.probability for x in ss)/p
def qualifying_paths(s):
    return [name for name,r in PATH_RULES.items() if sum(x.probability for x in s.scenarios if x.return_pct>=r['min_upside'] and x.horizon_days<=r['max_days'])>=r['min_probability']]
def calculate_risk_reward(s):
    if not s.plan.invalidation or not s.plan.tp1 or s.price<=0:return None
    risk=(s.price-s.plan.invalidation)/s.price; reward=(s.plan.tp1-s.price)/s.price
    return reward/risk if risk>0 else None

def choose_action(s,score,paths):
    reasons=[]; warnings=[]
    existing=s.is_existing_position or s.was_previously_signaled
    if s.fundamentals.thesis_broken:return (Action.EXIT if existing else Action.NONE),reasons,["thesis-breaking nieuws/fundamentals"]
    if s.context.liquidity_quality<.45 or s.context.spread_quality<.45:
        warnings.append("liquiditeit/spread onvoldoende")
        if not existing:return Action.NONE,reasons,warnings
    if not existing:
        if not paths: warnings.append("geen hard rendementspad gehaald"); return Action.NONE,reasons,warnings
        if score<85: warnings.append("score onder voorkeursdrempel 85"); return Action.NONE,reasons,warnings
        if s.technical.reversal_confirmation<.55: warnings.append("reversal nog onvoldoende bevestigd"); return Action.NONE,reasons,warnings
        if s.fundamentals.dilution_risk>.75 or s.fundamentals.leverage_risk>.85: warnings.append("financierings-/dilutierisico te hoog"); return Action.NONE,reasons,warnings
        return Action.BUY,reasons+[f"kwalificeert via {', '.join(paths)}"],warnings
    over=(s.technical.rsi14 is not None and s.technical.rsi14>=75) or (s.plan.tp1 is not None and s.price>=s.plan.tp1)
    if score<60:return Action.EXIT,reasons+["Opportunity score onder 60"],warnings
    if s.plan.tp2 is not None and s.price>=s.plan.tp2:return Action.TAKE_PROFIT,reasons+["TP2 bereikt"],warnings
    if over:return Action.PARTIAL_TAKE_PROFIT,reasons+["Setup is overextended of TP1 bereikt"],warnings
    if score>=85 and s.technical.reversal_confirmation>=.70 and s.analysts.earnings_revision_direction>=-.15 and s.analysts.revenue_revision_direction>=-.15:return Action.ADD,reasons+["Sterke score, reversal en analistenrevisies"],warnings
    return Action.HOLD,reasons+["Bestaande positie blijft binnen de actieband"],warnings

def _load_previous():
    p=Path("public/data/alert_history.json")
    if not p.exists():return {}
    try:
        raw=json.loads(p.read_text()); items=raw.get('alerts',raw) if isinstance(raw,dict) else raw
        return {str(x.get('ticker')).upper():x for x in items if isinstance(x,dict) and x.get('ticker')}
    except Exception:return {}

def _setup(s,t,f,v):
    if s.fundamentals.thesis_broken or (f<.35 and v<.45):return SetupType.VALUE_TRAP.value
    if s.technical.reversal_confirmation>=.55 and t>=.70:return SetupType.HIGH_BETA_MEAN_REVERSION.value
    if f>=.70 and v>=.60 and t<.65:return SetupType.QUALITY_VALUE_PULLBACK.value
    if f>=.70:return SetupType.STRUCTURAL_GROWTH.value
    if v>=.70 and f>=.55:return SetupType.QUALITY_VALUE_PULLBACK.value
    return SetupType.STRUCTURAL_GROWTH.value if f>=t else SetupType.HIGH_BETA_MEAN_REVERSION.value

def _map_row(r):
    def f(k,d=None):
        try:
            x=r.get(k); return d if x is None or (isinstance(x,float) and not math.isfinite(x)) else float(x)
        except:return d
    dd=max(0.,-f('distance_1m_high',0.))
    d20=f('distance_sma20'); d50=f('distance_sma50'); d200=f('distance_sma200')
    ma=[x for x in (d20,d50,d200) if x is not None]
    trend=.5 if not ma else clamp(1-sum(max(0,-x) for x in ma)/len(ma)/.30)
    selloff=max(0., min(1., .40*scale(-f('return_1d',0),.01,.12)+.40*scale(-f('return_5d',0),.04,.25)+.20*scale(dd,.15,.50)))
    close=f('close_location',.5); vals=[]
    if close is not None: vals.append(scale(close,.5,1))
    one=f('return_1d'); five=f('return_5d')
    if one is not None: vals.append(scale(one,.005,.08))
    if five is not None: vals.append(scale(five,-.10,.10))
    macdchg=f('macd_histogram_change'); hist=f('macd_histogram',0.)
    if macdchg is not None: vals.append(clamp(.5+macdchg/(2*max(abs(hist),.01))))
    reversal=selloff*(sum(vals)/len(vals) if vals else 0.) if selloff>.05 else 0.
    debt=f('debt_equity'); debtq=.5 if debt is None else 1-clamp(debt/1.5)
    gm=f('gross_margin'); gmq=.5 if gm is None else scale(gm,.20,.60)
    fcfm=f('fcf_margin'); fcfq=.5 if fcfm is None else scale(fcfm,0,.25)
    cash=f('cash'); cashq=.5 if cash is None else clamp(math.log10(max(cash,1))/12)
    pevs=f('pe_vs_sector'); discpeers=0. if pevs is None else 1-pevs
    target=f('analyst_target_upside',0.) or 0.
    bullish=f('analyst_bullish_changes_30d',0.) or 0.; bearish=f('analyst_bearish_changes_30d',0.) or 0.
    targetrev=clamp(.5+.08*(bullish-bearish))*2-1
    count=int(f('analyst_count',0) or 0)
    stale=1. if r.get('analyst_cache_stale') else 0.
    sector=f('sector_relative_strength_20d',0.) or 0.; market=f('market_regime_score',.5) or .5
    dollar=f('avg_dollar_volume_20d'); liq=.5 if dollar is None else clamp((math.log10(max(dollar,1))-6)/3)
    earnings_days=None
    if r.get('next_earnings_date'):
        try:
            dt=pd.Timestamp(r['next_earnings_date']); now=pd.Timestamp.now(tz=dt.tz if dt.tzinfo else 'UTC'); earnings_days=max(0,int((dt-now).total_seconds()/86400))
        except: pass
    desc=[]
    if earnings_days is not None and earnings_days<=45: desc.append('Volgende kwartaalcijfers')
    if r.get('recent_news'): desc.append('Recente nieuwsflow beschikbaar')
    data_fields=['return_1d','return_5d','rsi_14','volume_ratio','distance_1m_high','close_location','macd_histogram_change','revenue_growth','eps_growth','gross_margin','fcf_margin','roe','debt_equity','pe','forward_pe','peg','analyst_consensus_score','analyst_target_mean','analyst_count']
    quality=sum(f(k) is not None for k in data_fields)/len(data_fields)
    t=TechnicalData(f('return_1d',0),f('return_5d',0),f('rsi_14'),f('volume_ratio'),f('atr_pct'),close,dd,f('distance_support_20d'),d20 is not None and d20>=0,d50 is not None and d50>=0,d200 is not None and d200>=0,reversal,trend)
    fs=Fundamentals(f('revenue_growth',0),f('eps_growth'),gmq,fcfq,debtq,cashq,1-debtq,0,bool(r.get('thesis_broken')))
    v=ValuationData(0.,discpeers,0.)
    a=AnalystData((f('analyst_consensus_score',50) or 50)/100,target,targetrev,0.,0.,count,stale)
    c=CatalystData(0.,0.,0.,earnings_days,desc)
    ctx=MarketContext(.5,.5,0.,clamp((sector+.20)/.40),market,liq,1.)
    scenarios=[]
    if isinstance(r.get('scenarios'),list):
        for x in r['scenarios']:
            if isinstance(x,dict):
                try:scenarios.append(Scenario(x['name'],float(x['return_pct']),float(x['probability']),int(x['horizon_days'])))
                except:pass
    price=f('price',0) or 0; atr=f('atr_pct',.06) or .06
    plan=TradingPlan(price*(1-min(.08,max(.02,atr*.5))),price*(1+min(.02,max(.005,atr*.15))),price*(1-min(.12,max(.04,atr))),price*(1-min(.08,max(.02,atr*.5))),price*(1-min(.18,max(.07,atr*1.5))),price*1.25,price*1.50)
    return StockSnapshot(str(r.get('ticker','')),str(r.get('company_name',r.get('ticker',''))),price,technical=t,fundamentals=fs,valuation=v,analysts=a,catalysts=c,context=ctx,scenarios=scenarios,plan=plan,data_quality=quality)

def evaluate_row(row,previous=None):
    s=_map_row(row); score,normalized,reasons=calculate_opportunity_score(s); paths=qualifying_paths(s); action,ar,warnings=choose_action(s,score,paths); reasons=(reasons+ar)[:8]; rr=calculate_risk_reward(s); expected=scenario_expected_return(s.scenarios)
    confidence=clamp(.45*s.data_quality+.20*s.technical.reversal_confirmation+.20*s.analysts.consensus_score+.15*(1-s.fundamentals.dilution_risk))*100
    prev_score=None if not previous else previous.get('opportunity_score',previous.get('score')); prev_price=None if not previous else previous.get('price')
    delta=abs(score-float(prev_score)) if prev_score is not None else None; pdelta=abs(s.price/float(prev_price)-1) if prev_price and s.price else None
    material=previous is None or action not in (Action.NONE,Action.HOLD) or (delta is not None and delta>=4) or (pdelta is not None and pdelta>=.05)
    should=action not in (Action.NONE,Action.HOLD) and material
    setup=_setup(s,normalized['technical'],normalized['fundamentals'],normalized['valuation'])
    breakdown={k:round(normalized[k]*WEIGHTS[k],2) for k in WEIGHTS}
    out={'opportunity_score':score,'score_label':score_label(score),'component_scores':{k:round(v*100,1) for k,v in normalized.items()},'score_breakdown':breakdown,'action':action.value,'qualifies_new_buy':action==Action.BUY,'should_alert':should,'qualifying_paths':paths,'scenarios':[x.__dict__ for x in s.scenarios],'expected_return':expected,'risk_reward':round(rr,2) if rr is not None else None,'confidence':round(confidence,1),'reasons':reasons,'warnings':warnings,'reversal_confirmation':round(s.technical.reversal_confirmation,3),'catalyst_description':' '.join(s.catalysts.description) if s.catalysts.description else None,'catalyst_nearest_days':s.catalysts.nearest_days,'trading_plan':s.plan.__dict__,'data_quality':round(s.data_quality,3),'material_change':material,'previous_score':prev_score,'score_delta':round(delta,1) if delta is not None else None,'price_delta':round(pdelta,4) if pdelta is not None else None,'setup_type':setup}
    return out

def apply_opportunity_engine(frame):
    if frame is None or frame.empty:return frame
    prev=_load_previous(); out=frame.copy(); ev=[evaluate_row(row.to_dict(),prev.get(str(row.get('ticker','')).upper())) for _,row in out.iterrows()]
    for k in ['opportunity_score','score_label','action','qualifies_new_buy','should_alert','expected_return','risk_reward','confidence','reversal_confirmation','catalyst_description','catalyst_nearest_days','data_quality','material_change','previous_score','score_delta','price_delta','setup_type']:out[k]=[e[k] for e in ev]
    for k in ['component_scores','score_breakdown','qualifying_paths','scenarios','reasons','warnings','trading_plan']:out[k]=[e[k] for e in ev]
    for n in WEIGHTS:out[f'opportunity_{n}_score']=[e['component_scores'][n] for e in ev]; out[f'opportunity_{n}_weighted']=[e['score_breakdown'][n] for e in ev]
    return out.sort_values(['opportunity_score','ticker'],ascending=[False,True]).reset_index(drop=True)
