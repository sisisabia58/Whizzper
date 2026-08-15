def test_postgres_pool_defaults_allow_threaded_workers(monkeypatch):
    monkeypatch.setenv("DB_URL", "postgresql+psycopg2://u:p@localhost/db")
    monkeypatch.delenv("DB_POOL_SIZE", raising=False)
    monkeypatch.delenv("DB_MAX_OVERFLOW", raising=False)
    from backend.db.db_instance import postgres_pool_kwargs

    kwargs = postgres_pool_kwargs()
    assert kwargs["pool_size"] == 20
    assert kwargs["max_overflow"] == 40
