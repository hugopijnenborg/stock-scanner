from __future__ import annotations
from pathlib import Path
import json,math
from typing import Any
import numpy as np
import pandas as pd
ENGINE_VERSION=2
WEIGHTS={'technical':30,'fundamentals':20,'valuation':10,'analysts':15,'catalysts':10,'institutional':5,'macro_sector':5,'liquidity_risk':5}
NEW_BUY_SCORE_PREFERRED=85.0
MATERIAL_SCORE_DELTA=4.0
MATERIAL_PRICE_DELTA=0.05
PATH_RULES={'25pct_1m':{'min_upside':0.25,'max_days':31,'min_probability':0.35},'50pct_3m':{'min_upside':0.50,'max_days':93,'min_probability':0.35},'100pct_12m':{'min_upside':1.00,'max_days':365,'min_probability':0.30}}

def _f(v:Any,default:float|None=None)->float|None:
    try:
        if v is None or (isinstance(v,str) and not v.strip()):return default
        x=float(v);return x if math.isfinite(x) else default
    except Exception:return default

def _clamp(x:float,lo:float=0.0,hi:float=1.0)->float:return float(np.clip(x,lo,hi))
def _norm(v:Any,default:float=0.5)->float:
    x=_f(v);return default if x is None else _clamp(x)
def _positive_scale(v:Any,start:float,strong:float)->float:
    x=_f(v)
    if x is None:return 0.5
    if x<=start:return 0.0
    return _clamp((x-start)/(strong-start))
def _negative_scale(v:Any,start:float,extreme:float)->float:
    x=_f(v)
    if x is None:return 0.5
    if x>=start:return 0.0
    return _clamp((start-x)/(start-extreme))
def _target_upside(r:dict[str,Any])->float|None:
    u=_f(r.get('analyst_target_upside'))
    if u is not None:return u
    cur=_f(r.get('analyst_target_current')) or _f(r.get('price'));mean=_f(r.get('analyst_target_mean'))
    return mean/cur-1.0 if cur and mean else None

def score_technical(r:dict[str,Any])->tuple[float,float]:
    selloff=.30*_negative_scale(r.get('return_1d'),-.01,-.15)+.30*_negative_scale(r.get('return_5d'),-.04,-.30)+.20*_negative_scale(r.get('return_20d'),-.05,-.40)+.20*_negative_scale(r.get('distance_52w_high'),-.05,-.50)
    rsi=_negative_scale(r.get('rsi_14'),45,20);volume=_positive_scale(r.get('volume_ratio'),1.0,4.0);support=1-_clamp(float(np.mean([_f(r.get('distance_support_20d'),.10),_f(r.get('distance_support_60d'),.10),_f(r.get('distance_support_120d'),.10)]))/.10);reversal=reversal_confirmation(r)
    trend=.45*_clamp((_f(r.get('distance_sma20'),0)+.20)/.40)+.35*_clamp((_f(r.get('distance_sma50'),0)+.25)/.50)+.20*_clamp((_f(r.get('distance_sma200'),0)+.30)/.60);td_bonus=.08 if (_f(r.get('td_setup_count')) or _f(r.get('td_countdown_count')) or 0)>=9 and reversal>=.55 else 0;sector=_clamp((_f(r.get('sector_relative_strength_20d'),0)+.20)/.40)
    return 100*_clamp(.27*selloff+.13*rsi+.10*volume+.08*support+.25*reversal+.12*trend+.05*sector+td_bonus),reversal

def reversal_confirmation(r:dict[str,Any])->float:
    signals=[];close=_f(r.get('close_location'));one=_f(r.get('return_1d'));change=_f(r.get('macd_histogram_change'));hist=_f(r.get('macd_histogram'),0);intra=_f(r.get('intraday_score'))
    if close is not None:signals.append(_clamp((close-.45)/.55))
    if one is not None:signals.append(_clamp((one+.15)/.20))
    if change is not None:signals.append(_clamp((change+abs(hist or 0))/(abs(hist or 0)+1e-9)))
    if intra is not None:signals.append(_clamp(intra/100))
    return float(np.mean(signals)) if signals else 0

