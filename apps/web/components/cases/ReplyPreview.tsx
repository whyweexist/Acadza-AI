'use client';
import {MessageSquare} from 'lucide-react';
import type {CaseDetail,TriageResult} from '@/lib/types';
export function ReplyPreview({detail,active,index,onSelect}:{detail:CaseDetail;active:TriageResult|null|undefined;index:number;onSelect:(n:number)=>void}){
 return <div className="student-reply"><div className="reply-header"><MessageSquare size={17}/><strong>Student reply preview</strong><span>Not sent</span></div><div className="reply-message">{active?.student_reply||'A faculty member will review this issue before we respond.'}</div>
 {detail.reports.length>1&&<div className="reply-select">Reply for <select value={index} onChange={e=>onSelect(Number(e.target.value))}>{detail.reports.map((r,i)=><option key={r.id} value={i}>{r.id}</option>)}</select></div>}
 </div>
}
