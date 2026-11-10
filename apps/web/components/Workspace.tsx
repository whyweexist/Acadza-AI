'use client';
import {useCallback,useEffect,useMemo,useRef,useState} from 'react';
import {Activity,ArrowDown,ArrowRight,ArrowUpRight,Bell,BookOpen,Check,CheckCheck,CheckCircle2,ChevronDown,ChevronLeft,ChevronRight,Clock3,Code2,Command,Copy,FileDiff,Filter,GraduationCap,History,Info,Keyboard,LayoutDashboard,LoaderCircle,MessageSquare,MessagesSquare,Moon,Settings2,MoreHorizontal,PanelLeftClose,PanelLeftOpen,RefreshCw,Search,Shield,ShieldAlert,SlidersHorizontal,Sun,ThumbsDown,ThumbsUp,TriangleAlert,UserRound,WandSparkles,X} from 'lucide-react';
import {MathContent} from './MathContent';
import {CaseCard} from './queue/CaseCard';
import {QuestionTab,DiffTab,ReportsTab,AuditTab} from './cases/CaseTabs';
import {EvidencePanel} from './cases/EvidencePanel';
import {ReplyPreview} from './cases/ReplyPreview';
import {ReviewDialog} from './review/ReviewDialog';
import {ProviderSettings} from './settings/ProviderSettings';
import {human,shortId,relative,formatDate,priorityLabel,previewPatch,diffSegments,fieldValue} from '@/lib/utils';
import type {CaseSummary,CaseDetail,QueueResponse,Edit,Tab,ActionType,TriageResult} from '@/lib/types';

const initialQueue:QueueResponse={items:[],total:0,counts:{all:0,needs_review:0,auto_eligible:0,resolved:0}};
type View = 'queue'|'audit'|'insights'|'providers';
function Label({children,kind='muted'}:{children:React.ReactNode;kind?:string}){return <span className={`tag tag-${kind}`}>{children}</span>}