def score_fundamentals(r:dict[str,Any])->float:
    if bool(r.get('thesis_broken')):return 0
    growth=.5*_positive_scale(r.get('revenue_growth'),0,.30)+.5*_positive_scale(r.get('eps_growth'),0,.40);quality=.35*_positive_scale(r.get('gross_margin'),.20,.60)+.35*_positive_scale(r.get('fcf_margin'),0,.25)+.30*_positive_scale(r.get('roe'),.10,.30);leverage=1-_clamp((_f(r.get('debt_equity'),.5) or .5)/1.5);dilution=1-_norm(r.get('dilution_risk'),0)
    return 100*_clamp(.45*growth+.35*quality+.12*leverage+.08*dilution)

def score_valuation(r:dict[str,Any])->float:
    pe=_f(r.get('pe'));fpe=_f(r.get('forward_pe'));peg=_f(r.get('peg'));target=_target_upside(r);a=_clamp((35-pe)/25) if pe is not None and pe>0 else .5;b=_clamp((30-fpe)/22) if fpe is not None and fpe>0 else .5;c=_clamp((2-peg)/1.5) if peg is not None and peg>0 else .5;d=_clamp((target+.10)/.60) if target is not None else .5
    return 100*(.25*a+.25*b+.20*c+.30*d)

def score_analysts(r:dict[str,Any])->float:
    consensus=_norm((_f(r.get('analyst_consensus_score'),50) or 50)/100);target=_clamp((_target_upside(r)+.10)/.60) if _target_upside(r) is not None else .5;changes=_f(r.get('analyst_bullish_changes_30d'),0) or 0;bearish=_f(r.get('analyst_bearish_changes_30d'),0) or 0;revision=_clamp(.5+.08*(changes-bearish));fresh=_clamp((_f(r.get('analyst_count'),0) or 0)/20);stale=_norm(r.get('analyst_cache_stale'),0);raw=.25*consensus+.20*target+.20*revision+.20*revision+.10*revision+.05*fresh
    return 100*_clamp(raw*(1-.15*stale))

def score_catalysts(r:dict[str,Any])->tuple[float,str|None,int|None]:
    days=None;earnings=r.get('next_earnings_date')
    if earnings:
        try:
            dt=pd.Timestamp(earnings);now=pd.Timestamp.now(tz=dt.tz if dt.tzinfo else 'UTC');days=max(0,int((dt-now).total_seconds()/86400))
        except Exception:days=None
    if days is not None and days<=45:return 75,'Volgende kwartaalcijfers',days
    if r.get('recent_news'):return 60,'Recente nieuwsflow beschikbaar',days
    return 40,None,days

def score_market_and_risk(r:dict[str,Any])->tuple[float,float,float,list[str]]:
    warnings=[];institutional=_norm(r.get('institutional_sentiment'),.5);sector=_f(r.get('sector_relative_strength_20d'));sector_score=_clamp((sector+.20)/.40) if sector is not None else .5;market=_f(r.get('market_regime_score'));macro=.55*(market if market is not None else .5)+.45*sector_score;dollar=_f(r.get('avg_dollar_volume_20d'));liquidity=_clamp((math.log10(max(dollar,1))-6)/3) if dollar is not None else .5;spread=_f(r.get('spread_quality'));liquidity=.5*liquidity+.5*_norm(spread) if spread is not None else liquidity
    if dollar is not None and dollar<10_000_000:warnings.append('Liquiditeit is relatief laag')
    short=_norm(r.get('short_interest_risk'),0);return institutional*100,macro*100,_clamp(.75*liquidity+.25*(1-short))*100,warnings

def calculate_opportunity_score(components:dict[str,float],data_quality:float,thesis_broken:bool=False)->float:
    score=sum((components[k]/100)*w for k,w in WEIGHTS.items())*(.90+.10*_clamp(data_quality));return round(min(score,55) if thesis_broken else score,1)

def scenario_data(r:dict[str,Any],score:float,reversal:float,analyst_score:float)->list[dict[str,Any]]:
    target=_target_upside(r)
    if target is None:return []
    upside=max(0,target);confidence=_clamp(.40*score/100+.35*reversal+.25*analyst_score/100)
    return [{'name':'25pct_1m','return_pct':min(upside,.25),'probability':_clamp(.15+.45*confidence),'horizon_days':31},{'name':'50pct_3m','return_pct':min(upside,.50),'probability':_clamp(.12+.48*confidence),'horizon_days':93},{'name':'100pct_12m','return_pct':upside,'probability':_clamp(.10+.55*confidence),'horizon_days':365}]

