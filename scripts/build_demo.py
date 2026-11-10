"""Build portable read-only UI fixtures from source data and the curated baseline.
This is a data packaging step; it never runs the app or its tests.
"""
from __future__ import annotations
import hashlib
import json
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]
WEB=ROOT/'apps'/'web'/'public'
WEB.mkdir(parents=True,exist_ok=True)
read=lambda name:json.loads((ROOT/name).read_text(encoding='utf-8'))
questions=read('data/questions.json'); reports=read('data/reports.json'); results=read('results.json')
by=defaultdict(list); rr=defaultdict(list)
for r in reports:by[r['questionId']].append(r)
for r in results:rr[r['questionId']].append(r)
def hashq(q):return hashlib.sha256(json.dumps(q,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def plain(s):return ' '.join(BeautifulSoup(s or '', 'html.parser').get_text(' ',strip=True).split())
def normalized(q):
 b=q[q['questionType']];return {'questionType':q['questionType'],'question_html':b.get('question',''),'solution_html':b.get('solution',''),'safe_question_html':None,'safe_solution_html':None,
 'question_text':plain(b.get('question','')),'solution_text':plain(b.get('solution','')),'options':{},'answer':b.get('answer'), 'subject':q.get('subject'),'chapter':q.get('chapter')}
def priority(q,rs,primary):
 if not primary:return 0
 sev=52 if primary['verdict']=='defect' else 12
 if primary['repair'] in ('answer_key','unsound','type_mismatch'):sev+=30
 if primary['repair'] in ('diagram','option_repair','wrong_question'):sev+=21
 age=(datetime.now(timezone.utc)-datetime.fromisoformat(min(r['reportedAt'] for r in rs).replace('Z','+00:00'))).total_seconds()/86400
 return round(sev+min(len(rs),10)*7+min(max(age,0),30)*.4+(8 if primary['route']=='faculty_review' else 0),1)

index=[];detail={}
for q in questions:
 qid=q['_id'];rs=sorted(by.get(qid,[]),key=lambda r:r['reportedAt'])
 if not rs:continue
 out=sorted(rr[qid],key=lambda r:r['reportId']);p=out[0] if out else None
 h=hashq(q)
 summary={'question_id':qid,'subject':q.get('subject'),'chapter':q.get('chapter'),'question_type':q['questionType'],
 'status':'pending','triage_status':'precomputed','report_count':len(rs),'oldest':rs[0]['reportedAt'],'updated_at':q.get('updatedAt',''),
 'revision':0,'source_hash':h,'preview':rs[0]['comment'],'verdict':p['verdict'] if p else 'pending', 'repair':p['repair'] if p else None,
 'route':p['route'] if p else 'faculty_review','priority':priority(q,rs,p),'confidence':p['confidence'] if p else 0,
 'evidence':p['evidence'] if p else 'Awaiting triage','primary_result':p}
 index.append(summary)
 detail[qid]={
 'question_id':qid,'status':'pending','triage_status':'precomputed','review_note':'','revision':0,
 'question_hash':h,'question':q,'normalized':normalized(q),
 'reports':[{'id':r['reportId'],'reported_at':r['reportedAt'],'source':r['source'],'comment':r['comment']} for r in rs],
 'results':out,'meta':{'all_edits':[v['edit'] for v in out if v.get('edit')][:1], 'static_findings':[], 'safety_reasons':[], 'triage_status':'precomputed', 'mode':'manually_curated_sample_no_model_executed'},
 'audit':[],'subject':q.get('subject'),'chapter':q.get('chapter'),'question_type':q['questionType'],'updated_at':q.get('updatedAt')}
index.sort(key=lambda x:(-x['priority'],x['oldest'],x['question_id']))
package={'items':index,'total':len(index),'counts':{'all':len(index),'needs_review':sum(c['route']=='faculty_review' for c in index),'auto_eligible':sum(c['route']=='auto_apply' for c in index),'resolved':0}}
(WEB/'demo-index.json').write_text(json.dumps(package,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
(WEB/'demo-cases.json').write_text(json.dumps(detail,ensure_ascii=False,separators=(',',':')),encoding='utf-8')

unreported=[]
for q in questions:
 if q['_id'] in by:continue
 b=q[q['questionType']]
 warnings=[]
 if not b.get('solution'):warnings.append({'code':'solution_empty','evidence':'Stored solution field empty; independent review needed'})
 if q['questionType']=='mcq' and (not isinstance(b.get('answer'),list) or any(not isinstance(v,str) or len(v)!=1 or v not in 'ABCD' for v in b.get('answer',[]))):
  warnings.append({'code':'mcq_answer_shape','evidence':'MCQ answer not a list of single option letters'})
 if r'\frac' in b.get('question',''):warnings.append({'code':'latex_leak','evidence':'Raw LaTeX appears in question'})
 unreported.append({'questionId':q['_id'],'subject':q.get('subject'),'chapter':q.get('chapter'),'status':'candidate_only_unverified','findings':warnings})
(ROOT/'findings.json').write_text(json.dumps(unreported,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(f'Packaged {len(index)} cases and {len(unreported)} unreported question scans as static demo files (no tests executed).')
