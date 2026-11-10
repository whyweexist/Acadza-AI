'use client';
import {ArrowRight,WandSparkles} from 'lucide-react';
import type {CaseDetail,TriageResult} from '@/lib/types';
export function EvidencePanel({result,meta,expanded,onToggle}:{result:TriageResult|null;meta:CaseDetail['meta'];expanded:boolean;onToggle:()=>void}){
 const precomputed = meta.triage_status === 'precomputed';
 return <div className="decision-bar"><div className="decision-icon"><WandSparkles size={20}/></div><div className="decision-body"><div className="decision-title"><strong>{precomputed?'Precomputed assessment':'AI assessment'}</strong><span className="confidence-pill">{Math.round((result?.confidence||0)*100)}% {precomputed?'baseline score':'evidence score'}</span></div>{precomputed&&<p className="subtle">No live LLM verification has run for this case. The decision is from the bundled demonstration baseline.</p>}<p>{result?.evidence||'Awaiting independent verification.'}</p>
 {expanded&&<div className="extra-evidence"><strong>Verification & safeguards</strong>{meta.safety_reasons?.length?<ul>{meta.safety_reasons.map((reason,index)=><li key={index}>{reason}</li>)}</ul>:<p>No safety-block reasons recorded in this snapshot.</p>}{meta.verification&&<pre>{JSON.stringify(meta.verification,null,2)}</pre>}</div>}
 <button className="inline-link" onClick={onToggle}>{expanded?'Hide technical evidence':'View technical evidence'}<ArrowRight size={14}/></button>
 </div></div>
}