def qualifying_paths(scenarios:list[dict[str,Any]])->list[str]:return [s['name'] for s in scenarios if s['return_pct']>=PATH_RULES[s['name']]['min_upside'] and s['horizon_days']<=PATH_RULES[s['name']]['max_days'] and s['probability']>=PATH_RULES[s['name']]['min_probability']]
def risk_reward(r:dict[str,Any],target:float|None)->float|None:
    price=_f(r.get('price'))
    if not price or target is None or target<=0:return None
    support=_f(r.get('distance_support_20d'));stop=price*(1+min(-.05,support if support is not None else -.05));risk=max(.01*price,price-stop);reward=max(0,target-price);return reward/risk if risk>0 else None
def trading_plan(r:dict[str,Any],target:float|None)->dict[str,Any]:
    price=_f(r.get('price')) or 0;atr=_f(r.get('atr_pct'),.06) or .06;entry_low=price*(1-min(.08,max(.02,atr*.5)));entry_high=price*(1+min(.02,max(.005,atr*.15)));add_low=price*(1-min(.12,max(.04,atr)));add_high=entry_low;invalidation=price*(1-min(.18,max(.07,atr*1.5)));tp1=price*1.25 if target is None else min(target,price*1.25) if target>price else price*1.15;tp2=price*1.50 if target is None else target if target>price else price*1.25;return {'entry_low':entry_low,'entry_high':entry_high,'add_low':add_low,'add_high':add_high,'invalidation':invalidation,'tp1':tp1,'tp2':tp2}
def _load_previous()->dict[str,dict[str,Any]]:
    path=Path('public/data/alert_history.json')
    if not path.exists():return {}
    try:
        raw=json.loads(path.read_text(encoding='utf-8'));items=raw.get('alerts',raw) if isinstance(raw,dict) else raw;return {str(x.get('ticker')).upper():x for x in items if isinstance(x,dict) and x.get('ticker')}
    except Exception:return {}
def _action(score,reversal,dilution,leverage,paths,revision,r,previous):
    reasons=[];existing=bool(r.get('is_existing_position')) or previous is not None
    if r.get('thesis_broken'):return ('EXIT' if existing else 'NONE'),['Thesis is gemarkeerd als gebroken']
    if not paths:reasons.append('Geen return-pad voldoet aan de vereiste upside, horizon en kans')
    if (_f(r.get('avg_dollar_volume_20d'),0) or 0)<5_000_000:return 'NONE',reasons+['Liquiditeit onder de scannergrens']
    if not existing:
        if score>=NEW_BUY_SCORE_PREFERRED and paths and reversal>=.55 and dilution<=.75 and leverage<=.85:return 'BUY',reasons+['Score, reversal, return-pad, leverage en dilution voldoen aan de BUY-filters']
        return 'NONE',reasons
    price=_f(r.get('price'),0) or 0;plan=trading_plan(r,_f(r.get('analyst_target_mean')))
    if score<60:return 'EXIT',reasons+['Opportunity score onder 60']
    if price>=plan['tp2']:return 'TAKE PROFIT',reasons+['TP2 bereikt']
    if price>=plan['tp1'] or (_f(r.get('rsi_14'),0) or 0)>=75:return 'PARTIAL TAKE PROFIT',reasons+['Setup is overextended of TP1 bereikt']
    if score>=85 and reversal>=.70 and revision>=.40:return 'ADD',reasons+['Sterke score, reversal en analistenrevisies']
    return 'HOLD',reasons+['Bestaande positie blijft binnen de actieband']
