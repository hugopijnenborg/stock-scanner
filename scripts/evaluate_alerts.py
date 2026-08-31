from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime, timezone
import pandas as pd
import yfinance as yf

SCAN=Path('public/data/latest_scan.json')
HISTORY=Path('public/data/alert_history.json')
HORIZONS={1:'1D',5:'5D',10:'10D',20:'20D'}
TARGETS=[5,10,20,30]

def load(path):
    if not path.exists(): return {}
    try: return json.loads(path.read_text(encoding='utf-8'))
    except Exception: return {}

def evaluate(a):
    try:
        start=pd.Timestamp(a['alert_date'])
        hist=yf.download(a['ticker'],start=start.strftime('%Y-%m-%d'),end=(pd.Timestamp.now()+pd.Timedelta(days=2)).strftime('%Y-%m-%d'),auto_adjust=False,progress=False)
        if hist.empty: return
        close,high,low=hist['Close'],hist['High'],hist['Low']
        if hasattr(close,'columns'): close,high,low=close.iloc[:,0],high.iloc[:,0],low.iloc[:,0]
        close=close.dropna(); high=high.reindex(close.index).dropna(); low=low.reindex(close.index).dropna()
        if close.empty: return
        entry=float(a['alert_price'] or close.iloc[0])
        a.setdefault('returns',{})
        for n,label in HORIZONS.items():
            if len(close)>n: a['returns'][label]=round((float(close.iloc[n])/entry-1)*100,2)
        if not high.empty:
            a['max_gain_pct']=round((float(high.max())/entry-1)*100,2)
            a['max_drawdown_pct']=round((float(low.min())/entry-1)*100,2)
            a['targets_hit']=[f'+{t}%' for t in TARGETS if float(high.max())>=entry*(1+t/100)]
        if '20D' in a['returns']: a['status']='WIN' if a['returns']['20D']>0 else 'LOSS'
        elif '10D' in a['returns']: a['status']='WIN' if a['returns']['10D']>0 else 'LOSS'
        elif '5D' in a['returns']: a['status']='WIN' if a['returns']['5D']>0 else 'LOSS'
        else: a['status']='PENDING'
    except Exception as exc:
        a['evaluation_error']=str(exc)

def main():
    scan=load(SCAN); data=load(HISTORY); alerts=data.get('alerts',[])
    existing={(x.get('ticker'),x.get('alert_date')) for x in alerts}
    today=datetime.now(timezone.utc).date().isoformat()
    for r in scan.get('results',[]):
        if r.get('signal')!='ALERT': continue
        key=(r.get('ticker'),today)
        if key not in existing:
            alerts.append({'ticker':r.get('ticker'),'company_name':r.get('company_name'),'alert_date':today,'alert_price':r.get('price'),'score':r.get('overall_score'),'trader_score':r.get('trader_similarity_score'),'technical_score':r.get('technical_score'),'fundamental_score':r.get('fundamental_score'),'returns':{},'max_gain_pct':None,'max_drawdown_pct':None,'targets_hit':[],'status':'PENDING'})
    for a in alerts: evaluate(a)
    HISTORY.parent.mkdir(parents=True,exist_ok=True)
    HISTORY.write_text(json.dumps({'updated_at':datetime.now(timezone.utc).isoformat(),'alerts':sorted(alerts,key=lambda x:x.get('alert_date',''),reverse=True)},indent=2,allow_nan=False),encoding='utf-8')

if __name__=='__main__': main()
