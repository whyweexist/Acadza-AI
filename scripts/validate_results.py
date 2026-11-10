"""Run only if requested: validates schema, links and taxonomy without AI calls."""
from __future__ import annotations
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'services'/'triage'))
from pydantic import TypeAdapter
from app.core.contracts import TriageResult
from app.core.loader import fingerprint
from app.core.safety import apply_patch

def main()->int:
    reports=json.loads((ROOT/'data'/'reports.json').read_text())
    questions={q['_id']:q for q in json.loads((ROOT/'data'/'questions.json').read_text())}
    taxonomy=json.loads((ROOT/'data'/'taxonomy.json').read_text())
    entries=json.loads((ROOT/'results.json').read_text())
    assert len(entries)==len(reports), 'Incorrect result count'
    expected={r['reportId']:r['questionId'] for r in reports}
    assert {r['reportId']:r['questionId'] for r in entries}==expected, 'Missing/duplicate/mismatched report'
    adapter=TypeAdapter(TriageResult)
    for row in entries:
        adapter.validate_python(row)
        if row['verdict']=='defect':
            repair=row['repair']; assert repair in taxonomy['repairs']
            edit=row['edit']
            if edit:
                assert edit['field'] in taxonomy['repairs'][repair]['fields'], (row['reportId'],'scope violation')
                from app.core.contracts import Edit
                apply_patch(questions[row['questionId']],Edit.model_validate(edit),fingerprint(questions[row['questionId']]))
            if row['route']=='auto_apply':
                assert taxonomy['repairs'][repair]['auto'] and edit
        else:
            assert row['route']=='no_change' and row['repair'] is None and row['edit'] is None
    print('JSON schema, report identity, scope and deterministic patch matching verified')
    return 0
if __name__=='__main__':raise SystemExit(main())
