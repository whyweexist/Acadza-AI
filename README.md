# Acadza — Report → Fix

**Evidence-first question QA** for JEE/NEET. Groups multiple student reports into reviewable question cases, independently checks the science, proposes minimum edits, enforces taxonomy-based write restrictions, and gives faculty a fast, contextual review workspace.

> **Execution disclosure:** This codebase was generated at the user's request **without running application tests, type checks, a build, or a deployment**. The included `results.json` is a **manually inspected precomputed demo baseline**, not an output from actual LLM calls. The separate live orchestration is implemented but requires real model credentials and its outputs have not been verified. The project should not be treated as audited production software until the listed checks are executed and the findings are addressed.

## What is included

- 43 real-format question snapshots and 44 raw reports (39 question-level cases), plus closed taxonomy.
- `results.json`: one report-specific decision for each of the 44 input reports. Labels are a conservatively authored demonstration baseline, **not hidden-ground-truth scores**.
- `findings.json`: candidates from the four *unreported* question snapshots, kept separate from `results.json`.
- `services/triage`: Python FastAPI, SQLite-only persistence, async LLM expert orchestration, Pydantic discriminated unions, static prechecks, pure safety validation, optimistic review revisions and append-only audit events.
- `apps/web`: interactive Next.js/TypeScript faculty console, native MathML, searchable and sortable question-level queue, repair diffs, report-specific response previews, approval/edit/rejection, keyboard navigation, dark mode, audit timeline and responsive layout.
- Fully local data mode: if the backend is absent, Next.js serves **read-only** packaged sample data. It never fabricates review writes.

## Architecture

```text
source JSON -> SQLite fixtures ──> grouped cases ───────────> Faculty UI
                                     |                         |
                        no-LLM static checks                 review
                                     |                         |
                        ┌────────────┴────────────┐            |
                        |                         |            |
                 untrusted report track   report-blind track   |
                 claim extraction          solver A + solver B |
                                           solution audit     |
                                           lint + metadata    |
                        └────────────┬────────────┘            |
                                     v                         |
                               adjudicator                     |
                                     v                         |
                           deterministic safety gate          |
                                     v                         v
                             triage result <--------- revision-checked SQLite
                                     |               audit + patch approval only
                          reply preview per report
```

The UI's **Approve** action saves an auditable faculty decision and an approved *patch preview*. It does **not** mutate the 800k-question production bank. External publication requires a separate, authenticated, transactional adapter with question-version rechecking.

## Requirements

- Python 3.12+
- Node.js 20.9+ (Node 22 recommended)
- SQLite bundled with Python; **no PostgreSQL, Redis, Docker, or cloud account is required** for local operation

## 1. Start the SQLite API

From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate              # Windows: .venv\Scripts\activate
python -m pip install -r services/triage/requirements.txt
cp .env.example .env                   # set a long ADMIN_REVIEW_TOKEN
cd services/triage
uvicorn app.main:app --reload --port 8000
```

The API creates its SQLite database on first start and imports source questions, reports and the provided precomputed decisions idempotently. SQLite has `journal_mode=WAL`, `busy_timeout` and foreign-key checks enabled. The SQLite file defaults to `data/acadza.sqlite3` relative to the path used in `SQLITE_PATH`; set an absolute filesystem path if preferred. **Do not commit SQLite database files or secrets.**

## 2. Start the faculty console

In another terminal, from the repository root:

```bash
cd apps/web
cp .env.example .env.local
# Set API_BASE_URL=http://127.0.0.1:8000 and REVIEW_TOKEN to the API token.
npm install
npm run dev
```

Visit **http://localhost:3000**.

When the API is unavailable, the console automatically loads packaged read-only demo snapshots. Search, filters, question rendering, case navigation, evidence and diffs still work. Review buttons are disabled. With the backend connected and matching tokens, approve/edit/reject actions persist to SQLite.

`API_BASE_URL` and `REVIEW_TOKEN` are **server-side Next.js environment variables**; do not expose them via `NEXT_PUBLIC_` variables.

## 3. Live LLM orchestration (optional; not exercised in this handoff)

From the root after configuring `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `LLM_CHEAP_MODEL` and `LLM_STRONG_MODEL`:

```bash
python services/triage/scripts/triage.py
```

