import backend.tests.unit.ml_stubs  # noqa: F401

import os
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine, text

import backend.main as main_module


def test_schema_rebuild_skipped_without_allow_db_rebuild_flag():
    """Destructive table drops must require ALLOW_DB_REBUILD=true."""
    engine = create_engine("sqlite:///:memory:")

    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE tasks (id INTEGER PRIMARY KEY, legacy_col TEXT)"
            )
        )

    inspector = MagicMock()
    inspector.get_table_names.return_value = ["tasks"]
    inspector.get_columns.return_value = [{"name": "uuid"}]

    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("ALLOW_DB_REBUILD", None)
        with patch.object(main_module, "inspect", return_value=inspector):
            main_module.maybe_rebuild_database(engine)

    with engine.connect() as conn:
        tables = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table'")
        ).fetchall()

    assert ("tasks",) in tables


def test_schema_rebuild_runs_when_allow_db_rebuild_true():
    engine = create_engine("sqlite:///:memory:")

    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE tasks (id INTEGER PRIMARY KEY, legacy_col TEXT)"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE batch_jobs (id INTEGER PRIMARY KEY, legacy_col TEXT)"
            )
        )

    inspector = MagicMock()
    inspector.get_table_names.return_value = ["tasks", "batch_jobs"]
    inspector.get_columns.return_value = [{"name": "uuid"}]

    def failing_execute(*args, **kwargs):
        raise Exception("schema mismatch")

    mock_conn = MagicMock()
    mock_conn.execute.side_effect = failing_execute
    mock_conn.__enter__ = lambda s: mock_conn
    mock_conn.__exit__ = MagicMock(return_value=False)

    with patch.dict(os.environ, {"ALLOW_DB_REBUILD": "true"}):
        with patch.object(main_module, "inspect", return_value=inspector):
            with patch.object(engine, "connect", return_value=mock_conn):
                with patch.object(engine, "begin") as mock_begin:
                    mock_begin.return_value.__enter__.return_value.execute = MagicMock()
                    main_module.maybe_rebuild_database(engine)
                    assert mock_begin.called
