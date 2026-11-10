"""Pure-code final authority. Model confidence is ignored."""
from __future__ import annotations
import copy
import json
import re
from dataclasses import dataclass
from .contracts import Edit, Solver, SolutionAudit
from .loader import question_body, raw_field, fingerprint
from .normalization import html_options, stem_only, plain_text
from .static_checks import inspect_question


@dataclass(frozen=True)
class SafetyDecision:
    safe: bool
    reasons: tuple[str, ...]
    patched: dict | None = None


def apply_patch(q: dict, edit: Edit, expected_hash: str) -> dict:
    if fingerprint(q) != expected_hash:
        raise ValueError("Question changed since triage; stale edit")
    raw = raw_field(q, edit.field)
    if raw.count(edit.find) != 1:
        raise ValueError("find must occur exactly once in the raw target field")
    if edit.find == edit.replace:
        raise ValueError("no-op replacement")
    clone = copy.deepcopy(q)
    changed = raw.replace(edit.find, edit.replace, 1)
    if edit.field == "questionType":
        # A full migration of nested source shape requires dedicated logic and faculty approval.
        raise ValueError("questionType edits need an explicit faculty-controlled migration")
    if edit.field == "answer":
        old_answer = question_body(q)["answer"]
        if isinstance(old_answer, str):
            question_body(clone)["answer"] = changed
        else:
            question_body(clone)["answer"] = json.loads(changed)
    else:
        question_body(clone)[edit.field] = changed
    return clone


def confidence_from_evidence(repair: str, findings: list, solver_a: Solver | None,
                             solver_b: Solver | None, audit: SolutionAudit | None,
                             lint_proof: bool = False, stored_answer=None) -> float:
    """Evidence-based policy score, not the model's subjective confidence.

    These weights are a conservative heuristic, NOT calibrated empirical probabilities.
    Validate/calibrate on faculty-labeled production data before deploying auto-writes.
    """
    codes = {getattr(f, "code", "") for f in findings}
    score = 0.47
    direct = {"noise": "noise", "exam_reference": "exam_tag", "markup_leak": "latex_leak",
              "option_repair": "blank_option", "solution_missing": "solution_empty", "answer_key": "invalid_mcq_answer"}
    if direct.get(repair) in codes:
        score += 0.26
    if lint_proof:
        score += 0.34
    if solver_a and solver_b and solver_a.answer is not None and solver_a.answer == solver_b.answer:
        score += 0.25
    if solver_a and stored_answer is not None and solver_a.answer is not None and solver_a.answer != stored_answer:
        score += 0.10 if repair == "answer_key" else 0.0
    if solver_a and audit and solver_a.answer is not None and str(solver_a.answer) == str(audit.final_answer):
        score += 0.14
    if repair in {"diagram", "identical_options", "wrong_chapter", "syllabus", "wrong_question", "unsound"}:
        score = min(score, 0.78)
    return round(min(score, 0.98), 2)


