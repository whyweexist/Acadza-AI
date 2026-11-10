'use client';
import {Check,LoaderCircle,Shield,X} from 'lucide-react';
import type {ActionType,CaseDetail,Edit} from '@/lib/types';
import {human} from '@/lib/utils';
export function ReviewDialog({action,detail,actor,setActor,reason,setReason,editing,setEditing,submitting,onClose,onSubmit}:{
 action:ActionType;detail:CaseDetail;actor:string;setActor:(v:string)=>void;reason:string;setReason:(v:string)=>void;
 editing:Edit;setEditing:(v:Edit)=>void;submitting:boolean;onClose:()=>void;onSubmit:()=>void;
}){
 return <div className="modal-backdrop" onMouseDown={e=>{if(e.target===e.currentTarget)onClose()}}><div className="review-modal" role="dialog" aria-modal="true" aria-label={`${human(action)} case`}>
  <div className="modal-top"><div><span className="eyebrow">FACULTY REVIEW</span><h2>{human(action)} case</h2></div><button className="icon-button" title="Close" onClick={onClose}><X size={19}/></button></div>
  <p className="modal-description">{action==='approve'?'Approve this patch for the review workflow. Production data is not modified.':action==='edit'?'Propose a surgical edit. The server rechecks its exact match, field scope, and source version.':'Reject the proposed correction and preserve the original question.'}</p>
  <label className="modal-label" htmlFor="actor">Reviewer</label><input id="actor" className="modal-input" value={actor} onChange={e=>setActor(e.target.value)} maxLength={120}/>
  {action==='edit'&&<div className="edit-fields"><label className="modal-label" htmlFor="edit-field">Field</label><select id="edit-field" className="modal-input" value={editing.field} onChange={e=>setEditing({...editing,field:e.target.value as Edit['field']})}>{['question','solution','answer','questionType'].map(v=><option key={v}>{v}</option>)}</select>
   <label className="modal-label" htmlFor="edit-find">Find — must occur exactly once</label><textarea id="edit-find" className="modal-input" rows={3} value={editing.find} onChange={e=>setEditing({...editing,find:e.target.value})}/>
   <label className="modal-label" htmlFor="edit-replace">Replace</label><textarea id="edit-replace" className="modal-input" rows={3} value={editing.replace} onChange={e=>setEditing({...editing,replace:e.target.value})}/></div>}
  <label className="modal-label" htmlFor="reason">Reason / notes</label><textarea id="reason" className="modal-input" rows={3} value={reason} onChange={e=>setReason(e.target.value)} placeholder="Add context to the audit trail…" maxLength={1000}/>
  <div className="modal-warning"><Shield size={16}/> Version check: {detail.question_hash.slice(0,12)} · revision {detail.revision}</div>
  <div className="modal-actions"><button onClick={onClose} className="review-edit">Cancel</button><button disabled={submitting||!actor.trim()||(action==='edit'&&!editing.find)} onClick={onSubmit} className="review-approve">{submitting?<LoaderCircle className="spin" size={16}/>:<Check size={16}/>}Confirm {action}</button></div>
 </div></div>
}
