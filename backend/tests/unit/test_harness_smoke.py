import pytest

def test_pytest_collects_and_runs():
    assert True

def test_scratch_db_fixture_available(scratch_db):
    assert scratch_db is not None
