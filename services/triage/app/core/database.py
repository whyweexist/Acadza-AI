"""SQLite-only persistence: WAL, short write transactions, optimistic revisions."""
from __future__ import annotations
import asyncio
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import aiosqlite
from .loader import fingerprint, question_body, raw_field, read_json
from .normalization import normalized_question, sanitize_markup
from .contracts import Edit, ReviewAction
from .safety import apply_patch
from .settings import settings, ROOT


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS questions (
 id TEXT PRIMARY KEY, source_json TEXT NOT NULL, source_hash TEXT NOT NULL,
 subject TEXT NOT NULL, chapter TEXT NOT NULL, question_type TEXT NOT NULL, updated_at TEXT
);
CREATE TABLE IF NOT EXISTS reports (
 id TEXT PRIMARY KEY, question_id TEXT NOT NULL REFERENCES questions(id),
 reported_at TEXT NOT NULL, source TEXT NOT NULL, comment TEXT NOT NULL,
 student_id TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_reports_question ON reports(question_id);
CREATE TABLE IF NOT EXISTS cases (
 question_id TEXT PRIMARY KEY REFERENCES questions(id), status TEXT NOT NULL DEFAULT 'pending',
 triage_status TEXT NOT NULL DEFAULT 'pending', review_note TEXT NOT NULL DEFAULT '',
 revision INTEGER NOT NULL DEFAULT 0, triage_hash TEXT, meta_json TEXT NOT NULL DEFAULT '{}', updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cases_status ON cases(status);
CREATE TABLE IF NOT EXISTS triage_results (
 report_id TEXT PRIMARY KEY REFERENCES reports(id), question_id TEXT NOT NULL,
 result_json TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_triage_case ON triage_results(question_id);
CREATE TABLE IF NOT EXISTS audit_events (
 id TEXT PRIMARY KEY, question_id TEXT NOT NULL REFERENCES cases(question_id),
 actor TEXT NOT NULL, action TEXT NOT NULL, before_json TEXT NOT NULL, after_json TEXT NOT NULL,
 note TEXT NOT NULL, created_at TEXT NOT NULL, idempotency_key TEXT UNIQUE
);
CREATE INDEX IF NOT EXISTS idx_audit_case ON audit_events(question_id, created_at);
CREATE TABLE IF NOT EXISTS llm_cache (
 fingerprint TEXT PRIMARY KEY, output_json TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS triage_jobs (
 id TEXT PRIMARY KEY, question_id TEXT NOT NULL REFERENCES cases(question_id),
 provider TEXT NOT NULL, status TEXT NOT NULL, message TEXT NOT NULL DEFAULT '',
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_triage_jobs_question ON triage_jobs(question_id, created_at);
"""


class Conflict(Exception):
    pass


class InvalidReview(Exception):
    pass


class Database:
    def __init__(self, path: str | None = None):
        self.path = Path(path or settings().db_file)

    async def open(self) -> aiosqlite.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        c = await aiosqlite.connect(str(self.path), timeout=12.0)
        c.row_factory = aiosqlite.Row
        await c.execute("PRAGMA foreign_keys=ON")
        await c.execute("PRAGMA busy_timeout=12000")
        await c.execute("PRAGMA journal_mode=WAL")
        return c

    async def setup(self) -> None:
        c = await self.open()
        try:
            await c.executescript(SCHEMA)
            await c.commit()
        finally:
            await c.close()

    async def seed(self) -> None:
        """Idempotent fixture import; never overwrites review decisions or source snapshots."""
        await self.setup()
        questions, reports = read_json("questions.json"), read_json("reports.json")
        file = ROOT / "results.json"
        seeds = json.loads(file.read_text(encoding="utf-8")) if file.exists() else []
        c = await self.open()
        try:
            await c.execute("BEGIN IMMEDIATE")
            for q in questions:
                await c.execute("INSERT OR IGNORE INTO questions(id,source_json,source_hash,subject,chapter,question_type,updated_at) VALUES(?,?,?,?,?,?,?)",
                                (q["_id"],json.dumps(q,ensure_ascii=False),fingerprint(q),q.get("subject", "Unknown"),q.get("chapter", "Unknown"),q["questionType"],q.get("updatedAt")))
            for r in reports:
                await c.execute("INSERT OR IGNORE INTO reports VALUES(?,?,?,?,?,?)",(r["reportId"],r["questionId"],r["reportedAt"],r["source"],r.get("comment", ""),r["studentId"]))
                await c.execute("INSERT OR IGNORE INTO cases(question_id,updated_at) VALUES(?,?)",(r["questionId"],utcnow()))
            for v in seeds:
                await c.execute("INSERT OR IGNORE INTO triage_results VALUES(?,?,?,?)",(v["reportId"],v["questionId"],json.dumps(v,ensure_ascii=False),utcnow()))
            for q in questions:
                if any(r["questionId"]==q["_id"] for r in reports):
                    await c.execute("UPDATE cases SET triage_hash=COALESCE(triage_hash,?),triage_status=CASE WHEN triage_status='pending' AND EXISTS(SELECT 1 FROM triage_results WHERE question_id=?) THEN 'precomputed' ELSE triage_status END WHERE question_id=?",(fingerprint(q),q["_id"],q["_id"]))
            await c.commit()
        except Exception:
            await c.rollback()
            raise
        finally:
            await c.close()

    async def cache_read(self, fingerprint_: str) -> str | None:
        c=await self.open()
        try:
            cur=await c.execute("SELECT output_json FROM llm_cache WHERE fingerprint=?",(fingerprint_,))
            row=await cur.fetchone()
            return row[0] if row else None
        finally:
            await c.close()

    async def cache_write(self, fingerprint_: str, output: str) -> None:
        c=await self.open()
        try:
            await c.execute("INSERT OR REPLACE INTO llm_cache VALUES(?,?,?)",(fingerprint_,output,utcnow()))
            await c.commit()
        finally: await c.close()

    async def store_results(self, qid: str, results: list[dict], meta: dict) -> None:
        c=await self.open()
        try:
            await c.execute("BEGIN IMMEDIATE")
            cur=await c.execute("SELECT source_hash FROM questions WHERE id=?",(qid,))
            row=await cur.fetchone()
            if row is None or row["source_hash"]!=meta["question_hash"]:
                raise Conflict("question version changed while triaging")
            for v in results:
                await c.execute("INSERT OR REPLACE INTO triage_results VALUES(?,?,?,?)",(v["reportId"],qid,json.dumps(v,ensure_ascii=False),utcnow()))
            await c.execute("UPDATE cases SET triage_status='completed',triage_hash=?,meta_json=?,updated_at=? WHERE question_id=?",(meta["question_hash"],json.dumps(meta,ensure_ascii=False),utcnow(),qid))
            triage_event_key='triage:'+qid+':'+meta['question_hash']+':'+meta.get('prompt_version','unknown')+':'+meta.get('execution_id','initial')
            await c.execute("INSERT OR IGNORE INTO audit_events VALUES(?,?,?,?,?,?,?,?,?)",
                            (str(uuid.uuid4()),qid,'AI pipeline','triage_generated','{}',
                             json.dumps({'report_ids':[r['reportId'] for r in results],'question_hash':meta['question_hash'],'routes':[r['route'] for r in results],'provider':meta.get('provider','unknown'),'models':meta.get('models',{})},ensure_ascii=False),
                             'Generated and stored advisory results, no production mutation',utcnow(),triage_event_key))
            await c.commit()
        except Exception:
            await c.rollback();raise
        finally:await c.close()

    async def flag_failure(self, qid: str, reason: str) -> None:
        c=await self.open()
        try:
            await c.execute("INSERT OR IGNORE INTO cases(question_id,updated_at) VALUES(?,?)",(qid,utcnow()))
            await c.execute("UPDATE cases SET triage_status='failed_review',status='needs_review',review_note=?,updated_at=? WHERE question_id=?",(reason[:1000],utcnow(),qid))
            await c.commit()
        finally:await c.close()

    async def list_cases(self, search: str = "", status: str = "all", subject: str = "all", route: str = "all", offset: int = 0, limit: int = 100) -> dict:
        """SQLite JSON1 + indexed report aggregation; pagination and filtering in SQL."""
        c = await self.open()
        try:
            base = """
            WITH report_stats AS (
              SELECT question_id, COUNT(*) report_count, MIN(reported_at) oldest
              FROM reports GROUP BY question_id
            ), first_triage AS (
              SELECT tr.question_id,tr.result_json
              FROM triage_results tr
              WHERE tr.report_id=(SELECT MIN(t2.report_id) FROM triage_results t2 WHERE t2.question_id=tr.question_id)
            ), case_data AS (
              SELECT ca.question_id,ca.status,ca.triage_status,ca.revision,ca.updated_at,
                     q.subject,q.chapter,q.question_type,q.source_hash,
                     rs.report_count,rs.oldest,
                     (SELECT comment FROM reports r WHERE r.question_id=ca.question_id ORDER BY reported_at LIMIT 1) preview,
                     ft.result_json primary_result,
                     COALESCE(json_extract(ft.result_json,'$.route'),'faculty_review') route,
                     COALESCE(json_extract(ft.result_json,'$.verdict'),'pending') verdict,
                     json_extract(ft.result_json,'$.repair') repair,
                     COALESCE(json_extract(ft.result_json,'$.confidence'),0) confidence,
                     COALESCE(json_extract(ft.result_json,'$.evidence'),'Awaiting triage') evidence
              FROM cases ca JOIN questions q ON q.id=ca.question_id
              JOIN report_stats rs ON rs.question_id=ca.question_id
              LEFT JOIN first_triage ft ON ft.question_id=ca.question_id
            ), ranked AS (
              SELECT *, ROUND(
                CASE WHEN verdict='defect' THEN 52 ELSE 12 END
                + CASE WHEN repair IN ('answer_key','unsound','type_mismatch') THEN 30 ELSE 0 END
                + CASE WHEN repair IN ('diagram','option_repair','wrong_question') THEN 21 ELSE 0 END
                + MIN(report_count,10)*7
                + MIN(MAX(julianday('now')-julianday(oldest),0),30)*0.4
                + CASE WHEN route='faculty_review' THEN 8 ELSE 0 END, 1) priority
              FROM case_data
            )
            """
            where = "WHERE (?='all' OR status=?) AND (?='all' OR subject=?) AND (?='all' OR route=?) AND (?='' OR question_id LIKE ? OR subject LIKE ? OR chapter LIKE ? OR preview LIKE ? OR repair LIKE ?)"
            term = "%" + search + "%"
            params = (status,status,subject,subject,route,route,search,term,term,term,term,term)
            cur=await c.execute(base+f"SELECT COUNT(*) FROM ranked {where}",params)
            total=(await cur.fetchone())[0]
            cur=await c.execute(base+f"SELECT * FROM ranked {where} ORDER BY priority DESC, oldest, question_id LIMIT ? OFFSET ?",params+(limit,offset))
            rows=await cur.fetchall()
            items=[]
            for row in rows:
                d=dict(row)
                d['primary_result']=json.loads(d['primary_result']) if d.get('primary_result') else None
                items.append(d)
            cur=await c.execute("SELECT COUNT(*) FROM cases")
            all_count=(await cur.fetchone())[0]
            cur=await c.execute("SELECT COUNT(*) FROM cases WHERE status IN ('approved','rejected')")
            resolved=(await cur.fetchone())[0]
            cur=await c.execute("""SELECT
                SUM(CASE WHEN json_extract(t.result_json,'$.route')='auto_apply' THEN 1 ELSE 0 END),
                SUM(CASE WHEN json_extract(t.result_json,'$.route')='faculty_review' AND ca.status NOT IN ('approved','rejected') THEN 1 ELSE 0 END)
                FROM cases ca LEFT JOIN triage_results t ON t.report_id=(SELECT MIN(r.report_id) FROM triage_results r WHERE r.question_id=ca.question_id)""")
            summary=await cur.fetchone()
            return {'items':items,'total':total,'counts':{'all':all_count,'auto_eligible':summary[0] or 0,'needs_review':summary[1] or 0,'resolved':resolved}}
        finally:
            await c.close()

    async def get_case(self,qid:str)->dict|None:
        c=await self.open()
        try:
            cur=await c.execute("SELECT ca.*,q.source_json,q.source_hash,q.subject,q.chapter,q.question_type FROM cases ca JOIN questions q ON q.id=ca.question_id WHERE ca.question_id=?",(qid,))
            row=await cur.fetchone()
            if row is None:return None
            d=dict(row)
            question=json.loads(d.pop("source_json"));d["question_hash"]=d.pop("source_hash")
            d["question"]=question
            n=normalized_question(question)
            n["safe_question_html"]=sanitize_markup(n["question_html"])
            n["safe_solution_html"]=sanitize_markup(n["solution_html"])
            d["normalized"]=n
            d["meta"]=json.loads(d.pop("meta_json"))
            cur=await c.execute("SELECT id,reported_at,source,comment FROM reports WHERE question_id=? ORDER BY reported_at",(qid,))
            d["reports"]=[dict(x) for x in await cur.fetchall()]
            cur=await c.execute("SELECT result_json FROM triage_results WHERE question_id=? ORDER BY report_id",(qid,))
            d["results"]=[json.loads(x[0]) for x in await cur.fetchall()]
            cur=await c.execute("SELECT id,actor,action,before_json,after_json,note,created_at FROM audit_events WHERE question_id=? ORDER BY created_at DESC",(qid,))
            d["audit"]=[{**dict(x),"before":json.loads(x["before_json"]),"after":json.loads(x["after_json"])} for x in await cur.fetchall()]
            for a in d["audit"]:
                a.pop("before_json",None);a.pop("after_json",None)
            return d
        finally:await c.close()

    async def act(self,qid:str, action:ReviewAction)->dict:
        c=await self.open()
        try:
            await c.execute("BEGIN IMMEDIATE")
            cur=await c.execute("SELECT id,action FROM audit_events WHERE idempotency_key=?",(action.idempotency_key,))
            old=await cur.fetchone()
            if old:
                await c.rollback()
                return {"ok":True,"idempotent":True,"audit_id":old["id"]}
            cur=await c.execute("SELECT ca.revision,ca.status,ca.triage_hash,q.source_hash,q.source_json FROM cases ca JOIN questions q ON q.id=ca.question_id WHERE ca.question_id=?",(qid,))
            state=await cur.fetchone()
            if state is None:raise InvalidReview("Case not found")
            if state["revision"]!=action.expected_revision:raise Conflict("Another reviewer has updated this case; refresh it")
            if state["source_hash"]!=action.expected_hash or state["triage_hash"]!=action.expected_hash:
                raise Conflict("Question changed since triage; re-triage before approving")
            if state["status"] in ("approved","rejected"):
                raise Conflict("Case is already resolved")
            cur=await c.execute("SELECT result_json FROM triage_results WHERE question_id=? ORDER BY report_id LIMIT 1",(qid,))
            raw=await cur.fetchone()
            if not raw:raise InvalidReview("No validated triage proposal is available")
            result=json.loads(raw[0]);taxonomy=read_json("taxonomy.json")
            before={"status":state["status"],"revision":state["revision"],"edit":result.get("edit")}
            after={"status":state["status"],"revision":state["revision"]+1,"edit":result.get("edit")}
            edit = action.edit if action.action=="edit" else Edit.model_validate(result["edit"]) if result.get("edit") else None
            if action.action in ("approve","edit"):
                if result["verdict"]!="defect":raise InvalidReview("No defect patch exists for this case")
                rule=taxonomy["repairs"][result["repair"]]
                if not edit or edit.field not in rule["fields"]:
                    raise InvalidReview("Patch unavailable or outside taxonomy scope; use a separate authored-content workflow")
                source=json.loads(state["source_json"])
                try:
                    patched=apply_patch(source,edit,action.expected_hash)
                    from .static_checks import inspect_question
                    newly_critical={x.code for x in inspect_question(patched) if x.severity=="critical"}-{x.code for x in inspect_question(source) if x.severity=="critical"}
                    if newly_critical:raise ValueError("patch introduces critical static violations")
                except (ValueError,KeyError,TypeError) as exc:
                    raise InvalidReview(str(exc)) from exc
                after["edit"]=edit.model_dump()
                after["patch_preview"]={"before":raw_field(source,edit.field),"after":raw_field(patched,edit.field)}
                after["status"]="approved" if action.action=="approve" else "needs_review"
                if action.action == "edit":
                    # Persist revised proposal, but force another faculty review; never auto-apply it.
                    cur=await c.execute("SELECT report_id,result_json FROM triage_results WHERE question_id=?",(qid,))
                    for record in await cur.fetchall():
                        candidate=json.loads(record["result_json"])
                        if candidate["verdict"] != "defect":
                            continue
                        candidate["edit"]=edit.model_dump()
                        candidate["route"]="faculty_review"
                        await c.execute("UPDATE triage_results SET result_json=? WHERE report_id=?",
                                        (json.dumps(candidate,ensure_ascii=False),record["report_id"]))
            elif action.action=="reject":after["status"]="rejected"
            audit_id=str(uuid.uuid4())
            await c.execute("INSERT INTO audit_events VALUES(?,?,?,?,?,?,?,?,?)",(audit_id,qid,action.actor,action.action,json.dumps(before,ensure_ascii=False),json.dumps(after,ensure_ascii=False),action.reason,utcnow(),action.idempotency_key))
            await c.execute("UPDATE cases SET status=?,revision=revision+1,review_note=?,updated_at=? WHERE question_id=?",(after["status"],action.reason,utcnow(),qid))
            await c.commit()
            return {"ok":True,"audit_id":audit_id,"status":after["status"],"revision":after["revision"],"production_applied":False}
        except Exception:
            await c.rollback()
            raise
        finally:await c.close()

    async def audit(self,limit:int=100)->list[dict]:
        c=await self.open()
        try:
            cur=await c.execute("SELECT id,question_id,actor,action,note,created_at FROM audit_events ORDER BY created_at DESC LIMIT ?",(limit,))
            return [dict(x) for x in await cur.fetchall()]
        finally:await c.close()


    async def fail_interrupted_jobs(self) -> None:
        """The demo runner is in-process; never claim old unfinished jobs succeeded."""
        c=await self.open()
        try:
            await c.execute("UPDATE triage_jobs SET status='interrupted',message='API restarted before the verification finished',updated_at=? WHERE status IN ('queued','running')", (utcnow(),))
            await c.commit()
        finally:
            await c.close()

    async def queue_triage(self, qid: str, provider: str) -> dict:
        c=await self.open()
        try:
            await c.execute('BEGIN IMMEDIATE')
            cur=await c.execute('SELECT status FROM cases WHERE question_id=?', (qid,))
            case=await cur.fetchone()
            if not case:
                raise InvalidReview('Unknown question case')
            if case['status'] in ('approved','rejected'):
                raise Conflict('Case was resolved; reopen through a faculty workflow before re-triaging')
            cur=await c.execute("SELECT * FROM triage_jobs WHERE question_id=? AND status IN ('queued','running') ORDER BY created_at DESC LIMIT 1", (qid,))
            previous=await cur.fetchone()
            if previous:
                await c.commit()
                return dict(previous)
            job_id=str(uuid.uuid4())
            now=utcnow()
            await c.execute('INSERT INTO triage_jobs(id,question_id,provider,status,message,created_at,updated_at) VALUES(?,?,?,?,?,?,?)',
                            (job_id,qid,provider,'queued','Waiting for verification worker',now,now))
            await c.commit()
            return {'id':job_id,'question_id':qid,'provider':provider,'status':'queued','message':'Waiting for verification worker','created_at':now,'updated_at':now}
        except Exception:
            await c.rollback()
            raise
        finally:
            await c.close()

    async def update_job(self, job_id: str, status: str, message: str) -> None:
        c=await self.open()
        try:
            await c.execute('UPDATE triage_jobs SET status=?,message=?,updated_at=? WHERE id=?', (status,message[:500],utcnow(),job_id))
            await c.commit()
        finally:
            await c.close()

    async def job(self, job_id: str) -> dict | None:
        c=await self.open()
        try:
            cur=await c.execute('SELECT * FROM triage_jobs WHERE id=?', (job_id,))
            row=await cur.fetchone()
            return dict(row) if row else None
        finally:
            await c.close()
