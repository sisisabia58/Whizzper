import os
from pathlib import Path

from dotenv import load_dotenv

_env_path = Path(__file__).resolve().parent / "configs" / ".env"
if _env_path.exists():
    load_dotenv(_env_path)
load_dotenv()

import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, Response
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text, inspect
import time
import threading

from backend.db.db_instance import engine, SessionLocal
from backend.routers.transcription.router import transcription_router, get_pipeline
from backend.routers.vad.router import get_vad_model, vad_router
from backend.routers.bgm_separation.router import get_bgm_separation_inferencer, bgm_separation_router
from backend.routers.task.router import task_router
from backend.routers.auth.router import auth_router
from backend.common.config_loader import read_env, load_server_config
from backend.common.cache_manager import cleanup_old_files
from backend.common.logging import setup_json_logging
from backend.common.observability import init_sentry, generate_latest, CONTENT_TYPE_LATEST
from backend.common.security import cors_origins
from modules.utils.paths import SERVER_CONFIG_PATH, BACKEND_CACHE_DIR


def clean_cache_thread(ttl: int, frequency: int) -> threading.Thread:
    def clean_cache(_ttl: int, _frequency: int):
        while True:
            cleanup_old_files(cache_dir=BACKEND_CACHE_DIR, ttl=_ttl)
            time.sleep(_frequency)

    return threading.Thread(
        target=clean_cache,
        args=(ttl, frequency),
        daemon=True
    )


def check_redis_health() -> bool:
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    try:
        import redis

        client = redis.from_url(redis_url, socket_connect_timeout=1)
        client.ping()
        return True
    except Exception:
        return False


def maybe_rebuild_database(engine) -> None:
    """Self-heal legacy schema conflicts. Destructive rebuild requires ALLOW_DB_REBUILD=true."""
    inspector = inspect(engine)
    try:
        tables = inspector.get_table_names()
        if "tasks" in tables:
            columns = [c["name"] for c in inspector.get_columns("tasks")]
            if "uuid" not in columns:
                with engine.begin() as conn:
                    drop_sql = "DROP TABLE IF EXISTS legacy_tasks CASCADE" if "postgres" in str(engine.url) else "DROP TABLE IF EXISTS legacy_tasks"
                    conn.execute(text(drop_sql))
                    conn.execute(text("ALTER TABLE tasks RENAME TO legacy_tasks"))
            else:
                try:
                    with engine.connect() as conn:
                        conn.execute(text("SELECT uuid, status, task_params, batch_id, source_parent_id, writeback_status FROM tasks LIMIT 1"))
                        conn.execute(text("SELECT id, batch_id, status, access_mode, writeback_enabled FROM batch_jobs LIMIT 1"))
                except Exception as schema_err:
                    if os.environ.get("ALLOW_DB_REBUILD", "").lower() != "true":
                        import logging
                        logging.getLogger("uvicorn.error").warning(
                            f"Database schema mismatch detected: {schema_err}. "
                            "Set ALLOW_DB_REBUILD=true to rebuild tables."
                        )
                        return

                    import logging
                    logging.getLogger("uvicorn.error").warning(
                        f"Database schema mismatch detected: {schema_err}. Rebuilding database tables..."
                    )
                    with engine.begin() as conn:
                        drop_tasks = "DROP TABLE IF EXISTS tasks CASCADE" if "postgres" in str(engine.url) else "DROP TABLE IF EXISTS tasks"
                        drop_batches = "DROP TABLE IF EXISTS batch_jobs CASCADE" if "postgres" in str(engine.url) else "DROP TABLE IF EXISTS batch_jobs"
                        conn.execute(text(drop_tasks))
                        conn.execute(text(drop_batches))
    except Exception as db_err:
        import logging
        logging.getLogger("uvicorn.error").warning(f"Database self-healing warning: {db_err}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_json_logging()
    init_sentry()
    server_config = load_server_config()
    read_env("DB_URL")

    # Automatically initialize database tables
    from backend.db.db_instance import Base
    import backend.db.models
    
    # Self-heal legacy table structure conflicts on startup
    maybe_rebuild_database(engine)

    Base.metadata.create_all(bind=engine)

    from sqlmodel import SQLModel
    import backend.db.task.models
    import backend.db.batch.models
    import backend.db.share.models
    SQLModel.metadata.create_all(bind=engine)

    transcription_pipeline = get_pipeline()
    vad_inferencer = get_vad_model()
    bgm_separation_inferencer = get_bgm_separation_inferencer()

    cache_thread = clean_cache_thread(server_config["cache"]["ttl"], server_config["cache"]["frequency"])
    cache_thread.start()
    import asyncio
    from backend.routers.task.router import task_event_broker
    task_event_broker.loop = asyncio.get_running_loop()

    yield

    transcription_pipeline = None
    vad_inferencer = None
    bgm_separation_inferencer = None


app = FastAPI(
    title="Whisper-WebUI-Backend",
    description="REST API for Whisper-WebUI.",
    version="0.0.1",
    lifespan=lifespan,
)

_allowed_origins = cors_origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(transcription_router, prefix="/api")
app.include_router(vad_router, prefix="/api")
app.include_router(bgm_separation_router, prefix="/api")
app.include_router(task_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
from backend.routers.drive.router import drive_router
app.include_router(drive_router, prefix="/api")
from backend.routers.share.router import share_router
app.include_router(share_router)


@app.get("/health")
def health_check():
    db_ok = True
    redis_ok = check_redis_health()
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1") if hasattr(text, "__call__") else "SELECT 1")
    except Exception:
        db_ok = False

    pool_data = []
    try:
        from backend.routers.transcription.router import modal_pool
        if modal_pool:
            for ep in modal_pool.endpoints:
                pool_data.append({
                    "endpoint": ep,
                    "inflight": modal_pool.counters.get(ep),
                    "healthy": ep in modal_pool.healthy_endpoints(),
                    "consecutive_failures": modal_pool._consecutive_failures.get(ep, 0)
                })
    except Exception:
        pass

    status_code = 200 if (db_ok and redis_ok) else 503
    
    response_body = {
        "status": "ok" if status_code == 200 else "degraded",
        "database": db_ok,
        "redis": redis_ok
    }
    if pool_data:
        response_body["pool"] = pool_data

    return Response(
        status_code=status_code,
        content=json.dumps(response_body),
        media_type="application/json"
    )


@app.get("/metrics")
def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/api/config/client")
def client_config():
    """Runtime client config (e.g. public URL for Google Translate share links in local dev)."""
    public_url = os.getenv("PUBLIC_APP_URL", "").strip().rstrip("/")
    return {"public_app_url": public_url or None}


from fastapi.staticfiles import StaticFiles

app.mount("/", StaticFiles(directory="backend/static", html=True), name="static")

