from __future__ import annotations
import argparse,json,math
from datetime import datetime,timezone
from pathlib import Path
import scanner as scanner_module
from market_validation import run_market_validation
from scanner import scan
from universe import load_top_us_stocks
from opportunity_engine import ENGINE_VERSION

EXCLUDED_TICKERS={'FLNC'}

def scanner_universe(limit:int|None=None):
    frame=load_top_us_stocks(limit)
    return frame[~frame['ticker'].isin(EXCLUDED_TICKERS)].reset_index(drop=True)

def _json_safe(value):
    if value is None:return None
    if isinstance(value,float):return value if math.isfinite(value) else None
    try:
        if hasattr(value,'item'):return _json_safe(value.item())
    except Exception:pass
    if isinstance(value,dict):return {str(k):_json_safe(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [_json_safe(v) for v in value]
    return value

def write_web_output(result,universe_size:int,path:str)->None:
    rows=[_json_safe(row) for row in result.where(result.notna(),None).to_dict(orient='records')]
    top_score=_json_safe(result['opportunity_score'].max()) if not result.empty else None
    payload={'engine_version':ENGINE_VERSION,'generated_at':datetime.now(timezone.utc).isoformat(),'universe_size':int(universe_size),'alert_count':int((result['action']=='BUY').sum()) if not result.empty else 0,'top_score':top_score,'results':rows}
    output=Path(path); output.parent.mkdir(parents=True,exist_ok=True); output.write_text(json.dumps(payload,indent=2,allow_nan=False),encoding='utf-8')

def main()->None:
    parser=argparse.ArgumentParser(description='MarketIntel Opportunity Engine scanner')
    sub=parser.add_subparsers(dest='command',required=True)
    u=sub.add_parser('universe'); u.add_argument('--limit',type=int,default=1000)
    s=sub.add_parser('scan'); s.add_argument('--limit',type=int,default=1000); s.add_argument('--top',type=int,default=1000); s.add_argument('--output',default=None); s.add_argument('--web-output',default='public/data/latest_scan.json')
    v=sub.add_parser('validate-market'); v.add_argument('--output',default='market_validation.csv'); v.add_argument('--summary',default='market_validation.json')
    args=parser.parse_args()
    if args.command=='universe':print(scanner_universe(args.limit).to_string(index=False)); return
    if args.command=='scan':
        scanner_module.load_top_us_stocks=scanner_universe
        universe=scanner_universe(args.limit)
        result=scan(args.limit,args.top)
        print(result.to_string(index=False))
        if args.output:result.to_csv(args.output,index=False); print(f'\nSaved {args.output}')
        write_web_output(result,len(universe),args.web_output); print(f'Saved {args.web_output}'); return
    signals,summary=run_market_validation(); print(json.dumps(summary,indent=2)); signals.to_csv(args.output,index=False); Path(args.summary).write_text(json.dumps(summary,indent=2,allow_nan=False),encoding='utf-8'); print(f'Saved {args.output} and {args.summary}')

if __name__=='__main__':main()
