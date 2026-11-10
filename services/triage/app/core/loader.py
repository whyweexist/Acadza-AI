import hashlib
import json
from pathlib import Path
from typing import Any
from .settings import ROOT


def read_json(name: str) -> Any:
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))


def question_body(question: dict) -> dict:
    return question[question["questionType"]]


def fingerprint(question: dict) -> str:
    raw = json.dumps(question, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def raw_field(question: dict, field: str) -> str:
    if field == "questionType":
        return question["questionType"]
    value = question_body(question)[field]
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def known_chapters(questions: list[dict]) -> dict[str, list[str]]:
    out: dict[str, set[str]] = {}
    for q in questions:
        out.setdefault(q.get("subject", "Unknown"), set()).add(q.get("chapter", "Unknown"))
    return {k: sorted(v) for k, v in out.items()}