Per question, it performs static prechecks, then two independent async tracks (`asyncio.gather`, bounded by a semaphore): structured claims extracted from untrusted reports and report-blind solution audits/solvers. The adjudicator proposes fixes, pure-code rules determine route and safety, and a reply is generated **per report**. A failed expert validation gets one retry, then the case is flagged `failed_review` in SQLite without falsely manufacturing a confirmed defect. If any question fails, the script preserves the existing `results.json` and writes failure details separately.

**Important:** Running live inference without supervision can consume model credits and is not proof that the model's mathematics is accurate. Human-evaluate the output and run safety tests before considering auto-writes.

## 4. Regenerate precomputed sample snapshots

```bash
python scripts/make_precomputed.py  # manually curated baseline, NOT model inference
python scripts/build_demo.py        # packages demo-index, demo-cases, findings
```

## 5. Validation and tests (included, intentionally NOT executed)

```bash
python scripts/validate_results.py
cd services/triage && pytest -q
cd ../../apps/web && npm run typecheck && npm run build
```

These commands are provided for your execution. **They have not been run for this deliverable, as requested.** A pass/fail claim would be dishonest.

## API

| Route | Function |
|---|---|
| `GET /api/health` | Health/status |
| `GET /api/cases?search=&status=&subject=&route=&offset=&limit=` | Indexed group summaries and server-side pagination |
| `GET /api/cases/{id}` | Canonical question snapshot, grouped reports, decisions, diff inputs, audit |
| `GET /api/cases/{id}/reports` | All report summaries for a question |
| `GET /api/cases/{id}/history` | Case audit history |
| `POST /api/cases/{id}/actions` | Authenticated approve/edit/reject with hash + revision + idempotency key |
| `GET /api/audit` | Audit timeline |
| `GET /api/metrics` | Sample-case counters |

Mutation endpoint requires `X-Review-Token`, enforced by the Python API. The Next.js route handler adds it **only on the server**. Treat this shared token as a *demo credential*, not a substitute for production SSO and per-person authentication.

## Review safeguards

1. `_id` is canonical. `qid` is untrusted for identity and may repeat.
2. Question body lives under `question[questionType]`.
3. Non-defect verdicts have `repair=null`, `edit=null`, `route=no_change`.
4. Every defect repair must exist in the closed `taxonomy.json`.
5. `edit={field,find,replace}` must match exactly once in the raw field. Array answer values use their JSON serialization for exact matching; primary edit exported in `results.json`.
6. Only taxonomy-allowed fields may change. `auto:false` repairs cannot produce an automatic edit.
7. Spelling cannot alter symbols/digits/markup; noise/exam reference is deletion-only; answer form is additive; option edits must retain raw stem and distinct options; stem numbers must be found in the stored solution; answer key requires two independent matching solvers and valid answer shape.
8. The question snapshot hash and case revision are checked before *every review action*.
9. No student comment can become executable instructions; raw comments are never shown to solvers.
10. Auto-eligible is **not** production-applied, and the student reply preview is **not** sent.

### Important limits

- SQLite is an excellent single-instance fit, but it is not a distributed multi-writer database. Host API and SQLite on one persistent volume; avoid ephemeral multi-instance serverless backends for authenticated writes. Back up database and its WAL consistently.
- Token authentication is suitable only for a controlled demo. Before broader deployment, add institution SSO/RBAC, student privacy reviews, per-user audit identity, backup/restore drills, hardening and rate limits at the edge.
- The confidence heuristic is not empirically calibrated. A numeric threshold alone does not prove safe automation; conduct faculty-labeled evaluation and calibrate it first.
- HTML extracted from production data can be malformed. All renderer input must be sanitized; the UI uses DOMPurify before HTML insertion. Browser MathML support differs by environment.
- `results.json` is a handwritten **precomputed** baseline. No LLM was invoked to produce it; no ground-truth accuracy is claimed.
- The assignment's live URL, GitHub publication and screen recording require action from an authenticated user and are not fabricated here.

See `docs/architecture.md`, `docs/safety.md`, `docs/deployment.md`, `PRODUCT.md` and `PROMPTS.md`.

## Optional containers (not built or run in this handoff)

A two-service `docker-compose.yml` is provided: the Python API and Next.js web app, backed by a named **SQLite volume**. Set `ADMIN_REVIEW_TOKEN` in a local `.env`, then run `docker compose up --build` if you choose. A single API worker is configured to respect SQLite's single-writer model. The CI workflow is manually invoked (`workflow_dispatch`) and **was not executed**.
