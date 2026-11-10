'use client';
import {BookOpen,ChevronDown,ChevronRight,History,ShieldAlert,TriangleAlert} from 'lucide-react';
import type {CaseDetail,TriageResult} from '@/lib/types';
import {human,shortId,formatDate,diffSegments} from '@/lib/utils';
import {MathContent} from '../MathContent';

type Patch={before:string;after:string;ok:boolean;reason?:string}|null;
export function QuestionTab({detail,showSolution,toggleSolution}:{detail:CaseDetail;showSolution:boolean;toggleSolution:()=>void}){
 return <div className="tab-body"><div className="content-topline"><span className="section-label">ORIGINAL QUESTION</span><span className="question-id">#{shortId(detail.question_id)}</span></div>
  <div className="question-card"><MathContent html={detail.normalized.safe_question_html||detail.normalized.question_html}/></div>
  <div className="answer-row"><span>Stored answer</span><strong>{Array.isArray(detail.normalized.answer)?detail.normalized.answer.join(', '):detail.normalized.answer}</strong><span className="answer-type">{human(detail.question_type)}</span></div>
  <button className="solution-toggle" onClick={toggleSolution}><BookOpen size={17}/>{showSolution?'Hide stored solution':'Show stored solution'}<ChevronDown size={16} className={showSolution?'rotate':''}/></button>
  {showSolution&&<div className="solution-card"><MathContent html={detail.normalized.safe_solution_html||detail.normalized.solution_html} empty="No stored solution"/></div>}
 </div>
}
export function DiffTab({result,patch}:{result:TriageResult|null;patch:Patch}){
 const diff=patch?.ok?diffSegments(patch.before,patch.after):null;
 return <div className="tab-body"><div className="content-topline"><span className="section-label">PROPOSED CHANGE</span><span className={`tag tag-${patch?.ok?'green':'muted'}`}>{result?.edit?'Surgical patch':'No proposed patch'}</span></div>
  {result?.edit&&patch?<><div className="patch-meta"><span>FIELD</span><strong>{result.edit.field}</strong><span>PATCH</span><strong>Exact match · {patch.ok?'unique':'invalid'}</strong></div>
   <div className="diff-block"><div className="diff-label"><span className="minus-symbol">−</span> Before <span className="diff-right">Stored value</span></div><pre className="diff-code">{diff?<>{diff.prefix}<mark className="diff-remove">{diff.removed}</mark>{diff.suffix}</>:patch.before}</pre></div>
   <div className="diff-block"><div className="diff-label"><span className="plus-symbol">+</span> After <span className="diff-right">Proposed value</span></div><pre className="diff-code">{diff?<>{diff.prefix}<mark className="diff-add">{diff.added}</mark>{diff.suffix}</>:patch.after}</pre></div>
   {!patch.ok&&<div className="warning-line"><TriangleAlert size={16}/>{patch.reason}</div>}
   {result.edit.field==='question'&&patch.ok&&<><div className="content-topline section-gap"><span className="section-label">RENDERED AFTER</span></div><div className="question-card"><MathContent html={patch.after}/></div></>}
  </>:<div className="empty-panel"><ShieldAlert size={27}/><strong>Human investigation required</strong><p>No executable patch exists for this decision. Faculty must review or author missing content through a separate controlled workflow.</p></div>}
 </div>
}
export function ReportsTab({detail,index,onSelect}:{detail:CaseDetail;index:number;onSelect:(index:number)=>void}){
 return <div className="tab-body"><div className="content-topline"><span className="section-label">STUDENT REPORTS</span><span className="subtle">{detail.reports.length} independent submissions</span></div><div className="report-list">
  {detail.reports.map((r,i)=><button key={r.id} onClick={()=>onSelect(i)} className={`report-row ${index===i?'report-active':''}`}><span className="report-avatar">{r.source==='android'?'A':r.source==='ios'?'i':'W'}</span><span><strong>{r.id} <em>{r.source}</em></strong><span>{r.comment}</span><small>{formatDate(r.reported_at)}</small></span><ChevronRight size={16}/></button>)}
 </div></div>
}
export function AuditTab({detail}:{detail:CaseDetail}){
 return <div className="tab-body"><div className="content-topline"><span className="section-label">REVIEW ACTIVITY</span><span className="subtle">Append-only events</span></div>
 {detail.audit.length?detail.audit.map(event=><div className="audit-event" key={event.id}><div className="audit-mark"><History size={16}/></div><div><strong>{human(event.action)} <span>by {event.actor}</span></strong><p>{event.note||'No additional note'}</p><small>{formatDate(event.created_at)}</small></div></div>):<div className="empty-panel"><History size={28}/><strong>No review actions yet</strong><p>Approve, edit and reject events appear here with their actor and timestamp.</p></div>}
 </div>
}
