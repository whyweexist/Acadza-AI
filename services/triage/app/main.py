from __future__ import annotations
import logging
import secrets
import asyncio
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from .core.settings import settings
from .core.database import Database, Conflict, InvalidReview
from .core.contracts import ReviewAction
from .core.providers import ProviderUpdate, current_provider, choose_provider, clear_provider_override, check_provider_credentials
from .core.loader import read_json
from .core.pipeline import analyze_question
from .core.loader import known_chapters
from .agents.client import AgentClient

logging.basicConfig(level=logging.INFO)
db = Database()
_running_tasks: dict[str, asyncio.Task] = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.seed()
    await db.fail_interrupted_jobs()
    yield

app = FastAPI(title="Acadza Faculty Review API", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[x.strip() for x in settings().cors_origins.split(",") if x.strip()],
                   allow_methods=["GET","POST","PUT","DELETE"], allow_headers=["Content-Type","X-Review-Token"], allow_credentials=False)

async def require_reviewer(x_review_token: str | None=Header(default=None)) -> None:
    secret=settings().admin_review_token
    if not secret or not x_review_token or not secrets.compare_digest(x_review_token,secret):
        raise HTTPException(403,"Faculty review authentication is not configured or invalid")

@app.get("/api/health")
async def health():
    return {"ok":True,"storage":"sqlite","demo_seed":True,"writes_require_auth":True}

@app.get("/api/cases")
async def cases(search:str="",status:str="all",subject:str="all",route:str="all",offset:int=Query(0,ge=0),limit:int=Query(100,ge=1,le=250)):
    return await db.list_cases(search[:200],status,subject,route,offset,limit)

@app.get("/api/cases/{question_id}")
async def case(question_id:str):
    value=await db.get_case(question_id)
    if not value:raise HTTPException(404,"Case not found")
    return value

@app.get("/api/cases/{question_id}/reports")
async def case_reports(question_id:str):
    value=await db.get_case(question_id)
    if not value:raise HTTPException(404,"Case not found")
    return value["reports"]

@app.get("/api/cases/{question_id}/history")
async def case_history(question_id:str):
    value=await db.get_case(question_id)
    if not value:raise HTTPException(404,"Case not found")
    return value["audit"]

@app.post("/api/cases/{question_id}/actions",dependencies=[Depends(require_reviewer)])
async def review_action(question_id:str,payload:ReviewAction):
    try:return await db.act(question_id,payload)
    except Conflict as exc:raise HTTPException(409,str(exc)) from exc
    except InvalidReview as exc:raise HTTPException(422,str(exc)) from exc

@app.get("/api/audit")
async def audit(limit:int=Query(100,ge=1,le=300)):
    return await db.audit(limit)

@app.get("/api/metrics")
async def metrics():
    data=await db.list_cases(limit=250)
    return {"cases":data["total"],**data["counts"],"note":"Current imported sample only; not production-wide metrics"}


# All provider configuration operations require the *user-supplied* faculty admin token.
# The Next.js proxy never automatically inserts its server REVIEW_TOKEN for these routes.
@app.get("/api/llm/config", dependencies=[Depends(require_reviewer)])
async def llm_config():
    return current_provider().public()


@app.put("/api/llm/config", dependencies=[Depends(require_reviewer)])
async def llm_config_update(payload: ProviderUpdate):
    try:
        return choose_provider(payload)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.delete("/api/llm/config", dependencies=[Depends(require_reviewer)])
async def llm_config_reset():
    return clear_provider_override()


@app.post("/api/llm/test", dependencies=[Depends(require_reviewer)])
async def llm_test():
    return await check_provider_credentials()


class TriageJobRequest(BaseModel):
    question_id: str = Field(min_length=24, max_length=24, pattern=r"^[0-9a-fA-F]{24}$")


async def execute_triage(job_id: str, question_id: str, client: AgentClient):
    """Async single-process demo job. Never changes production question content."""
    try:
        await db.update_job(job_id, 'running', 'Independent solvers and report triage running')
        questions = read_json('questions.json')
        question = next((q for q in questions if q['_id']==question_id), None)
        reports = [r for r in read_json('reports.json') if r['questionId']==question_id]
        if question is None or not reports:
            raise ValueError('Source snapshot or reports missing')
        rows, meta = await analyze_question(question, reports, client, known_chapters(questions), read_json('taxonomy.json'))
        meta['execution_id'] = job_id
        meta['provider'] = client.provider.provider
        meta['models'] = {'cheap':client.provider.cheap_model,'strong':client.provider.strong_model}
        meta['model_usage'] = client.metrics
        await db.store_results(question_id, rows, meta)
        await db.update_job(job_id, 'completed', f'{len(rows)} reports independently triaged; decisions recorded in SQLite')
    except Exception as exc:
        logging.exception('Live verification failed: case=%s',question_id)
        # Fail closed; keep prior demo decisions but mark the case for faculty.
        await db.flag_failure(question_id, 'Live verification failed. See backend logs; review needed.')
        await db.update_job(job_id, 'failed', f'Checks could not finish safely ({type(exc).__name__}). Case flagged for faculty review.')


@app.post('/api/llm/jobs', dependencies=[Depends(require_reviewer)], status_code=202)
async def start_triage_job(payload: TriageJobRequest):
    provider=current_provider()
    if not provider.api_key:
        raise HTTPException(422, 'No model API key configured. Add one under AI providers or set .env variables.')
    try:
        job=await db.queue_triage(payload.question_id, provider.provider)
    except Conflict as exc:
        raise HTTPException(409,str(exc)) from exc
    except InvalidReview as exc:
        raise HTTPException(404,str(exc)) from exc
    if job['status']=='queued' and job['message']=='Waiting for verification worker':
        # Do not schedule a second worker for the same existing job.
        # create_task is not durable across process restarts; see README.
        if job['id'] not in _running_tasks or _running_tasks[job['id']].done():
            task=asyncio.create_task(execute_triage(job['id'], payload.question_id, AgentClient(db,provider)))
            _running_tasks[job['id']] = task
            task.add_done_callback(lambda _finished, jid=job['id']: _running_tasks.pop(jid, None))
    return job


@app.get('/api/llm/jobs/{job_id}', dependencies=[Depends(require_reviewer)])
async def triage_job_status(job_id: uuid.UUID):
    job=await db.job(str(job_id))
    if not job:
        raise HTTPException(404, 'Verification job not found')
    return job
