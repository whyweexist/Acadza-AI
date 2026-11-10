import pytest
from pydantic import ValidationError
from app.core.contracts import DefectResult, NonDefectResult, Edit, ResultEnvelope


def test_nondefect_cannot_make_changes():
    with pytest.raises(ValidationError):
        NonDefectResult(reportId='R',questionId='Q',verdict='no_error',repair='answer_key',
                        route='faculty_review',edit=None,confidence=.8,evidence='Reason',student_reply='Thanks')


def test_defect_requires_repair():
    with pytest.raises(ValidationError):
        DefectResult(reportId='R',questionId='Q',verdict='defect',repair='',route='faculty_review',
                     edit=None,confidence=.8,evidence='Reason',student_reply='Thanks')


def test_discriminated_union():
    sample={'result':{'reportId':'R','questionId':'Q','verdict':'no_error','repair':None,'edit':None,
                      'route':'no_change','confidence':.9,'evidence':'Checked and consistent', 'student_reply':'The key is correct.'}}
    assert ResultEnvelope.model_validate(sample).result.verdict=='no_error'
