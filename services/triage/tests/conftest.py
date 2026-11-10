"""Fixtures for future test execution. Tests are included but intentionally not run."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pytest
from app.core.loader import read_json

@pytest.fixture
def questions():return read_json('questions.json')

@pytest.fixture
def reports():return read_json('reports.json')

@pytest.fixture
def taxonomy():return read_json('taxonomy.json')
