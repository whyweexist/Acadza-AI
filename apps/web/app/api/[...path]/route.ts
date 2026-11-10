import {NextRequest, NextResponse} from 'next/server';
import {readFile} from 'node:fs/promises';
import path from 'node:path';

type Ctx={params:Promise<{path:string[]}>};
const endpoint=process.env.API_BASE_URL||'http://127.0.0.1:8000';

async function fallback(segments:string[]) {
  const root=path.join(process.cwd(),'public');
  if(segments[0]==='cases'&&segments.length===1) {
    return JSON.parse(await readFile(path.join(root,'demo-index.json'),'utf8'));
  }
  if(segments[0]==='cases'&&segments.length===2) {
    const map=JSON.parse(await readFile(path.join(root,'demo-cases.json'),'utf8')) as Record<string,unknown>;
    return map[segments[1]]??null;
  }
  if(segments[0]==='metrics') {
    const index=JSON.parse(await readFile(path.join(root,'demo-index.json'),'utf8'));
    return {cases:index.total,...index.counts,note:'Precomputed static demonstration'};
  }
  if(segments[0]==='audit')return [];
  if(segments[0]==='health')return {ok:true,storage:'static demo',writes_require_auth:true};
  return null;
}

export async function GET(req:NextRequest,ctx:Ctx) {
  const {path:parts}=await ctx.params;
  const suffix=parts.map(encodeURIComponent).join('/');
  const controller=new AbortController();
  const t=setTimeout(()=>controller.abort(),4000);
  try {
    const remote=await fetch(`${endpoint}/api/${suffix}${req.nextUrl.search}`,{cache:'no-store',signal:controller.signal});
    const text=await remote.text();
    return new NextResponse(text,{status:remote.status,headers:{'content-type':'application/json','x-data-mode':'live'}});
  }catch {
    const obj=await fallback(parts).catch(()=>null);
    if(!obj)return NextResponse.json({error:'No live backend and no static snapshot for this path'}, {status:503});
    // Offline snapshots are intentionally read-only. No simulated audit writes.
    return NextResponse.json(obj,{headers:{'x-data-mode':'demo'}});
  }finally{clearTimeout(t);}
}

export async function POST(req:NextRequest,ctx:Ctx) {
  const {path:parts}=await ctx.params;
  if(parts.length!==3 || parts[0]!=='cases' || parts[2]!=='actions')return NextResponse.json({error:'Invalid endpoint'},{status:404});
  if(!process.env.REVIEW_TOKEN)return NextResponse.json({detail:'Demo is read-only. Set REVIEW_TOKEN and start the SQLite API to review cases.'},{status:503});
  try {
    const data=await req.json();
    const remote=await fetch(`${endpoint}/api/cases/${encodeURIComponent(parts[1])}/actions`,{
      method:'POST',headers:{'content-type':'application/json','x-review-token':process.env.REVIEW_TOKEN},
      body:JSON.stringify(data),cache:'no-store',signal:AbortSignal.timeout(12000)
    });
    return new NextResponse(await remote.text(),{status:remote.status,headers:{'content-type':'application/json'}});
  }catch {
    return NextResponse.json({detail:'SQLite API unavailable. No review action was saved.'},{status:503});
  }
}
