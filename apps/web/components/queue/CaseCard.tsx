import {MessageSquare} from 'lucide-react';
import {human,relative,priorityLabel} from '@/lib/utils';
import type {CaseSummary} from '@/lib/types';

export function CaseCard({item,selected,onChoose}:{item:CaseSummary;selected:boolean;onChoose:()=>void}){
 return <button className={`case-item ${selected?'case-selected':''}`} onClick={onChoose} aria-current={selected?'true':undefined}>
  <div className="case-top"><span className={`priority-dot ${priorityLabel(item).toLowerCase()}`}/><span className="case-topic">{item.subject}<span className="case-separator">/</span>{item.chapter}</span><span className="case-age">{relative(item.oldest)}</span></div>
  <strong className="case-title">{item.repair?human(item.repair):human(item.verdict)}</strong>
  <div className="case-preview">{item.preview||'No comment provided'}</div>
  <div className="case-bottom"><span className={`mini-route ${item.route==='faculty_review'?'route-review':item.route==='auto_apply'?'route-auto':'route-none'}`}>{item.route==='faculty_review'?'Review':item.route==='auto_apply'?'Auto-eligible':'No change'}</span><span className="case-report-count"><MessageSquare size={13}/>{item.report_count}</span><span className="case-confidence">{Math.round(item.confidence*100)}%</span></div>
 </button>
}
