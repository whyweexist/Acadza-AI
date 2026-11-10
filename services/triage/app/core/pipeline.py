"""Parallel untrusted claim track and report-blind independent verification track."""
from __future__ import annotations
import asyncio
import json
import logging
from collections import defaultdict
from pydantic import TypeAdapter
from ..agents.client import AgentClient, AgentFailure
from ..agents.prompts import VERSION
from .contracts import (Claim, Solver, SolutionAudit, TextLint, MetadataAudit,
                        Adjudication, Reply, DefectResult, NonDefectResult, Edit,
                        TriageResult)
from .loader import fingerprint, known_chapters, read_json, raw_field
from .normalization import normalized_question
from .static_checks import inspect_question
from .safety import safety_gate, confidence_from_evidence, route_repair

logger = logging.getLogger(__name__)


class RequiresFaculty(Exception):
    """Pipeline failure is quarantined and NEVER passed off as a factual defect verdict."""
    def __init__(self, question_id: str, reason: str):
        self.question_id = question_id
        super().__init__(reason)


async def analyze_question(question: dict, reports: list[dict], client: AgentClient,
                           chapters: dict[str, list[str]], taxonomy: dict) -> tuple[list[dict], dict]:
    qhash = fingerprint(question)
    norm = normalized_question(question)
    static = inspect_question(question, reports)
    static_payload = [f.model_dump() for f in static]
    verify_payload = {"questionType": norm["questionType"], "subject": norm["subject"], "chapter": norm["chapter"], "stem": norm["question_text"], "options": norm["options"]}

    # The full student comments are visible ONLY to claim extractor and reply writer.
    # Solver A/B do not see stored answer, solution or ANY student comment.
    claims_task = asyncio.gather(*(client.call("claim", {"untrusted_student_comment": r.get("comment", "")}, Claim) for r in reports))
    experts_task = asyncio.gather(
        client.call("solver_a", verify_payload, Solver, strong=True),
        client.call("solver_b", verify_payload, Solver, strong=True),
        client.call("solution_audit", {"questionType": norm["questionType"], "subject": norm["subject"], "stem": norm["question_text"], "options": norm["options"], "solution": norm["solution_text"]}, SolutionAudit, strong=True),
        client.call("text_lint", {"question": norm["question_html"], "solution": norm["solution_html"]}, TextLint),
        client.call("metadata", {"subject": norm["subject"], "chapter": norm["chapter"], "stem": norm["question_text"], "available_chapters": chapters}, MetadataAudit),
    )
    try:
        (claims, experts) = await asyncio.gather(claims_task, experts_task)
        sa, sb, audit, lint, metadata = experts
        adjud = await client.call("adjudicate", {
            "questionType": norm["questionType"], "answer": norm["answer"],
            "question_html": norm["question_html"], "solution_html": norm["solution_html"],
            "taxonomy": taxonomy, "static_findings": static_payload,
            "structured_claims": [c.model_dump() for c in claims],
            "solver_a": sa.model_dump(), "solver_b": sb.model_dump(),
            "solution_audit": audit.model_dump(), "text_lint": lint.model_dump(), "metadata": metadata.model_dump(),
        }, Adjudication, strong=True)
    except AgentFailure as exc:
        raise RequiresFaculty(question["_id"], str(exc)) from exc
    if adjud.verdict not in taxonomy["verdicts"]:
        raise RequiresFaculty(question["_id"], "invalid verdict from adjudicator")
    if adjud.repair is not None and adjud.repair not in taxonomy["repairs"]:
        raise RequiresFaculty(question["_id"], "unknown repair from adjudicator")
    edits = adjud.edits
    if adjud.verdict == "defect":
        checked = safety_gate(question, adjud.repair, edits, taxonomy, qhash, static,
                              sa, sb, audit, [r.get("comment", "") for r in reports])
        score = confidence_from_evidence(adjud.repair, static, sa, sb, audit,
                 lint_proof=any(c.repair == adjud.repair and c.edit in edits for c in lint.candidates),
                 stored_answer=norm["answer"])
        route = route_repair(adjud.repair, score, checked, taxonomy)
        reasons = list(checked.reasons)
        if reasons:
            logger.info("safety_blocked question=%s reasons=%s", question["_id"], reasons)
    else:
        checked = None
        score = min(0.95, 0.45 + (0.15 if sa.answer == sb.answer else 0) + (0.18 if sa.answer == norm["answer"] else 0) + (0.08 if audit.final_answer == norm["answer"] else 0))
        route = "no_change"
        reasons = []
    # Per-report replies and decisions remain distinct even if expensive verification was reused.
    outputs = []
    for report, claim in zip(reports, claims):
        try:
            reply = await client.call("reply", {
                "untrusted_student_comment": report.get("comment", ""),
                "claim": claim.model_dump(), "verdict": adjud.verdict, "evidence": adjud.evidence,
                "route": route, "applied": False, "verified_answer": sa.answer if sa.answer == sb.answer else None,
            }, Reply)
            text = reply.text
        except AgentFailure:
            text = "Thank you for reporting this. We have reviewed the concern and will only change the question once the correction is verified."
        base = {"reportId": report["reportId"], "questionId": question["_id"],
                "confidence": score, "evidence": adjud.evidence, "student_reply": text}
        if adjud.verdict == "defect":
            value = DefectResult(**base, verdict="defect", repair=adjud.repair,
                                 edit=edits[0] if edits else None, route=route)
        else:
            value = NonDefectResult(**base, verdict=adjud.verdict)
        outputs.append(value.model_dump())
    metadata_result = {"question_hash": qhash, "all_edits": [e.model_dump() for e in edits],
                       "static_findings": static_payload, "safety_reasons": reasons,
                       "verification": {"solver_a": sa.model_dump(), "solver_b": sb.model_dump(), "solution_audit": audit.model_dump(),
                                        "text_lint": lint.model_dump(), "metadata": metadata.model_dump()},
                       "prompt_version": VERSION, "triage_status": "completed"}
    return outputs, metadata_result


async def run_all(client: AgentClient, db=None) -> tuple[list[dict], list[dict]]:
    questions = read_json("questions.json")
    reports = read_json("reports.json")
    taxonomy = read_json("taxonomy.json")
    by_question: dict[str, list[dict]] = defaultdict(list)
    for r in reports:
        by_question[r["questionId"]].append(r)
    qmap = {q["_id"]: q for q in questions}
    chapters = known_chapters(questions)
    result_rows: list[dict] = []
    failures: list[dict] = []
    async def one(qid: str, rs: list[dict]):
        if qid not in qmap:
            failures.append({"questionId": qid, "reason": "missing question", "reportIds": [r["reportId"] for r in rs]})
            if db: await db.flag_failure(qid, "missing question")
            return
        try:
            rows, meta = await analyze_question(qmap[qid], rs, client, chapters, taxonomy)
            result_rows.extend(rows)
            if db: await db.store_results(qid, rows, meta)
        except RequiresFaculty as exc:
            failures.append({"questionId": qid, "reason": str(exc), "reportIds": [r["reportId"] for r in rs]})
            if db: await db.flag_failure(qid, str(exc))
    # Batch question jobs: do not create an unbounded number of pending asyncio tasks.
    # Individual LLM calls are additionally limited by AgentClient's semaphore.
    pairs = list(by_question.items())
    window = max(2, client.config.llm_concurrency)
    for start in range(0, len(pairs), window):
        await asyncio.gather(*(one(qid, rs) for qid, rs in pairs[start:start + window]))
    result_rows.sort(key=lambda r: r["reportId"])
    return result_rows, failures
