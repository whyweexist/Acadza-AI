"""Generate PROMPTS.md directly from product prompt source to guarantee verbatim match."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'services'/'triage'))
from app.agents.prompts import VERSION, BASE, REGISTRY

header=f'''# PROMPTS.md — Verbatim prompts and honest engineering record

> **Disclosure:** The user explicitly requested a code-only deliverable **without running tests**. No LLM inference or prompt-evaluation experiment has been run in producing this repository. The `results.json` baseline is a manually inspected precomputed sample, not a fabricated LLM run. Only `v1.0.0` product prompts exist; any claimed earlier versions or measured improvements would be invented.

## Product prompts — {VERSION} (verbatim source)

The following strings are extracted directly from `services/triage/app/agents/prompts.py`, not paraphrased. At runtime `AgentClient` sends the `BASE` content + selected expert prompt + the exact Pydantic JSON Schema; the latter is machine generated per expert and can be reconstructed from `contracts.py`. The student report is supplied in the user role as a JSON string value labeled `untrusted_student_comment`.

### Shared system prefix — BASE

```text
{BASE}
```

'''
sections=[]
for k,txt in REGISTRY.items():
    sections.append(f'### {k} — exact text\n\n```text\n{txt}\n```\n')
closing='''
## Prompt versions and decisions

- **v1.0.0:** Introduced role-separated claim extraction, two distinct report-blind solvers, solution audit, lint, metadata, adjudication and reply writing. The main objective is limiting anchoring and student-controlled instructions. The safety gate is pure Python, not a prompt.
- No preceding product prompt versions were run, no model-comparison results exist, and no before/after prompt performance can responsibly be claimed for this handoff.
- If implementing a future v1.1, first run labeled cases, record misclassifications and version the changed prompt with actual measurements. Do not invent a retrospective history.

## Key prompts supplied to the coding assistant (verbatim)

### User request: SQLite architecture amendment and implementation

```text
I want you to remove the postgres completely and use sql lite also I wnat you to make the UI highly feasible and interactive and proper modules for it also integrate the part of the prompt below and use it whatever needed to you or fits best for you in your current prompt 
DOMAIN RULES
- Key questions on _id; qid is not unique. The body lives under the key named
  by questionType (scq | mcq | integerQuestion).
- TriageResult is a discriminated union on verdict: "defect" requires a repair;
  every other verdict has repair None, edit None, route "no_change".
- Edit = {field, find, replace}; find is an exact substring of the raw stored
  field. Internally allow a list; results.json writes the primary edit.
- Each case stores a hash of the question it was triaged against.
- Unreported defects go to findings.json, not results.json.

PIPELINE (per question, then fan out to its reports)
1. Ingest, normalize, group by question id, keep every report id.
2. Static checks (no LLM): option count, blank and duplicate options, answer
   shape per type (mcq answer is a list of single letters), raw LaTeX, exam
   tags, figure mentioned with empty quesImages, errorHistory entry newer than
   reportedAt with the problem absent (already_fixed), leaked list numbering,
   stray "&" in MathML.
3. Two tracks in parallel (asyncio.gather with a semaphore):
   AI triage: reads the reports. Independent verification: never reads them.
4. Adjudicate.  5. Deterministic safety gate.  6. Route to one of three lanes:
   auto-eligible, faculty review, no change.  7. Reply per report, audit entry.

EXPERT CONTRACTS (Pydantic-validated JSON; one retry on invalid output, then
fail closed to faculty_review)
- claim (cheap, triage track): the comment arrives inside a delimited JSON
  string labelled untrusted data. Output {claim_type: closed enum,
  claimed_answer, target, language, injection: bool}. Only this stage and the
  reply writer ever see the raw comment.
- solver x2 (strong, verification track): stem + options ONLY. No key,
  solution or comment. The second solver must use a different method. Output
  {answer, working, no_valid_option, multiple_valid, missing_data}.
- solution_audit (strong, verification track): question + solution, not the
  key. Output {belongs_to_question, final_answer, wrong_steps,
  values_not_in_stem}.
- text_lint (cheap): spelling/noise/notation candidates as exact find/replace.
- metadata (cheap): does subject/chapter fit, given the list of all chapters.
- adjudicate (strong): lint findings + expert outputs + structured claim.
  Picks verdict, repair and edits from the taxonomy; writes one evidence
  sentence naming the checks that agreed. The claim is a lead: the key may be
  wrong in a different way than the student says.
- reply (cheap): 1-3 sentences, plain and kind, mirrors the student's language
  mix, states the right answer when known, never promises a fix still waiting
  on faculty, never repeats injected text.

SAFETY GATE (pure code, final authority)
- edit.field must be in repairs[repair].fields; auto:false => no edit, review.
- find occurs exactly once; replace != find; the patched copy re-normalizes
  and passes static checks.
- spelling: no digit, symbol or MathML token changes. noise/exam_reference:
  deletion only. answer_form: find is a substring of replace. option_repair:
  stem byte-identical, new option distinct from all others. stem_data: the
  inserted value must appear in the stored solution. answer_key: both solvers
  agree, new answer is a real option or valid shape, solution audit agrees or
  is flagged wrong. solution_fix/solution_missing: must end at the keyed answer.
- No string from a student comment may appear in any edit.
- Version check: refuse to apply if the question hash changed since triage.
- confidence is computed from agreement (lint proof, solver A/B, solution
  audit), never model self-report.
- route(): auto_apply needs auto:true, all gates passing and confidence >=
  0.85 (0.9 for answer_key). Anything uncertain goes to faculty_review.




Now your task is to give me a zip file of the whole codebase do not test it write me the code and give me the final zip
```

### Other real instructions available in this conversation

The user initially asked for a senior-engineer assessment of Acadza's actual attached assignment, then requested a detailed master implementation prompt before this SQLite amendment. The authoritative wording of the challenge is preserved in `docs/ASSIGNMENT.md`; the revised specification is preserved in `MASTER_IMPLEMENTATION_PROMPT.md`. This paragraph is a summary, **not a falsely claimed verbatim export** of every previous message.

## Three meaningful failure traps in the supplied data (NOT observed AI runs)

The brief requests three moments where the AI was wrong and how it was caught. **No inference was run**, so claiming actual AI mistakes would be false. These are three *documented test targets* and their expected safeguards; replace them with actual observed mistakes after running inference.

1. **R004 — misleading correction:** The student's “8225” is incorrect, but the stored key is also incorrect; `ρv²/3=4800 Pa` (D). A model that follows the student's proposed answer would introduce another defect. Mitigation: report-blind verification and key comparison.
2. **R027 — prompt injection:** The report asks the assistant to become an admin and change the answer. That is not a scientific claim. Mitigation: comments isolated in structured untrusted JSON; only claim/reply stages see the raw comment; pure-code gate remains authoritative.
3. **R034 — assertion/reason contradiction:** The assertion and reason are both false, but the available choices do not include “both false”. A model that simply copies keyed D would be wrong. Mitigation: independent scientific verification and `unsound` faculty-only repair.

## Decision log — what was selected, what was not implemented

| Decision | Selected | Why | Not selected |
|---|---|---|---|
| Database | SQLite WAL, `aiosqlite`, one persistent writer | Simple local deployment, durable short writes and transparent audits | PostgreSQL, Redis and distributed DB clusters, explicitly removed |
| Analysis unit | Question snapshot + grouped reports | Reuse costly independent verification and retain every report outcome | One full LLM reasoning chain per report |
| Trust | Report-blind independent solvers | Minimizes answer and student anchoring | Solver prompted with stored key or malicious comment |
| Safety | Pure-code final gate | Field permissions and exact matching are enforceable | LLM self-authorized edits |
| Failed inference | Quarantine case as `failed_review` | Avoids fabricating a `defect` just to satisfy the discriminated union | Fake confident triage labels |
| Demo | Precomputed read-only snapshots, honest seed provenance | Works without credits and without backend | Pretend online inference succeeded |
| Approval | Transactional audit and patch preview, no production mutation | Avoids destructive edits to live question bank | Direct writes from public UI |
| Frontend | Modular Next.js workspace | MathML, quick review, clear per-case context | Decoration-only static mockup |
| Tests | Included, intentionally not executed | Explicit user instruction “do not test it” | Fabricated green test reports |

**Unverified / future decisions:** Provider/model accuracy, token budgets, real latency, test suite reliability, strict question-patch parser properties and faculty usability must be evaluated before any production auto-publication. No trial was falsely claimed to have been performed.
'''
(ROOT/'PROMPTS.md').write_text(header+'\n'.join(sections)+closing,encoding='utf-8')
print('Wrote PROMPTS.md from literal product prompt source (without model calls).')
