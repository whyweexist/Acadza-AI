import type { CaseSummary, Edit } from './types';
export const human = (v?:string|null)=> (v||'').replaceAll('_',' ').replace(/\b\w/g,x=>x.toUpperCase());
export const shortId = (s:string)=>s.slice(0,8)+'…'+s.slice(-5);
export function relative(date?:string) {if(!date)return '—';const days=Math.max(0,Math.floor((Date.now()-new Date(date).getTime())/86400000));return days===0?'Today':`${days}d ago`;}
export function formatDate(s?:string) {return s?new Date(s).toLocaleString('en-IN',{day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'}):'—';}
export function priorityLabel(c: CaseSummary) {if(c.priority>=100)return 'Critical'; if(c.priority>=70)return 'High';if(c.priority>=45)return 'Medium';return 'Low';}
export function fieldValue(source:Record<string,unknown>,field:string) {
  const questionType=String(source.questionType);
  if(field==='questionType')return questionType;
  const body=source[questionType] as Record<string,unknown>|undefined;
  const value=body?.[field];
  return typeof value==='string'?value:JSON.stringify(value??'',null,0);
}
export function previewPatch(source:Record<string,unknown>,edit:Edit|null): {before:string;after:string;ok:boolean;reason?:string} | null {
  if(!edit)return null;
  const before=fieldValue(source,edit.field);
  const i=before.indexOf(edit.find),second=before.indexOf(edit.find,i+edit.find.length);
  if(!edit.find||i<0||second>=0)return {before,after:before,ok:false,reason:'Patch must match exactly once in the raw source field.'};
  return {before,after:before.slice(0,i)+edit.replace+before.slice(i+edit.find.length),ok:true};
}
export function diffSegments(before:string,after:string) {
  let begin=0;while(begin<before.length&&begin<after.length&&before[begin]===after[begin])begin++;
  let tail=0;while(tail<before.length-begin&&tail<after.length-begin&&before[before.length-1-tail]===after[after.length-1-tail])tail++;
  return {prefix:before.slice(0,begin),removed:before.slice(begin,before.length-tail),added:after.slice(begin,after.length-tail),suffix:tail?before.slice(before.length-tail):''};
}
