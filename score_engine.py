from __future__ import annotations
import math
from typing import Any
import pandas as pd
TRADER_WEIGHT=.35; TECHNICAL_WEIGHT=.30; FUNDAMENTAL_WEIGHT=.20; ANALYST_WEIGHT=.15; ALERT_THRESHOLD=80.; WATCH_THRESHOLD=65.
def _num(value:Any):
    try:
        if value is None or (isinstance(value,str) and not value.strip()):return None
        value=float(value); return value if math.isfinite(value) else None
    except(TypeError,ValueError):return None
def _weighted(parts):
    usable=[(float(value),weight) for value,weight in parts if _num(value) is not None]
    if not usable:return None
    weight_sum=sum(weight for _,weight in usable)
    return sum(value*weight for value,weight in usable)/weight_sum if weight_sum>0 else None
def calculate_score(row:pd.Series|dict[str,Any]):
    trader=_num(row.get('trader_similarity_score')); technical=_num(row.get('technical_score')); fundamental=_num(row.get('fundamental_score')); analyst=_num(row.get('analyst_score'))
    overall=_weighted([(trader,TRADER_WEIGHT),(technical,TECHNICAL_WEIGHT),(fundamental,FUNDAMENTAL_WEIGHT),(analyst,ANALYST_WEIGHT)])
    signal='DATA_INCOMPLETE' if overall is None else 'ALERT' if overall>=ALERT_THRESHOLD else 'WATCH' if overall>=WATCH_THRESHOLD else 'NO_SIGNAL'
    return {'overall_score':round(overall,1) if overall is not None else None,'trader_score':round(trader,1) if trader is not None else None,'technical_score':round(technical,1) if technical is not None else None,'fundamental_score':round(fundamental,1) if fundamental is not None else None,'analyst_score':round(analyst,1) if analyst is not None else None,'signal':signal}
