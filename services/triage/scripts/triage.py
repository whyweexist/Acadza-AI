"""Run real LLM pipeline; never substitute fake model outputs when API is absent."""
import argparse
import asyncio
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.agents.client import AgentClient
from app.core.database import Database
from app.core.pipeline import run_all
from app.core.settings import ROOT

async def main(args):
    db=Database();await db.seed()
    rows,failures=await run_all(AgentClient(db),db)
    if failures:
        (ROOT/"triage_failures.json").write_text(json.dumps(failures,indent=2),encoding="utf-8")
        print(f"{len(failures)} questions need human review because live triage could not finish; results.json NOT overwritten")
        return 2
    (ROOT/"results.json").write_text(json.dumps(rows,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"Generated {len(rows)} report results from real model calls")
    return 0

if __name__=="__main__":
    raise SystemExit(asyncio.run(main(argparse.ArgumentParser().parse_args())))
