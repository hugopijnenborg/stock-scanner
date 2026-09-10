from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd
LEARNED_MODEL_PATH=Path('learned_model.json')
def clamp(x,lo=0.0,hi=1.0):return float(np.clip(x,lo,hi)) if pd.notna(x) else 0.0
def low_is_good(value,start,extreme):
    if pd.isna(value):return 0.0
    return clamp((start-value)/(start-extreme))
def high_is_good(value,start,extreme):
    if pd.isna(value):return 0.0
    return clamp((value-start)/(extreme-start))
def _neutral_centered_low(value,start,extreme):
    if pd.isna(value):return .5
    span=abs(float(start)-float(extreme))
    if span==0:return .5
    value=float(value)
    if value<=extreme:return 1.0
    if value>=start+span:return 0.0
    if value<start:return .5+.5*(start-value)/span
    return .5-.5*(value-start)/span
def _neutral_centered_high(value,start,extreme):
    if pd.isna(value):return .5
    span=abs(float(extreme)-float(start))
    if span==0:return .5
    value=float(value)
    if value>=extreme:return 1.0
    if value<=start-span:return 0.0
    if value>start:return .5+.5*(value-start)/span
    return .5-.5*(start-value)/span
def support_component(r):
    values=[float(x) for x in [r.get('distance_support_20d'),r.get('distance_support_60d'),r.get('distance_support_120d')] if pd.notna(x)]
    return float(np.mean([clamp((.10-x)/.10) for x in values])) if values else 0.0
def _technical_support_component(r):
    values=[float(x) for x in [r.get('distance_support_20d'),r.get('distance_support_60d'),r.get('distance_support_120d')] if pd.notna(x)]
    return float(np.mean([_neutral_centered_low(x,.10,0.0) for x in values])) if values else .5
def rebound_components(r):
    return {'drawdown_5d':low_is_good(r.get('return_5d',np.nan),-.05,-.30),'drawdown_20d':low_is_good(r.get('return_20d',np.nan),-.05,-.40),'rsi_14':low_is_good(r.get('rsi_14',np.nan),45,20),'z_score':low_is_good(r.get('z_score',np.nan),-.5,-3.0),'volume_ratio':high_is_good(r.get('volume_ratio',np.nan),1.0,4.0),'bollinger_pct':low_is_good(r.get('bollinger_pct',np.nan),.35,-.05),'distance_sma20':low_is_good(r.get('distance_sma20',np.nan),-.03,-.25),'distance_sma50':low_is_good(r.get('distance_sma50',np.nan),-.03,-.30),'relative_strength_20d':low_is_good(r.get('relative_strength_20d',np.nan),-.02,-.25),'support':support_component(r),'intraday_reversal':high_is_good(r.get('close_location',np.nan),.50,1.00),'market_regime':float(r.get('market_regime_score',.5)) if pd.notna(r.get('market_regime_score',np.nan)) else .5}
def quality_components(r):
    return {'distance_52w_high':low_is_good(r.get('distance_52w_high',np.nan),-.05,-.50),'distance_sma200':low_is_good(r.get('distance_sma200',np.nan),-.02,-.30),'drawdown_20d':low_is_good(r.get('return_20d',np.nan),-.05,-.40),'relative_strength_20d':low_is_good(r.get('relative_strength_20d',np.nan),-.10,-.25),'rsi_14':low_is_good(r.get('rsi_14',np.nan),50,25),'z_score':low_is_good(r.get('z_score',np.nan),-.5,-3.0),'volume_ratio':high_is_good(r.get('volume_ratio',np.nan),1.0,3.0),'support':support_component(r),'market_regime':float(r.get('market_regime_score',.5)) if pd.notna(r.get('market_regime_score',np.nan)) else .5,'fundamental_placeholder':0.0}
def cyclical_components(r):
    return {'drawdown_5d':low_is_good(r.get('return_5d',np.nan),-.05,-.35),'drawdown_20d':low_is_good(r.get('return_20d',np.nan),-.05,-.50),'rsi_14':low_is_good(r.get('rsi_14',np.nan),45,20),'atr_pct':high_is_good(r.get('atr_pct',np.nan),.03,.15),'volume_ratio':high_is_good(r.get('volume_ratio',np.nan),1.0,4.0),'z_score':low_is_good(r.get('z_score',np.nan),-.5,-3.0),'relative_strength_20d':low_is_good(r.get('relative_strength_20d',np.nan),-.05,-.30),'bollinger_pct':low_is_good(r.get('bollinger_pct',np.nan),.35,-.05),'support':support_component(r),'intraday_reversal':high_is_good(r.get('close_location',np.nan),.50,1.00),'market_regime':float(r.get('market_regime_score',.5)) if pd.notna(r.get('market_regime_score',np.nan)) else .5}
def weighted_score(components,weights):
    usable=[(k,w) for k,w in weights.items() if k in components and pd.notna(components[k])]; total=sum(w for _,w in usable)
    return 100.0*sum(components[k]*w for k,w in usable)/total if total>0 else 0.0