def evaluate_row(row:Any,previous=None)->dict[str,Any]:
    r=dict(row);technical,reversal=score_technical(r);fundamentals=score_fundamentals(r);valuation=score_valuation(r);analysts=score_analysts(r);catalysts,catalyst_desc,catalyst_days=score_catalysts(r);institutional,macro,liquidity,warnings=score_market_and_risk(r);components={'technical':technical,'fundamentals':fundamentals,'valuation':valuation,'analysts':analysts,'catalysts':catalysts,'institutional':institutional,'macro_sector':macro,'liquidity_risk':liquidity};required=[r.get('price'),r.get('rsi_14'),r.get('revenue_growth'),r.get('analyst_consensus_score')];quality=sum(v is not None and _f(v) is not None for v in required)/len(required);target=_target_upside(r);score=calculate_opportunity_score(components,quality,bool(r.get('thesis_broken')));scenarios=scenario_data(r,score,reversal,analysts);paths=qualifying_paths(scenarios);dilution=_norm(r.get('dilution_risk'),0);leverage=_clamp((_f(r.get('debt_equity'),.5) or .5));revision=_clamp(.5+.08*((_f(r.get('analyst_bullish_changes_30d'),0) or 0)-(_f(r.get('analyst_bearish_changes_30d'),0) or 0)));action,reasons=_action(score,reversal,dilution,leverage,paths,revision,r,previous);rr=risk_reward(r,_f(r.get('analyst_target_mean')));confidence=100*_clamp(.45*quality+.20*reversal+.20*analysts/100+.15*(1-dilution));price=_f(r.get('price'));prev_score=_f((previous or {}).get('score')) or _f((previous or {}).get('opportunity_score'));prev_price=_f((previous or {}).get('price'));score_delta=abs(score-prev_score) if prev_score is not None else None;price_delta=abs(price/prev_price-1) if price and prev_price else None;material=previous is None or action not in {'NONE','HOLD'} or (score_delta is not None and score_delta>=MATERIAL_SCORE_DELTA) or (price_delta is not None and price_delta>=MATERIAL_PRICE_DELTA)
    if reversal>=.55:reasons.append('Er is daadwerkelijke reversal-confirmatie')
    if target is not None and target>.25:reasons.append(f'Analistentarget impliceert {target*100:.1f}% upside')
    if catalyst_desc:reasons.append(catalyst_desc)
    return {'opportunity_score':score,'score_label':'EXCELLENT' if score>=85 else 'STRONG' if score>=75 else 'WATCH' if score>=65 else 'LOW','component_scores':{k:round(v,1) for k,v in components.items()},'action':action,'qualifies_new_buy':action=='BUY','qualifying_paths':paths,'scenarios':scenarios,'expected_return':target,'risk_reward':round(rr,2) if rr is not None else None,'confidence':round(confidence,1),'reasons':reasons[:8],'warnings':warnings,'reversal_confirmation':round(reversal,3),'catalyst_description':catalyst_desc,'catalyst_nearest_days':catalyst_days,'trading_plan':trading_plan(r,_f(r.get('analyst_target_mean'))),'data_quality':round(quality,3),'material_change':bool(material),'previous_score':prev_score,'score_delta':round(score_delta,1) if score_delta is not None else None,'price_delta':round(price_delta,4) if price_delta is not None else None,'setup_type':'high-beta mean reversion' if technical>=fundamentals and reversal>=.55 else 'quality/value pullback' if fundamentals>=technical else 'structural growth' if fundamentals>=60 else 'structural deterioration / value trap'}
def apply_opportunity_engine(frame:pd.DataFrame)->pd.DataFrame:
    if frame is None or frame.empty:return frame
    previous=_load_previous();out=frame.copy();evaluations=[evaluate_row(row.to_dict(),previous.get(str(row.get('ticker','')).upper())) for _,row in out.iterrows()]
    for key in ['opportunity_score','score_label','action','qualifies_new_buy','expected_return','risk_reward','confidence','reversal_confirmation','catalyst_description','catalyst_nearest_days','data_quality','material_change','previous_score','score_delta','price_delta','setup_type']:out[key]=[e.get(key) for e in evaluations]
    for key in ['component_scores','qualifying_paths','scenarios','reasons','warnings','trading_plan']:out[key]=[e.get(key) for e in evaluations]
    for name in WEIGHTS:out[f'opportunity_{name}_score']=[e['component_scores'][name] for e in evaluations]
    return out.sort_values(['opportunity_score','ticker'],ascending=[False,True]).reset_index(drop=True)
