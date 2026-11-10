'use client';
import {useCallback,useEffect,useState} from 'react';
import {ArrowRight,CheckCircle2,Cloud,Eye,EyeOff,Info,KeyRound,LoaderCircle,PlayCircle,RefreshCw,RotateCcw,ShieldAlert,ShieldCheck,Terminal,TriangleAlert} from 'lucide-react';

type Provider='openai'|'gemini'|'openrouter';
type PublicConfig={provider:Provider;configured:boolean;source:'session'|'environment';cheap_model:string;strong_model:string};
type Job={id:string;question_id:string;provider:Provider;status:'queued'|'running'|'completed'|'failed'|'interrupted';message:string};
const MODELS:Record<Provider,{cheap:string;strong:string;homepage:string;detail:string}>= {
 openai:{cheap:'gpt-4.1-mini',strong:'gpt-4.1',homepage:'https://platform.openai.com/api-keys',detail:'Direct OpenAI API access'},
 gemini:{cheap:'gemini-2.5-flash',strong:'gemini-2.5-pro',homepage:'https://aistudio.google.com/apikey',detail:'Google AI Studio API key'},
 openrouter:{cheap:'google/gemini-2.5-flash',strong:'google/gemini-2.5-pro',homepage:'https://openrouter.ai/settings/keys',detail:'Choose models from OpenRouter'},
};
const PROVIDER_NAMES:Record<Provider,string>={openai:'OpenAI',gemini:'Google Gemini',openrouter:'OpenRouter'};

