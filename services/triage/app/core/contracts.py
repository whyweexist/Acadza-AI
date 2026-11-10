"""Shared typed contracts. The closed taxonomy is additionally checked at runtime."""
from __future__ import annotations
from typing import Annotated, Any, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

Verdict = Literal["defect", "no_error", "display_issue", "app_issue", "language_mode", "already_fixed", "not_actionable"]
Route = Literal["auto_apply", "faculty_review", "no_change"]
QuestionType = Literal["scq", "mcq", "integerQuestion"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Edit(Strict):
    field: Literal["question", "solution", "answer", "questionType"]
    find: str = Field(min_length=1)
    replace: str


class BaseResult(Strict):
    reportId: str
    questionId: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: str = Field(min_length=3, max_length=1500)
    student_reply: str = Field(min_length=3, max_length=1000)


class DefectResult(BaseResult):
    verdict: Literal["defect"]
    repair: str = Field(min_length=1)
    edit: Edit | None
    route: Literal["auto_apply", "faculty_review"]


class NonDefectResult(BaseResult):
    verdict: Literal["no_error", "display_issue", "app_issue", "language_mode", "already_fixed", "not_actionable"]
    repair: None = None
    edit: None = None
    route: Literal["no_change"] = "no_change"


TriageResult = Annotated[DefectResult | NonDefectResult, Field(discriminator="verdict")]


class ResultEnvelope(Strict):
    result: TriageResult


class Claim(Strict):
    claim_type: Literal["answer", "option", "stem", "solution", "spelling", "diagram", "metadata", "syllabus", "display", "app", "language", "unspecified", "injection"]
    claimed_answer: str | None = None
    target: str | None = None
    language: str | None = None
    injection: bool = False


class Solver(Strict):
    answer: str | list[str] | None
    working: str
    no_valid_option: bool
    multiple_valid: bool
    missing_data: bool


class SolutionAudit(Strict):
    belongs_to_question: bool
    final_answer: str | list[str] | None
    wrong_steps: list[str]
    values_not_in_stem: list[str]


class LintCandidate(Strict):
    repair: str
    edit: Edit
    explanation: str


class TextLint(Strict):
    candidates: list[LintCandidate]


class MetadataAudit(Strict):
    subject_fits: bool
    chapter_fits: bool
    suggested_chapter: str | None = None
    explanation: str


class Adjudication(Strict):
    verdict: Verdict
    repair: str | None
    edits: list[Edit] = Field(default_factory=list)
    evidence: str

    @model_validator(mode="after")
    def has_repair_if_defect(self) -> "Adjudication":
        if self.verdict == "defect" and not self.repair:
            raise ValueError("Defect requires repair")
        if self.verdict != "defect" and (self.repair or self.edits):
            raise ValueError("Non-defect cannot have repair or edit")
        return self


class Reply(Strict):
    text: str = Field(min_length=3, max_length=500)


class ReviewAction(Strict):
    action: Literal["approve", "edit", "reject"]
    expected_hash: str
    expected_revision: int = Field(ge=0)
    actor: str = Field(min_length=2, max_length=120)
    reason: str = Field(default="", max_length=1000)
    edit: Edit | None = None
    idempotency_key: str = Field(min_length=8, max_length=120)

    @model_validator(mode="after")
    def ensure_edit(self) -> "ReviewAction":
        if self.action == "edit" and self.edit is None:
            raise ValueError("Edit action requires an edit")
        if self.action != "edit" and self.edit is not None:
            raise ValueError("Only edit actions can contain an edit")
        return self


class StaticFinding(Strict):
    code: str
    severity: Literal["info", "warning", "critical"]
    evidence: str
    suggested_repair: str | None = None