def safety_gate(q: dict, repair: str, edits: list[Edit], taxonomy: dict, expected_hash: str,
                findings: list, solver_a: Solver | None = None, solver_b: Solver | None = None,
                audit: SolutionAudit | None = None, student_comments: list[str] | None = None) -> SafetyDecision:
    reasons: list[str] = []
    config = taxonomy["repairs"].get(repair)
    if config is None:
        return SafetyDecision(False, ("unknown repair key",))
    if not config["auto"]:
        return SafetyDecision(False, ("taxonomy prohibits automatic editing",))
    if not edits:
        return SafetyDecision(False, ("no proposed edit",))
    if fingerprint(q) != expected_hash:
        return SafetyDecision(False, ("stale question version",))
    patched = copy.deepcopy(q)
    before = inspect_question(q)
    severe_before = {f.code for f in before if f.severity == "critical"}
    for edit in edits:
        if edit.field not in config["fields"]:
            reasons.append(f"field {edit.field} outside {repair} scope")
            continue
        if edit.find == edit.replace:
            reasons.append("no-op patch")
            continue
        if any((edit.find and edit.find in c) or (edit.replace and edit.replace in c) for c in (student_comments or []) if c.strip()):
            # This catches copying a complete hostile comment, but factual overlaps require manual scrutiny too.
            reasons.append("edit string appears in student comment")
            continue
        if repair == "spelling":
            if re.search(r"[\d<>\\&^=+*/{}\[\]$]", edit.find + edit.replace):
                reasons.append("spelling patch touches numeric/symbolic/markup token")
            if re.sub(r"[A-Za-z\s]", "", edit.find) != re.sub(r"[A-Za-z\s]", "", edit.replace):
                reasons.append("spelling patch changes non-letter content")
        if repair in ("noise", "exam_reference") and edit.replace != "":
            reasons.append("noise/reference patches must be deletion-only")
        if repair == "answer_form" and edit.find not in edit.replace:
            reasons.append("answer_form must be additive")
        if repair == "stem_data":
            before, after = edit.find, edit.replace
            start = 0
            while start < min(len(before), len(after)) and before[start] == after[start]:
                start += 1
            end = 0
            while end < min(len(before)-start, len(after)-start) and before[-1-end] == after[-1-end]:
                end += 1
            inserted = after[start:len(after)-end if end else len(after)]
            inserted_numbers = set(re.findall(r"\d+(?:\.\d+)?", inserted))
            solution_text = plain_text(q[q["questionType"]].get("solution", ""))
            solution_numbers = set(re.findall(r"\d+(?:\.\d+)?", solution_text))
            if not inserted_numbers or not inserted_numbers.issubset(solution_numbers):
                reasons.append("inserted stem value is not supported by numbers in stored solution")
        if repair in ("solution_fix", "solution_missing") and not audit:
            reasons.append("solution requires independent audit")
        if repair == "answer_key":
            if not solver_a or not solver_b or solver_a.answer != solver_b.answer or solver_a.answer is None:
                reasons.append("two independent solvers did not agree")
            if audit and audit.final_answer is not None and solver_a and str(audit.final_answer) != str(solver_a.answer) and not audit.wrong_steps:
                reasons.append("solution audit disagrees without identifying wrong steps")
        if reasons:
            continue
        def raw_stem(value: str) -> str:
            import re as _re
            hit = _re.search(r"\(A\)", value)
            return value[:hit.start()] if hit else value
        pre_stem = raw_stem(patched[patched["questionType"]].get("question", ""))
        pre_opts = html_options(patched[patched["questionType"]].get("question", ""))
        try:
            patched = apply_patch(patched, edit, fingerprint(patched))
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            reasons.append(str(exc))
            continue
        if repair == "option_repair":
            post_stem = raw_stem(patched[patched["questionType"]].get("question", ""))
            post_opts = html_options(patched[patched["questionType"]].get("question", ""))
            if pre_stem != post_stem:
                reasons.append("option repair changed stem")
            changed = [k for k in "ABCD" if post_opts.get(k) != pre_opts.get(k)]
            if len(changed) != 1 or not post_opts.get(changed[0]):
                reasons.append("option repair must fill exactly one option")
            if changed and post_opts.get(changed[0]) in [v for k, v in post_opts.items() if k != changed[0]]:
                reasons.append("option duplicates another answer")
        if repair == "answer_key":
            new_answer = patched[patched["questionType"]]["answer"]
            if patched["questionType"] == "scq" and (not isinstance(new_answer, str) or new_answer not in "ABCD"):
                reasons.append("SCQ key must name a real option")
            if patched["questionType"] == "mcq" and (not isinstance(new_answer, list) or not new_answer or any(x not in "ABCD" for x in new_answer)):
                reasons.append("MCQ key must be a list of single letters")
            if solver_a and new_answer != solver_a.answer:
                # Different solver output representation needs explicit review.
                reasons.append("new key differs from independent solver answer")
    after = inspect_question(patched)
    severe_after = {f.code for f in after if f.severity == "critical"}
    if severe_after - severe_before:
        reasons.append("patch introduced new critical static finding")
    if repair in ("solution_fix", "solution_missing"):
        value = patched[patched["questionType"]].get("answer")
        text = plain_text(patched[patched["questionType"]].get("solution", "")).strip()
        if not text or not re.search(r"(?<!\d)" + re.escape(str(value)) + r"(?:\s*(?:cm|mm|m|V|N|J|eV|s|seconds|ohm|Ω|%))?\s*[.。]?$", text, re.I):
            reasons.append("patched solution must end at the keyed answer")
    return SafetyDecision(not reasons, tuple(reasons), patched if not reasons else None)


def route_repair(repair: str, score: float, result: SafetyDecision, taxonomy: dict) -> str:
    if not taxonomy["repairs"][repair]["auto"] or not result.safe:
        return "faculty_review"
    threshold = 0.90 if repair == "answer_key" else 0.85
    return "auto_apply" if score >= threshold else "faculty_review"
