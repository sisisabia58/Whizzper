from backend.db.db_instance import normalize_db_url

def test_normalize_db_url_converts_postgres_prefix():
    raw = "postgres://user:pass@localhost:5432/dbname"
    normalized = normalize_db_url(raw)
    assert normalized == "postgresql+psycopg2://user:pass@localhost:5432/dbname"

def test_normalize_db_url_leaves_sqlite_untouched():
    raw = "sqlite:///./whizzper.db"
    normalized = normalize_db_url(raw)
    assert normalized == "sqlite:///./whizzper.db"
