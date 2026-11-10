from __future__ import annotations
import re
from datetime import datetime, timezone
from .contracts import StaticFinding
from .loader import question_body
from .normalization import html_options, plain_text


def _f(code: str, evidence: str, repair: str | None = None, severity: str = "warning") -> StaticFinding:
    return StaticFinding(code=code, evidence=evidence, suggested_repair=repair, severity=severity)


def inspect_question(question: dict, reports: list[dict] | None = None) -> list[StaticFinding]:
    """Signals, not verdicts. A broken HTML parser must not manufacture high certainty."""
    reports = reports or []
    body = question_body(question)
    raw = body.get("question", "") or ""
    solution = body.get("solution", "") or ""
    findings = []
    opts = html_options(raw)
    qt = question["questionType"]
    if qt in ("scq", "mcq"):
        for letter in "ABCD":
            if letter not in opts:
                findings.append(_f("missing_option", f"Option {letter} label absent in parsed question", "option_repair"))
            elif not opts[letter]:
                findings.append(_f("blank_option", f"Option {letter} has no parsed content", "option_repair", "critical"))
        normalized = {k: re.sub(r"\s+", "", v).casefold() for k, v in opts.items() if v}
        for a in normalized:
            for b in normalized:
                if a < b and normalized[a] == normalized[b]:
                    findings.append(_f("duplicate_options", f"Options {a} and {b} have identical extracted text", "identical_options"))
    answer = body.get("answer")
    if qt == "scq" and (not isinstance(answer, str) or answer not in "ABCD" or len(answer) != 1):
        findings.append(_f("invalid_scq_answer", "SCQ key must be one letter A-D", "answer_key", "critical"))
    if qt == "mcq" and (not isinstance(answer, list) or not answer or any(not isinstance(v, str) or v not in "ABCD" or len(v) != 1 for v in answer)):
        findings.append(_f("invalid_mcq_answer", "MCQ key must be a list of single A-D letters", "answer_key", "critical"))
    if qt == "integerQuestion" and (not isinstance(answer, (int, str)) or not str(answer).lstrip("+-").isdigit()):
        findings.append(_f("invalid_integer_answer", "Integer key is not an integer-like value", "answer_key"))
    if re.search(r"\\(?:frac|sqrt|begin|end)\b", raw):
        findings.append(_f("latex_leak", "Raw LaTeX command appears in question HTML", "markup_leak"))
    if re.search(r"\((?:NEET|JEE(?:\s+Main|\s+Advanced)?)\s+20\d{2}\)", plain_text(raw), re.I):
        findings.append(_f("exam_tag", "Exam-year reference embedded in question", "exam_reference", "info"))
    if re.search(r"\b(?:given\s+in\s+(?:the\s+)?figure|as\s+shown|in\s+the\s+figure|figure\s+below)\b", plain_text(raw), re.I) and not body.get("quesImages"):
        findings.append(_f("missing_figure_reference", "Stem refers to a figure but quesImages is empty", "diagram"))
    if re.search(r"(?:Space\s+for\s+rough\s+work|(?:^|\s)Q(?:uestion)?\s*\d+\s*[.:])", plain_text(raw), re.I):
        findings.append(_f("noise", "Possible leaked numbering or rough-work text", "noise", "info"))
    if re.search(r"<ol\b[^>]*>\s*<li\b", raw, re.I):
        findings.append(_f("list_numbering", "Ordered-list markup appears in stem; review for stray list numbering", "noise", "info"))
    if re.search(r"<m(?:i|o|n)[^>]*>\s*&\s*</m(?:i|o|n)>", raw + solution, re.I):
        findings.append(_f("mathml_ampersand", "Literal ampersand in MathML token", "notation"))
    if not solution.strip():
        findings.append(_f("solution_empty", "Stored solution field is empty", "solution_missing"))
    for r in reports:
        for h in question.get("errorHistory", []):
            dt = h.get("updatedAt") or h.get("resolvedAt") or h.get("createdAt")
            if not dt:
                continue
            try:
                if datetime.fromisoformat(dt.replace("Z", "+00:00")) > datetime.fromisoformat(r["reportedAt"].replace("Z", "+00:00")):
                    findings.append(_f("history_newer", f"Error history entry postdates {r['reportId']}; verify current issue is absent", None, "info"))
                    comment = r.get("comment", "").casefold()
                    has_all_options = all(opts.get(k) for k in "ABCD") if qt in ("scq", "mcq") else False
                    absent = (("missing" in comment or "blank" in comment) and "option" in comment and has_all_options)
                    absent = absent or ("\\frac" in comment and not re.search(r"\\(?:frac|sqrt)", raw))
                    absent = absent or ("figure" in comment and bool(body.get("quesImages")))
                    if absent:
                        findings.append(_f("already_fixed_signal", f"{r['reportId']} predates a recorded update and the reported symptom is absent", None, "info"))
            except ValueError:
                continue
    return findings
