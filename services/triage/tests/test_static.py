from app.core.static_checks import inspect_question
from app.core.normalization import html_options


def test_missing_option_detected(questions,reports):
    q=next(q for q in questions if q['_id']=='622f08d7b70e4b50e4500a1b')
    codes={f.code for f in inspect_question(q)}
    assert 'missing_option' in codes


def test_mcq_answer_shape_detected(questions):
    q=next(q for q in questions if q['_id']=='68c8153cfb6b2f16e2d3ceaf')
    assert 'invalid_mcq_answer' in {x.code for x in inspect_question(q)}


def test_latex_leak_detected(questions):
    q=next(q for q in questions if q['_id']=='63765a28f1d8416ae0408d89')
    assert 'latex_leak' in {x.code for x in inspect_question(q)}
