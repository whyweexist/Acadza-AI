from app.core.contracts import Edit, Solver, SolutionAudit
from app.core.loader import fingerprint, raw_field
from app.core.safety import safety_gate, apply_patch, route_repair


def test_scope_blocks_answer_mutation_under_spelling(questions,taxonomy):
    q=questions[0]
    edit=Edit(field='answer',find='C',replace='D')
    check=safety_gate(q,'spelling',[edit],taxonomy,fingerprint(q),[],student_comments=[])
    assert not check.safe


def test_stale_question_hash_fails(questions):
    q=questions[0]
    try:apply_patch(q,Edit(field='answer',find='C',replace='B'),'bad-version')
    except ValueError:return
    raise AssertionError('Stale patch was accepted')


def test_nonautomatic_repair_never_passes(questions,taxonomy):
    q=questions[0]
    check=safety_gate(q,'diagram',[],taxonomy,fingerprint(q),[])
    assert not check.safe
    assert route_repair('diagram',.99,check,taxonomy)=='faculty_review'


def test_exact_match_prevents_ambiguous_replacement(questions):
    q=questions[0]
    # Frequent punctuation in the raw HTML appears many times.
    try:apply_patch(q,Edit(field='question',find='<span',replace='<i'),fingerprint(q))
    except ValueError:return
    raise AssertionError('Ambiguous patch accepted')


def test_unique_exact_patch_preserves_original(questions):
    q=questions[0]
    edit=Edit(field='answer',find='C',replace='B')
    cloned=apply_patch(q,edit,fingerprint(q))
    assert cloned['scq']['answer']=='B'
    assert q['scq']['answer']=='C'