def technical_opportunity_score(r):
    c={'drawdown_5d':_neutral_centered_low(r.get('return_5d',np.nan),-.04,-.30),'rsi_14':_neutral_centered_low(r.get('rsi_14',np.nan),43,20),'drawdown_20d':_neutral_centered_low(r.get('return_20d',np.nan),-.05,-.40),'distance_sma20':_neutral_centered_low(r.get('distance_sma20',np.nan),-.03,-.25),'distance_sma50':_neutral_centered_low(r.get('distance_sma50',np.nan),-.03,-.30),'z_score':_neutral_centered_low(r.get('z_score',np.nan),-.5,-3.0),'distance_52w_high':_neutral_centered_low(r.get('distance_52w_high',np.nan),-.05,-.45),'volume_ratio':_neutral_centered_high(r.get('volume_ratio',np.nan),1.0,4.0),'support':_technical_support_component(r),'intraday_reversal':_neutral_centered_high(r.get('close_location',np.nan),.50,1.00),'sector_relative_strength_20d':_neutral_centered_high(r.get('sector_relative_strength_20d',np.nan),0,.20),'market_regime':float(r.get('market_regime_score',.5)) if pd.notna(r.get('market_regime_score',np.nan)) else .5}
    w={'drawdown_5d':.18,'rsi_14':.18,'drawdown_20d':.12,'distance_sma20':.10,'distance_sma50':.08,'z_score':.08,'distance_52w_high':.10,'volume_ratio':.06,'support':.05,'intraday_reversal':.02,'sector_relative_strength_20d':.01,'market_regime':.02}
    return {'technical_opportunity_score':weighted_score(c,w)}
def dip_score(r):
    c={'drawdown_5d':low_is_good(r.get('return_5d',np.nan),-.04,-.25),'drawdown_20d':low_is_good(r.get('return_20d',np.nan),-.05,-.35),'rsi_14':low_is_good(r.get('rsi_14',np.nan),40,22),'z_score':low_is_good(r.get('z_score',np.nan),-.5,-2.5),'distance_sma20':low_is_good(r.get('distance_sma20',np.nan),-.02,-.20),'distance_sma50':low_is_good(r.get('distance_sma50',np.nan),-.02,-.25),'distance_52w_high':low_is_good(r.get('distance_52w_high',np.nan),-.05,-.40),'volume':high_is_good(r.get('volume_ratio',np.nan),1.0,3.0),'support':_technical_support_component(r)}
    return weighted_score(c,{'drawdown_5d':.18,'drawdown_20d':.15,'rsi_14':.18,'z_score':.12,'distance_sma20':.08,'distance_sma50':.08,'distance_52w_high':.10,'volume':.06,'support':.05})
def reversal_trigger(r):
    signals=[]
    if pd.notna(r.get('close_location')):signals.append(clamp((r['close_location']-.45)/.55))
    if pd.notna(r.get('macd_histogram_change')):
        hist=float(r.get('macd_histogram',0) or 0); change=float(r.get('macd_histogram_change',0) or 0); signals.append(clamp((change+abs(hist))/(abs(hist)+1e-9)))
    if pd.notna(r.get('return_1d')):signals.append(clamp((r['return_1d']+.15)/.20))
    return float(np.mean(signals)) if signals else 0.0
def _learned_score(row):
    if not LEARNED_MODEL_PATH.exists():return None
    try:
        payload=json.loads(LEARNED_MODEL_PATH.read_text(encoding='utf-8')); features=payload['features']; x=pd.to_numeric(row.reindex(features),errors='coerce').replace([np.inf,-np.inf],np.nan).fillna(0).to_numpy(float); mean=np.asarray(payload['mean'],float); scale=np.asarray(payload['scale'],float); coef=np.asarray(payload['coef'],float); z=(x-mean)/np.where(scale==0,1,scale); logit=float(np.dot(coef,z)+payload['intercept']); return float((1/(1+np.exp(-np.clip(logit,-30,30))))*100)
    except Exception:return None
def score_row(row,rebound_weights,quality_weights,cyclical_weights):
    rb=rebound_components(row);qu=quality_components(row);cy=cyclical_components(row);scores={'rebound_score':weighted_score(rb,rebound_weights),'quality_score':weighted_score(qu,quality_weights),'cyclical_score':weighted_score(cy,cyclical_weights)};scores.update(technical_opportunity_score(row));scores['dip_score']=dip_score(row);scores['reversal_trigger']=reversal_trigger(row)*100;setup_key=max(['rebound_score','quality_score','cyclical_score'],key=lambda k:scores[k]);learned=_learned_score(row);scores['trader_similarity_score']=learned if learned is not None else scores['technical_opportunity_score'];scores['overall_score']=.50*scores['trader_similarity_score']+.50*scores['technical_opportunity_score'] if learned is not None else scores['technical_opportunity_score'];scores['watch_candidate']=bool(scores['overall_score']>=65 and scores['trader_similarity_score']>=65 and scores['technical_opportunity_score']>=60 and scores['dip_score']>=55);scores['setup_type']='watch' if scores['watch_candidate'] else setup_key.replace('_score','');return scores
