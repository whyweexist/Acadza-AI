export type Route = 'auto_apply' | 'faculty_review' | 'no_change';
export type Verdict = 'defect' | 'no_error' | 'display_issue' | 'app_issue' | 'language_mode' | 'already_fixed' | 'not_actionable';
export type Edit = {field: 'question'|'solution'|'answer'|'questionType'; find: string; replace: string};
export type TriageResult = { reportId:string; questionId:string; confidence:number; evidence:string; student_reply:string } & (
  | {verdict:'defect'; repair:string; edit:Edit|null;route:'auto_apply'|'faculty_review'}
  | {verdict:Exclude<Verdict,'defect'>;repair:null;edit:null;route:'no_change'}
);
export interface CaseSummary { question_id:string; subject:string;chapter:string;question_type:string;status:string;triage_status:string;report_count:number; oldest:string;updated_at:string;revision:number;source_hash:string;preview:string;verdict:string;repair:string|null;route:Route;priority:number;confidence:number;evidence:string;primary_result:TriageResult|null }
export interface QueueResponse {items:CaseSummary[];total:number;counts:{all:number;needs_review:number;auto_eligible:number;resolved:number}}
export interface Question { _id:string; qid:string|null;subject:string;chapter:string;questionType:string;updatedAt:string;[key:string]:unknown }
export interface CaseDetail {question_id:string;status:string;triage_status:string;review_note:string;revision:number;question_hash:string;question:Question; normalized:{question_html:string;solution_html:string;safe_question_html?:string;safe_solution_html?:string;question_text:string;solution_text:string;options:Record<string,string>;answer:string|string[];questionType:string;subject:string;chapter:string;}; reports:{id:string;reported_at:string;source:string;comment:string}[]; results:TriageResult[]; meta:{all_edits?:Edit[];static_findings?:{code:string;severity:string;evidence:string}[];safety_reasons?:string[];verification?:Record<string,unknown>;triage_status?:string};audit:{id:string;actor:string;action:string;note:string;created_at:string;before:unknown;after:unknown}[];subject:string;chapter:string;question_type:string;updated_at:string }
export type Tab = 'question' | 'diff' | 'reports' | 'audit';
export type ActionType = 'approve' | 'edit' | 'reject';