export default function Workspace(){
 const [queue,setQueue]=useState<QueueResponse>(initialQueue);
 const [selected,setSelected]=useState('');
 const [detail,setDetail]=useState<CaseDetail|null>(null);
 const [isLoading,setIsLoading]=useState(true);
 const [detailLoading,setDetailLoading]=useState(false);
 const [detailNonce,setDetailNonce]=useState(0);
 const [serverMode,setServerMode]=useState<'live'|'demo'>('demo');
 const [error,setError]=useState('');
 const [toast,setToast]=useState('');
 const [search,setSearch]=useState('');
 const [filter,setFilter]=useState('all');
 const [subject,setSubject]=useState('all');
 const [sort,setSort]=useState('priority');
 const [view,setView]=useState<View>('queue');
 const [tab,setTab]=useState<Tab>('question');
 const [reportIndex,setReportIndex]=useState(0);
 const [showSolution,setShowSolution]=useState(false);
 const [expandedEvidence,setExpandedEvidence]=useState(false);
 const [compact,setCompact]=useState(false);
 const [dark,setDark]=useState(false);
 const [shortcutHelp,setShortcutHelp]=useState(false);
 const [modal,setModal]=useState<ActionType|null>(null);
 const [reason,setReason]=useState('');
 const [editing,setEditing]=useState<Edit>({field:'question',find:'',replace:''});
 const [actor,setActor]=useState('Faculty reviewer');
 const [submitting,setSubmitting]=useState(false);
 const [allAudit,setAllAudit]=useState<{id:string;question_id:string;actor:string;action:string;note:string;created_at:string}[]>([]);
 const searchRef=useRef<HTMLInputElement|null>(null);
 const panelRef=useRef<HTMLDivElement|null>(null);

 const notify=useCallback((message:string)=>{setToast(message);window.setTimeout(()=>setToast(''),4200)},[]);
 const fetchQueue=useCallback(async()=>{
  setError('');
  try{
   const response=await fetch('/api/cases?limit=250',{cache:'no-store'});
   if(!response.ok)throw new Error('The review queue could not be loaded.');
   const data=await response.json() as QueueResponse;
   setQueue(data);setServerMode(response.headers.get('x-data-mode')==='live'?'live':'demo');
   setSelected(prev=>prev||new URLSearchParams(window.location.search).get('case')||data.items[0]?.question_id||'');
  }catch(e){setError(e instanceof Error?e.message:'Unable to fetch cases');}
  finally{setIsLoading(false)}
 },[]);
 const onCaseRechecked=useCallback(()=>{void fetchQueue();setDetailNonce(n=>n+1)},[fetchQueue]);
 useEffect(()=>{void fetchQueue()},[fetchQueue]);
 useEffect(()=>{
  if(!selected){setDetail(null);return}
  const controller=new AbortController();setDetailLoading(true);setDetail(null);
  void fetch(`/api/cases/${encodeURIComponent(selected)}`,{signal:controller.signal,cache:'no-store'})
   .then(async r=>{if(!r.ok)throw Error(`Case unavailable (${r.status})`);return await r.json() as CaseDetail})
   .then(d=>{if(!controller.signal.aborted){setDetail(d);setReportIndex(0);setShowSolution(false);setExpandedEvidence(false);}})
   .catch(e=>{if(!controller.signal.aborted)setError(e.message)})
   .finally(()=>{if(!controller.signal.aborted)setDetailLoading(false)});
  window.history.replaceState(null,'',selected?`?case=${encodeURIComponent(selected)}`:window.location.pathname);
  if(panelRef.current)panelRef.current.scrollTop=0;
  return ()=>controller.abort();
 },[selected,detailNonce]);
 useEffect(()=>{document.documentElement.dataset.theme=dark?'dark':'light'},[dark]);
 useEffect(()=>{if(view==='audit')void fetch('/api/audit').then(r=>r.json()).then(v=>Array.isArray(v)?setAllAudit(v):setAllAudit([])).catch(()=>setAllAudit([]))},[view]);

 const displayed=useMemo(()=>{
  const term=search.trim().toLowerCase();
  const rows=queue.items.filter(x=>{
   if(filter==='review'&&x.route!=='faculty_review')return false;
   if(filter==='auto'&&x.route!=='auto_apply')return false;
   if(filter==='defect'&&x.verdict!=='defect')return false;
   if(filter==='resolved'&&!['approved','rejected'].includes(x.status))return false;
   if(filter==='unresolved'&&['approved','rejected'].includes(x.status))return false;
   if(subject!=='all'&&x.subject!==subject)return false;
   return !term||[x.question_id,x.chapter,x.subject,x.preview,x.repair||'',x.verdict].join(' ').toLowerCase().includes(term);
  });
  rows.sort((a,b)=>sort==='oldest'?new Date(a.oldest).getTime()-new Date(b.oldest).getTime():sort==='reports'?b.report_count-a.report_count:sort==='confidence'?b.confidence-a.confidence:b.priority-a.priority);
  return rows;
 },[queue,filter,subject,search,sort]);
 const subjects=useMemo(()=>[...new Set(queue.items.map(x=>x.subject))].sort(),[queue]);
 const selectedSummary=queue.items.find(x=>x.question_id===selected);
 const result=detail?.results[0]||null;
 const activeReport=detail?.reports[reportIndex]||null;
 const activeResult=detail?.results.find(x=>x.reportId===activeReport?.id)||result;
 const patch=detail&&result?.edit?previewPatch(detail.question as Record<string,unknown>,result.edit):null;

 const move=useCallback((direction:number)=>{
  if(!displayed.length)return;
  const i=displayed.findIndex(x=>x.question_id===selected);
  setSelected(displayed[Math.max(0,Math.min(displayed.length-1,(i<0?0:i)+direction))].question_id);
 },[displayed,selected]);
 useEffect(()=>{
  const handler=(event:KeyboardEvent)=>{
   const target=event.target as HTMLElement;
   if(['INPUT','TEXTAREA','SELECT'].includes(target?.tagName)||target?.isContentEditable||modal)return;
   if(event.key==='/'){event.preventDefault();searchRef.current?.focus()}
   if(event.key==='j'||event.key==='ArrowDown'){event.preventDefault();move(1)}
   if(event.key==='k'||event.key==='ArrowUp'){event.preventDefault();move(-1)}
   if(event.key==='?'){event.preventDefault();setShortcutHelp(v=>!v)}
   if(event.key==='Escape'){setShortcutHelp(false);setModal(null)}
  };
  document.addEventListener('keydown',handler);return ()=>document.removeEventListener('keydown',handler);
 },[move,modal]);
 const openModal=(action:ActionType)=>{
  if(!result?.edit&&action!=='reject'){notify('No executable patch. Faculty should author the missing content separately.');return;}
  setEditing(result?.edit||{field:'question',find:'',replace:''});setReason('');setModal(action);
 };
 const submit=async()=>{
  if(!detail||!modal||submitting)return;
  setSubmitting(true);
  try{
   const response=await fetch(`/api/cases/${encodeURIComponent(detail.question_id)}/actions`,{
    method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({action:modal,expected_hash:detail.question_hash,expected_revision:detail.revision,actor:actor.trim()||'Faculty reviewer',reason,edit:modal==='edit'?editing:undefined,idempotency_key:crypto.randomUUID()})
   });
   const payload=await response.json();if(!response.ok)throw new Error(payload.detail||'Review action was rejected');
   setModal(null);notify(`${human(modal)} recorded. Production content remains unchanged.`);
   await fetchQueue();setSelected('');window.setTimeout(()=>setSelected(detail.question_id),50);
  }catch(e){notify(e instanceof Error?e.message:'Review action failed');}
  finally{setSubmitting(false)}
 };
 const copy=async(value:string,message='Copied')=>{try{await navigator.clipboard.writeText(value);notify(message)}catch{notify('Clipboard unavailable')}};

 return <div className="shell">
  <aside className={`sidebar ${compact?'sidebar-compact':''}`}>
   <div className="brand"><div className="brand-symbol"><GraduationCap size={23} strokeWidth={2.3}/></div>{!compact&&<div><strong>Acadza<span className="brand-dot">.</span></strong><span>Faculty workspace</span></div>}</div>
   <div className="side-section-label">{!compact?'WORKSPACE':'•••'}</div>
   <button className={`nav-item ${view==='queue'?'nav-active':''}`} onClick={()=>setView('queue')} title="Review queue"><LayoutDashboard size={19}/>{!compact&&<>Review queue<span className="nav-count">{queue.total}</span></>}</button>
   <button className={`nav-item ${view==='audit'?'nav-active':''}`} onClick={()=>setView('audit')} title="Audit trail"><History size={19}/>{!compact&&'Audit trail'}</button>
   <button className={`nav-item ${view==='insights'?'nav-active':''}`} onClick={()=>setView('insights')} title="Insights"><Activity size={19}/>{!compact&&'Insights'}</button>
   <button className={`nav-item ${view==='providers'?'nav-active':''}`} onClick={()=>setView('providers')} title="AI providers"><Settings2 size={19}/>{!compact&&'AI providers'}</button>
   <div className="sidebar-grow"/>
   {!compact&&<div className="sidebar-tip"><span className="tip-light"><Shield size={16}/></span><strong>Safety first</strong><p>AI proposes. Deterministic checks and faculty decide.</p></div>}
   <button className="nav-item sidebar-bottom" onClick={()=>setShortcutHelp(true)} title="Keyboard shortcuts"><Keyboard size={18}/>{!compact&&'Keyboard shortcuts'}{!compact&&<span className="key-cap">?</span>}</button>
   <div className="sidebar-footer"><div className="avatar"><UserRound size={17}/></div>{!compact&&<div><strong>Faculty reviewer</strong><span>Quality assurance</span></div>}<button className="icon-button sidebar-collapse" title="Toggle sidebar" onClick={()=>setCompact(x=>!x)}>{compact?<PanelLeftOpen size={17}/>:<PanelLeftClose size={17}/>}</button></div>
  </aside>
  <div className="main-wrap">
   <header className="topbar"><div className="top-breadcrumb"><span>Question quality</span><ChevronRight size={15}/><strong>{view==='queue'?'Review queue':view==='audit'?'Audit trail':view==='providers'?'AI providers':'Insights'}</strong></div><div className="top-actions"><span className={`connection ${serverMode==='live'?'connection-live':'connection-demo'}`}><span className="pulse-dot"/>{serverMode==='live'?'SQLite connected':'Read-only demo'}</span><button className="icon-button" title="Toggle theme" onClick={()=>setDark(v=>!v)}>{dark?<Sun size={18}/>:<Moon size={18}/>}</button><button className="icon-button" title="Refresh data" onClick={()=>void fetchQueue()}><RefreshCw size={18}/></button><span className="top-avatar">F</span></div></header>
   {view==='queue'?<main className="queue-layout">
    <section className="queue-pane">
     <div className="pane-heading"><div className="eyebrow"><span className="eyebrow-line"/>QUALITY OPERATIONS</div><h1>Review queue<span className="heading-count">{queue.total}</span></h1><p>One question, one decision. Every report considered.</p></div>
     <div className="queue-stats"><div><strong>{queue.items.filter(x=>x.route==='faculty_review'&&!['approved','rejected'].includes(x.status)).length}</strong><span>Needs review</span></div><div><strong>{queue.items.filter(x=>x.route==='auto_apply').length}</strong><span>Auto-eligible</span></div><div><strong>{queue.items.filter(x=>['approved','rejected'].includes(x.status)).length}</strong><span>Resolved</span></div></div>
     <div className="search-wrap"><Search size={17}/><input ref={searchRef} value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search question, topic, issue…" aria-label="Search cases"/><span className="shortcut-key">/</span></div>
     <div className="filters"><select aria-label="Filter by lane" value={filter} onChange={e=>setFilter(e.target.value)}><option value="all">All cases</option><option value="review">Faculty review</option><option value="auto">Auto-eligible</option><option value="defect">Defects</option><option value="unresolved">Unresolved</option><option value="resolved">Resolved</option></select><select aria-label="Filter by subject" value={subject} onChange={e=>setSubject(e.target.value)}><option value="all">All subjects</option>{subjects.map(x=><option key={x}>{x}</option>)}</select></div>
     <div className="queue-small-head"><span>{displayed.length} CASES</span><label>Sort <select value={sort} onChange={e=>setSort(e.target.value)}><option value="priority">Priority</option><option value="oldest">Oldest</option><option value="reports">Most reports</option><option value="confidence">Confidence</option></select></label></div>
     <div className="case-scroll">{isLoading?<div className="state"><LoaderCircle className="spin"/><p>Loading the queue…</p></div>:error&&queue.items.length===0?<div className="state"><TriangleAlert/><p>{error}</p><button onClick={()=>void fetchQueue()}>Retry</button></div>:displayed.length===0?<div className="state"><Search/><p>No cases match your filters.</p><button onClick={()=>{setSearch('');setFilter('all');setSubject('all')}}>Clear filters</button></div>:displayed.map(c=><CaseCard key={c.question_id} item={c} selected={selected===c.question_id} onChoose={()=>{setSelected(c.question_id);setTab('question')}}/>)}</div>
     <div className="queue-footer"><span><span className="queue-green-dot"/> 39 question groups in assignment</span><span><Keyboard size={13}/> J / K</span></div>
    </section>
    <section className="detail-pane" ref={panelRef}>
      {detailLoading?<div className="detail-loading"><div className="skeleton skeleton-title"/><div className="skeleton skeleton-block"/><div className="skeleton skeleton-block"/></div>:detail?<>
       <div className="detail-heading"><div className="detail-head-top"><span className="case-number">CASE / {shortId(detail.question_id)}</span><div className="detail-head-tools"><button className="icon-button" title="Copy question ID" onClick={()=>void copy(detail.question_id,'Question ID copied')}><Copy size={16}/></button><button className="icon-button" title="Copy link" onClick={()=>void copy(window.location.href,'Case link copied')}><ArrowUpRight size={17}/></button><button className="icon-button" title="Previous case" onClick={()=>move(-1)}><ChevronLeft size={17}/></button><button className="icon-button" title="Next case" onClick={()=>move(1)}><ChevronRight size={17}/></button></div></div>
        <h2>{detail.chapter}<span className="heading-muted"> · {detail.subject}</span></h2>
        <div className="detail-meta"><Label kind="blue">{human(detail.question_type)}</Label><Label kind={result?.verdict==='defect'?'red':'green'}>{human(result?.verdict||'Pending')}</Label><Label kind={detail.status==='approved'?'green':detail.status==='rejected'?'red':'muted'}>{human(detail.status)}</Label><span className="hash-meta"><Shield size={13}/> Version {detail.question_hash.slice(0,9)}</span><Label kind={detail.triage_status==='completed'?'green':'muted'}>{detail.triage_status==='completed'?'Live AI checked':detail.triage_status==='precomputed'?'Precomputed · no LLM checks':human(detail.triage_status)}</Label><button className="live-check-link" onClick={()=>setView('providers')}><Settings2 size={14}/> Configure / run AI checks</button></div>
       </div>
       <div className="detail-inner"><EvidencePanel result={activeResult||null} meta={detail.meta} expanded={expandedEvidence} onToggle={()=>setExpandedEvidence(v=>!v)}/>
       {detail.meta.triage_status==='failed_review'&&<div className="warning-line"><TriangleAlert size={17}/> Live AI verification failed. This case needs manual review; no defect was fabricated.</div>}
       <div className="segment-tabs" role="tablist" aria-label="Case details">{([['question',BookOpen,'Question'],['diff',FileDiff,'Proposed fix'],['reports',MessagesSquare,`Reports (${detail.reports.length})`],['audit',History,'Audit trail']] as const).map(([key,Icon,label])=><button role="tab" aria-selected={tab===key} key={key} className={tab===key?'segment-active':''} onClick={()=>setTab(key)}><Icon size={16}/>{label}</button>)}</div>
       {tab==='question'&&<QuestionTab detail={detail} showSolution={showSolution} toggleSolution={()=>setShowSolution(v=>!v)}/>}
       {tab==='diff'&&<DiffTab result={result} patch={patch}/>}
       {tab==='reports'&&<ReportsTab detail={detail} index={reportIndex} onSelect={setReportIndex}/>}
       {tab==='audit'&&<AuditTab detail={detail}/>}
       <ReplyPreview detail={detail} active={activeResult} index={reportIndex} onSelect={setReportIndex}/>
       </div>
       <div className="actionbar"><div className="action-help"><div className="action-help-icon"><Info size={17}/></div><div><strong>Review decision</strong><span>{serverMode==='demo'?'Demo is read-only · Connect SQLite backend to save actions':'Actions are version-checked and audited. Never a direct production write.'}</span></div></div><div className="review-buttons"><button className="review-reject" disabled={serverMode==='demo'||['approved','rejected'].includes(detail.status)} onClick={()=>openModal('reject')}><X size={17}/>Reject</button><button className="review-edit" disabled={serverMode==='demo'||!result?.edit||['approved','rejected'].includes(detail.status)} onClick={()=>openModal('edit')}><SlidersHorizontal size={16}/>Edit</button><button className="review-approve" disabled={serverMode==='demo'||!result?.edit||['approved','rejected'].includes(detail.status)} onClick={()=>openModal('approve')}><Check size={17}/>Approve</button></div></div>
      </>:<div className="detail-empty"><div><BookOpen size={32}/></div><h2>Select a question to review</h2><p>Choose an item from the queue to inspect its evidence, question, proposed patch and student communication.</p></div>}
    </section></main>:view==='audit'?<div className="standalone"><div className="eyebrow">TRACEABLE DECISIONS</div><h1>Audit trail</h1><p>Every human action is preserved as a durable SQLite event. Precomputed decisions do not count as faculty actions.</p><div className="standalone-card">{allAudit.length?allAudit.map(a=><button key={a.id} className="audit-list-row" onClick={()=>{setSelected(a.question_id);setTab('audit');setView('queue')}}><History size={17}/><div><strong>{human(a.action)} · {shortId(a.question_id)}</strong><span>{a.actor} · {a.note||'No note'}</span></div><time>{formatDate(a.created_at)}</time><ArrowUpRight size={16}/></button>):<div className="empty-panel"><History size={30}/><strong>No review activity yet</strong><p>Authenticated approvals, edits and rejections will appear here.</p></div>}</div></div>:view==='providers'?<ProviderSettings serverMode={serverMode} selectedCase={selected} onCaseRechecked={onCaseRechecked}/>:<div className="standalone"><div className="eyebrow">QUALITY SIGNALS</div><h1>Operations overview</h1><p>Sample-based statistics from the supplied Acadza reports, not a production-wide measurement.</p><div className="insights-grid">{[{icon:BookOpen,label:'Question cases',value:queue.total,sub:'Grouped by canonical _id'},{icon:ShieldAlert,label:'Faculty reviews',value:queue.items.filter(x=>x.route==='faculty_review').length,sub:'Potentially high-impact fixes'},{icon:WandSparkles,label:'Auto-eligible',value:queue.items.filter(x=>x.route==='auto_apply').length,sub:'Subject to deterministic gate'},{icon:CheckCheck,label:'Resolved',value:queue.items.filter(x=>['approved','rejected'].includes(x.status)).length,sub:'Human decisions in this workspace'}].map((x,i)=><div key={i} className="insight-card"><x.icon size={20}/><span>{x.label}</span><strong>{x.value}</strong><p>{x.sub}</p></div>)}</div><div className="standalone-card insights-explainer"><Shield size={22}/><div><h3>How urgency is calculated</h3><p>Verified defect severity, grading risk, number of distinct reports, oldest report age, and whether a case needs faculty review. Report volume alone never proves the student is right.</p></div></div></div>}
  </div>
  {modal&&detail&&<ReviewDialog action={modal} detail={detail} actor={actor} setActor={setActor} reason={reason} setReason={setReason} editing={editing} setEditing={setEditing} submitting={submitting} onClose={()=>setModal(null)} onSubmit={()=>void submit()}/>} 
  {shortcutHelp&&<div className="modal-backdrop" onMouseDown={e=>{if(e.target===e.currentTarget)setShortcutHelp(false)}}><div className="shortcuts-modal" role="dialog" aria-modal="true" aria-label="Keyboard shortcuts"><div className="modal-top"><h2>Keyboard shortcuts</h2><button className="icon-button" onClick={()=>setShortcutHelp(false)}><X size={18}/></button></div>{[['/','Focus search'],['J / ↓','Next question'],['K / ↑','Previous question'],['?','Toggle shortcuts'],['Esc','Close overlay']].map(([key,value])=><div className="shortcut-row" key={key}><span>{value}</span><kbd>{key}</kbd></div>)}</div></div>}
  {toast&&<div className="toast" role="status"><Info size={18}/>{toast}<button onClick={()=>setToast('')} aria-label="Dismiss"><X size={15}/></button></div>}
 </div>
}
