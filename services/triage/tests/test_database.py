import pytest
from app.core.database import Database,Conflict
from app.core.loader import fingerprint


@pytest.mark.asyncio
async def test_sqlite_import_idempotent(tmp_path):
    db=Database(str(tmp_path/'review.sqlite3'))
    await db.seed();await db.seed()
    cases=await db.list_cases()
    assert cases['total']==39


@pytest.mark.asyncio
async def test_case_snapshot_hash(tmp_path):
    db=Database(str(tmp_path/'review.sqlite3'))
    await db.seed()
    cases=await db.list_cases()
    first=await db.get_case(cases['items'][0]['question_id'])
    assert first['question_hash']==fingerprint(first['question'])