export function ProviderSettings({serverMode,selectedCase,onCaseRechecked}:{serverMode:'live'|'demo';selectedCase:string;onCaseRechecked:()=>void}){
 const [adminToken,setAdminToken]=useState('');
 const [provider,setProvider]=useState<Provider>('gemini');
 const [key,setKey]=useState('');
 const [showKey,setShowKey]=useState(false);
 const [cheap,setCheap]=useState(MODELS.gemini.cheap);
 const [strong,setStrong]=useState(MODELS.gemini.strong);
 const [saved,setSaved]=useState<PublicConfig|null>(null);
 const [busy,setBusy]=useState('');
 const [notice,setNotice]=useState<{ok:boolean;text:string}|null>(null);
 const [job,setJob]=useState<Job|null>(null);
 const [jobCase,setJobCase]=useState(selectedCase);
 const live=serverMode==='live';
 const readResponse=async (response:Response)=>{
   const value=await response.json().catch(()=>({detail:'Unexpected response'}));
   if(!response.ok)throw new Error(typeof value.detail==='string'?value.detail:`Request failed (HTTP ${response.status})`);
   return value;
 };
 const request=useCallback((url:string,method:'GET'|'POST'|'PUT'|'DELETE'='GET',body?:object)=>fetch(url,{
   method,cache:'no-store',headers:{'x-review-token':adminToken,...(body?{'content-type':'application/json'}:{})},
   body:body?JSON.stringify(body):undefined,
 }),[adminToken]);
 const sync=useCallback(async()=>{
  if(!adminToken.trim())throw Error('Enter the faculty admin token first.');
  const config=await readResponse(await request('/api/llm/config')) as PublicConfig;
  setSaved(config);setProvider(config.provider);setCheap(config.cheap_model);setStrong(config.strong_model);
  return config;
 },[adminToken,request]);
 const perform=async(label:string,run:()=>Promise<string>)=>{
  setBusy(label);setNotice(null);
  try{setNotice({ok:true,text:await run()})}catch(error){setNotice({ok:false,text:error instanceof Error?error.message:'Provider action failed'})}
  finally{setBusy('')}
 };
 const choose=(next:Provider)=>{
  setProvider(next);setKey('');setShowKey(false);
  if(saved?.provider===next){setCheap(saved.cheap_model);setStrong(saved.strong_model)}
  else{setCheap(MODELS[next].cheap);setStrong(MODELS[next].strong)}
 };
 const save=()=>perform('save',async()=>{
   if(!cheap.trim()||!strong.trim())throw Error('Enter both model identifiers.');
   if(!adminToken.trim())throw Error('Enter the faculty admin token first.');
   const config=await readResponse(await request('/api/llm/config','PUT',{
      provider,api_key:key.trim()||null,cheap_model:cheap.trim(),strong_model:strong.trim()
   })) as PublicConfig;
   setSaved(config);setKey('');setShowKey(false);
   return `${PROVIDER_NAMES[config.provider]} configured for this API process. The key is never returned or saved to SQLite.`;
 });
 const probe=()=>perform('test',async()=>{
  const result=await readResponse(await request('/api/llm/test','POST')) as {ok:boolean;message:string};
  if(!result.ok)throw Error(result.message);
  return result.message;
 });
 const reset=()=>perform('reset',async()=>{
   const config=await readResponse(await request('/api/llm/config','DELETE')) as PublicConfig;
   setSaved(config);setProvider(config.provider);setCheap(config.cheap_model);setStrong(config.strong_model);setKey('');
   return 'Temporary override cleared. Environment configuration is active.';
 });
 const start=()=>perform('run',async()=>{
   if(!jobCase.match(/^[a-fA-F0-9]{24}$/))throw Error('Select a valid question case from the queue.');
   const started=await readResponse(await request('/api/llm/jobs','POST',{question_id:jobCase})) as Job;
   setJob(started);
   return 'Live verification queued. Independent solvers and the safety gate will evaluate this question.';
 });
 useEffect(()=>{if(!job||!['queued','running'].includes(job.status)||!adminToken)return;
  let stopped=false;
  const tick=async()=>{
   try{
    const response=await request(`/api/llm/jobs/${job.id}`);
    if(!response.ok)return;
    const current=await response.json() as Job;
    if(stopped)return;
    setJob(current);
    if(current.status==='completed')onCaseRechecked();
   }catch{/* Retain displayed job state; network may be transiently unavailable. */}
  };
  const timer=window.setInterval(()=>void tick(),2500);
  return()=>{stopped=true;window.clearInterval(timer)};
 },[job?.id,job?.status,adminToken,request,onCaseRechecked]);

 return <div className="standalone provider-page">
  <div className="eyebrow">AI ORCHESTRATION</div><h1>AI providers</h1>
  <p>Connect a model provider and run genuine verification instead of relying on the precomputed demo assessments.</p>
  {!live&&<div className="provider-alert"><TriangleAlert size={19}/><div><strong>SQLite API not connected</strong><p>Start FastAPI and configure <code>API_BASE_URL</code>. Provider keys cannot be saved in offline demo mode.</p></div></div>}
  <div className="provider-intro-grid">
   <div className="provider-feature"><ShieldCheck size={21}/><div><strong>Server-side credentials</strong><span>Keys are never sent back to the browser or written to SQLite.</span></div></div>
   <div className="provider-feature"><RefreshCw size={20}/><div><strong>Switch without restarting</strong><span>Admin overrides stay in API memory until restart or reset.</span></div></div>
   <div className="provider-feature"><CheckCircle2 size={21}/><div><strong>Same safety rules</strong><span>All providers use independent solvers and the deterministic safety gate.</span></div></div>
  </div>
  <div className="provider-settings-grid">
   <section className="provider-panel">
    <div className="provider-panel-head"><div><div className="eyebrow">STEP 01</div><h2>Authorize configuration</h2></div><KeyRound size={21}/></div>
    <label className="provider-label" htmlFor="provider-admin-token">Faculty admin token</label>
    <div className="provider-input-wrap"><input id="provider-admin-token" type="password" autoComplete="off" spellCheck={false} placeholder="ADMIN_REVIEW_TOKEN from your .env" value={adminToken} onChange={e=>{setAdminToken(e.target.value);setSaved(null)}}/></div>
    <p className="provider-helper">Required for key changes, connection tests and live checks. Kept only in this page&apos;s memory; not stored in localStorage or cookies.</p>
    <button className="provider-secondary" disabled={!live||!!busy||!adminToken.trim()} onClick={()=>void perform('load',async()=>{const config=await sync();return `${PROVIDER_NAMES[config.provider]} ${config.configured?'has a key configured':'has no API key configured'}.`})}>{busy==='load'?<LoaderCircle className="spin" size={16}/>:<RefreshCw size={16}/>} Load current settings</button>
    {saved&&<div className="provider-status"><span className={`provider-status-dot ${saved.configured?'is-ready':''}`}/><div><strong>{PROVIDER_NAMES[saved.provider]} · {saved.configured?'Key configured':'Key missing'}</strong><span>{saved.source==='session'?'Temporary admin session':'Server environment'} · {saved.cheap_model} / {saved.strong_model}</span></div></div>}
   </section>
   <section className="provider-panel">
    <div className="provider-panel-head"><div><div className="eyebrow">STEP 02</div><h2>Choose your AI provider</h2></div><Cloud size={22}/></div>
    <div className="provider-choice-list" role="radiogroup" aria-label="Choose LLM provider">
     {(['gemini','openrouter','openai'] as const).map(option=><button type="button" role="radio" aria-checked={provider===option} className={`provider-choice ${provider===option?'provider-choice-active':''}`} key={option} onClick={()=>choose(option)}>
      <span className="provider-choice-avatar">{option==='gemini'?'G':option==='openrouter'?'R':'O'}</span>
      <span className="provider-choice-copy"><strong>{PROVIDER_NAMES[option]}</strong><span>{MODELS[option].detail}</span></span>
      <span className="provider-radio">{provider===option&&<span/>}</span>
     </button>)}
    </div>
   </section>
  </div>
  <section className="provider-panel provider-credentials">
   <div className="provider-panel-head"><div><div className="eyebrow">STEP 03</div><h2>API key and model routing</h2></div><KeyRound size={21}/></div>
   <div className="provider-fields-grid">
    <div className="provider-field"><label className="provider-label" htmlFor="provider-secret">{PROVIDER_NAMES[provider]} API key</label><div className="provider-input-wrap"><input id="provider-secret" spellCheck={false} autoComplete="off" type={showKey?'text':'password'} value={key} onChange={e=>setKey(e.target.value)} placeholder="Paste new key (leave blank to reuse existing key)"/><button type="button" aria-label={showKey?'Hide API key':'Show API key'} onClick={()=>setShowKey(x=>!x)}>{showKey?<EyeOff size={17}/>:<Eye size={17}/>}</button></div><a className="provider-link" href={MODELS[provider].homepage} target="_blank" rel="noreferrer">Get a {PROVIDER_NAMES[provider]} API key <ArrowRight size={14}/></a></div>
    <div className="provider-field"><label className="provider-label" htmlFor="provider-cheap">Fast / low-cost model</label><div className="provider-input-wrap"><input id="provider-cheap" autoComplete="off" spellCheck={false} value={cheap} onChange={e=>setCheap(e.target.value)}/></div><p className="provider-helper">Claim extraction, lint, metadata and student replies</p></div>
    <div className="provider-field"><label className="provider-label" htmlFor="provider-strong">Reasoning / verification model</label><div className="provider-input-wrap"><input id="provider-strong" autoComplete="off" spellCheck={false} value={strong} onChange={e=>setStrong(e.target.value)}/></div><p className="provider-helper">Independent solvers, solution audit and adjudication</p></div>
   </div>
   <div className="provider-action-row"><button className="provider-primary" disabled={!live||!!busy||!adminToken} onClick={()=>void save()}>{busy==='save'?<LoaderCircle size={16} className="spin"/>:<CheckCircle2 size={16}/>} Save provider</button><button className="provider-secondary" disabled={!live||!!busy||!adminToken||!saved?.configured||saved?.provider!==provider} onClick={()=>void probe()}>{busy==='test'?<LoaderCircle size={16} className="spin"/>:<Cloud size={16}/>} Test connection</button><button className="provider-link-button" disabled={!live||!!busy||!adminToken} onClick={()=>void reset()}><RotateCcw size={15}/> Use .env settings</button></div>
   <p className="provider-helper"><Info size={14}/> Connection test checks the API credential without generating tokens. Actual model access, costs and JSON-mode compatibility depend on your chosen model.</p>
   {notice&&<div role="status" className={`provider-alert ${notice.ok?'provider-alert-good':''}`}>{notice.ok?<CheckCircle2 size={18}/>:<TriangleAlert size={18}/>}<span>{notice.text}</span></div>}
  </section>
  <section className="provider-panel provider-run-panel">
   <div className="provider-panel-head"><div><div className="eyebrow">STEP 04</div><h2>Verify a real question</h2></div><PlayCircle size={22}/></div>
   <p>Run live, report-blind subject verification for one selected question. The result replaces its precomputed assessment in the SQLite review queue only; the original question bank remains untouched.</p>
   <div className="provider-run-form"><div className="provider-field"><label className="provider-label" htmlFor="provider-qid">Question _id</label><input id="provider-qid" value={jobCase} spellCheck={false} onChange={e=>setJobCase(e.target.value)} placeholder="Select a question in Review queue" maxLength={24}/></div><button className="provider-primary" disabled={!live||!!busy||!adminToken||!saved?.configured||saved?.provider!==provider||Boolean(job&&['queued','running'].includes(job.status))} onClick={()=>void start()}>{busy==='run'?<LoaderCircle size={16} className="spin"/>:<PlayCircle size={17}/>} Run LLM checks</button></div>
   {job&&<div className={`provider-job ${job.status==='completed'?'provider-job-done':''}`}><div className="provider-job-top"><span className="provider-job-icon">{['queued','running'].includes(job.status)?<LoaderCircle className="spin" size={20}/>:job.status==='completed'?<CheckCircle2 size={20}/>:<ShieldAlert size={20}/>}</span><div><strong>{job.status==='completed'?'LLM checks completed':job.status==='failed'?'Verification failed safely':job.status==='interrupted'?'Verification interrupted':'Verification in progress'}</strong><span>{job.message}</span></div></div><code>Job {job.id.slice(0,8)} · {PROVIDER_NAMES[job.provider]}</code>{job.status==='completed'&&<span className="provider-job-note">Return to the review queue and inspect the new evidence and verified solver outputs.</span>}</div>}
   <p className="provider-helper"><ShieldCheck size={14}/> In-process demo jobs may be interrupted by a backend restart. Failures are escalated to faculty, never silently marked fixed. For all 44 reports, run the CLI using environment variables.</p>
  </section>
  <div className="provider-footnote"><Terminal size={17}/><div><strong>Persistent provider configuration</strong><p>For Docker and production-style deployment set <code>LLM_PROVIDER</code> and the matching <code>GEMINI_API_KEY</code>, <code>OPENROUTER_API_KEY</code>, or <code>OPENAI_API_KEY</code> in server environment. The admin UI never writes secrets into SQLite, files, or browser storage.</p></div></div>
 </div>;
}
