# Engineering architecture — SQLite, bounded async experts and focused faculty UX

## Bounded contexts

- `core/loader.py`: canonical `_id`, nested per-type body, fingerprints, raw field serialization.
- `core/normalization.py`: tolerant HTML/MathML extraction and sanitized display content, with raw original retained.
- `core/static_checks.py`: deterministic signals (not conclusive verdicts).
- `agents/prompts.py`: versioned, verbatim AI expert instructions.
- `agents/client.py`: bounded async provider requests, JSON/Pydantic checking, one retry, SQLite cache.
- `core/pipeline.py`: per-question analysis, two independent tracks, per-report fanout and quarantined failures.
- `core/safety.py`: pure allowed-fields, unique-match, semantic invariants and version-aware patch policy.
- `core/database.py`: SQLite WAL, short explicit write transactions, idempotency, immutable source and audit history.
- `main.py`: thin FastAPI HTTP boundary.
- `apps/web/components/queue/CaseCard.tsx`: queue unit.
- `apps/web/components/cases/*`: evidence, question/diff/report/audit tabs and reply previews.
- `apps/web/components/review/ReviewDialog.tsx`: review editor and confirm flow.
- `apps/web/components/Workspace.tsx`: workspace coordination, key bindings, routes, search/filter state.
- `apps/web/app/api/[...path]/route.ts`: server-only authenticated API proxy, read-only offline data fallback.

## Domain model

`Question(_id, qid?, questionType, question[questionType], updatedAt)`. `qid` is **not** a unique key.

`Report(reportId, questionId, studentId, source, reportedAt, comment)`. Multiple reports per question.

`Case(question_id, triage_hash, triage_status, status, revision, meta_json)`. One faculty case per question, with a hash of the exact snapshot analyzed.

`TriageResult` is a Pydantic discriminated union by `verdict`. A defect must specify one real taxonomy repair; non-defects must specify no repair/edit and the `no_change` route. Internally a decision supports a list of edits, while the assignment export exposes only its primary `{field,find,replace}` edit. An answer that's a list uses serialized JSON for exact substring matching.

`AuditEvent(question_id, actor, action, before, after, note, timestamp, idempotency_key)`. Append-only; no automatic production content mutation.

## Offline and live paths

Precomputed: manually reviewed source examples -> `results.json` -> SQLite seed + `apps/web/public/demo-*.json` -> UI. No LLM invocation is claimed.

Live: per-question `static_checks` then parallel `claims` and `experts` via `asyncio.gather` with `AgentClient` semaphore. Solver A and solver B receive *only* stem, options, subject and type, never student comments, stored solution or stored key. `solution_audit` receives question plus solution but not key. `claim` receives untrusted report. `adjudicate` gets structured claims and experts, then `safety_gate` decides. `reply` is per report, no sending.

Any invalid/unavailable model response gets at most one retry; persistent `failed_review` cases signal review without a fabricated factual result.

## SQLite transaction model

- SQLite `WAL`, foreign keys and `busy_timeout` enabled on connections.
- Re-ingestion uses `INSERT OR IGNORE` to preserve original snapshots and reviewed cases.
- Review transactions use `BEGIN IMMEDIATE`, check `revision` and snapshot `hash`, create one `audit_events` row and update case revision atomically.
- Idempotency key is unique. Retried mutations resolve to an existing audit event rather than duplicate decisions.
- The app has no endpoint for writing the production question bank.
- Read queue grouping, filtering and pagination are pushed into SQLite SQL with explicit indexes, not a browser-wide question dump.

## Priority model

`severity(52 defect / 12 other) + 30 grading-risk / 21 blocked-option-risk + 7 × min(reports,10) + 0.4 × min(days-old,30) + 8 if faculty review`. This is an explainable sample heuristic, not a learned quality score. Real student exposure and attempt counts are not supplied and must not be fabricated.

## Failure policy

- Missing API credentials -> live triage refuses to run and retains the precomputed results.
- Invalid expert JSON after retry -> `failed_review` on case, no invented auto fix.
- Field-scope violation -> review only.
- Stale question version or case revision -> HTTP 409, refresh before review.
- Auth missing or wrong -> HTTP 403.
- Backend unavailable -> frontend read-only fixture mode, review actions disabled.
- Missing or unsupported authored content -> no invented diagram or option text.

## LLM provider adapters (Gemini, OpenRouter and OpenAI)

`app/core/providers.py` resolves one server-side provider snapshot from environment settings or an authenticated, **memory-only** admin override. All inference calls are routed through the same `AgentClient` JSON-schema/Pydantic validator. The provider snapshot is frozen when a triage job starts, avoiding mixed-model decisions if an admin changes the provider during a run. Model and provider enter the cache fingerprint.

The faculty UI's **AI providers** module uses `x-review-token` for authorization through an explicit Next.js proxy; the proxy never injects its ambient review token into LLM settings requests. No credential is returned from GET /api/llm/config or stored in SQLite. The GUI's key override is in-process and does not affect the standalone CLI, which reads `LLM_PROVIDER` and the chosen provider's key from `.env`.

Single-case `POST /api/llm/jobs` background jobs are intentionally scoped to the local demo. Jobs are registered in SQLite, marked interrupted on server restart and never result in production content mutation. For production concurrency, replace the FastAPI in-process task launch with a durable worker consuming the SQLite queue; do not deploy multiple API worker processes with transient keys.
