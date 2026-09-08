import {NextResponse} from 'next/server';

export const dynamic='force-dynamic';
export const revalidate=0;

const SOURCE='https://raw.githubusercontent.com/hugopijnenborg/stock-scanner/main/public/data/latest_scan.json';
const COMMITS='https://api.github.com/repos/hugopijnenborg/stock-scanner/commits?path=public/data/latest_scan.json&per_page=1';

export async function GET(){
  try{
    const [dataResponse,commitResponse]=await Promise.all([
      fetch(`${SOURCE}?t=${Date.now()}`,{cache:'no-store',headers:{Accept:'application/json'}}),
      fetch(`${COMMITS}&t=${Date.now()}`,{cache:'no-store',headers:{Accept:'application/vnd.github+json'}})
    ]);
    if(!dataResponse.ok)return NextResponse.json({error:`GitHub scan data returned HTTP ${dataResponse.status}`},{status:502});
    const text=await dataResponse.text();
    const data=JSON.parse(text.replace(/\bNaN\b/g,'null').replace(/\b-Infinity\b/g,'null').replace(/\bInfinity\b/g,'null'));
    const valid=Array.isArray(data.results)&&data.results.length>0&&data.results.every(r=>r&&r.opportunity_score!=null&&r.action!=null&&r.component_scores!=null);
    if(!valid)return NextResponse.json({error:'De gepubliceerde scan bevat nog geen geldige Opportunity Engine resultaten. De scanner moet eerst één volledige nieuwe scan publiceren.'},{status:503});
    data.engine_version=Number(data.engine_version)||3;
    const originalGeneratedAt=data.generated_at;
    if(commitResponse.ok){
      const commits=await commitResponse.json();
      const latestCommitDate=commits?.[0]?.commit?.committer?.date||commits?.[0]?.commit?.author?.date;
      const latestCommitSha=commits?.[0]?.sha;
      if(latestCommitDate)data.generated_at=latestCommitDate;
      if(originalGeneratedAt)data.scan_generated_at=originalGeneratedAt;
      if(latestCommitSha)data.scan_version=latestCommitSha;
    }
    return NextResponse.json(data,{headers:{'Cache-Control':'no-store, max-age=0'}});
  }catch(error){
    return NextResponse.json({error:`Kan scan data niet laden: ${error instanceof Error?error.message:'onbekende fout'}`},{status:500});
  }
}
