import os
import inspect
from functools import wraps
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker


def normalize_db_url(url: str) -> str:
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg2://", 1)
    return url


raw_url = os.environ.get("DB_URL") or os.environ.get("DATABASE_URL") or "sqlite:///./whizzper.db"
DB_URL = normalize_db_url(raw_url)

engine_args = {"pool_pre_ping": True}
if "sqlite" not in DB_URL:
    engine_args.update({"pool_size": 10, "max_overflow": 20})

engine = create_engine(DB_URL, **engine_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def handle_database_errors(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Inspect function signature
        sig = inspect.signature(func)
        bound_args = sig.bind_partial(*args, **kwargs)
        
        # Check if 'session' parameter is already bound (either in args or kwargs)
        session_bound = 'session' in bound_args.arguments
        
        created_session = None
        if not session_bound:
            # Create a new session dynamically
            created_session = SessionLocal()
            # Bind the new session to the parameter
            bound_args.arguments['session'] = created_session
            
        try:
            # Run the original function with the bound arguments
            result = func(*bound_args.args, **bound_args.kwargs)
            # If we created the session, commit it
            if created_session:
                created_session.commit()
            return result
        except Exception as e:
            # Rollback if error
            if created_session:
                created_session.rollback()
            else:
                passed_session = bound_args.arguments.get('session')
                if passed_session and hasattr(passed_session, 'rollback'):
                    passed_session.rollback()
            raise e
        finally:
            # Always close the session we created
            if created_session:
                created_session.close()

    return wrapper
