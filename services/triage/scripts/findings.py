"""Unreported question signals are kept outside results.json."""
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.core.loader import read_json
from app.core.static_checks import inspect_question
from app.core.settings import ROOT

questions=read_json("questions.json"); reports=read_json("reports.json")
reported={r["questionId"] for r in reports}
findings=[{"questionId":q["_id"],"subject":q.get("subject"),"chapter":q.get("chapter"),"findings":[x.model_dump() for x in inspect_question(q)],"status":"candidate_only_unverified"} for q in questions if q["_id"] not in reported]
(ROOT/"findings.json").write_text(json.dumps(findings,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
print(f"Wrote {len(findings)} unreported-question scans; static signals are not confirmed defects")
