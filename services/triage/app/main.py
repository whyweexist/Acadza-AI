from __future__ import annotations
import logging
import secrets
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from .core.settings import settings
from .core.database import Database, Conflict, InvalidReview
from .core.contracts import ReviewAction

logging.basicConfig(level=logging.INFO)
db = Database()

@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.seed()
    yield

app = FastAPI(title="Acadza Faculty Review API", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[x.strip() for x in settings().cors_origins.split(",") if x.strip()],
                   allow_methods=["GET","POST"], allow_headers=["Content-Type","X-Review-Token"], allow_credentials=False)

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
