import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

def normalize_db_url(url: str) -> str:
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg2://", 1)
    return url

raw_url = os.environ.get("DB_URL", "sqlite:///./whizzper.db")
DB_URL = normalize_db_url(raw_url)

engine_args = {"pool_pre_ping": True}
if "sqlite" not in DB_URL:
    engine_args.update({"pool_size": 10, "max_overflow": 20})

engine = create_engine(DB_URL, **engine_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
