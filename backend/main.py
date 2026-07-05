import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, Response
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
import os
import time
import threading

from backend.db.db_instance import engine, SessionLocal
from backend.routers.transcription.router import transcription_router, get_pipeline
from backend.routers.vad.router import get_vad_model, vad_router
from backend.routers.bgm_separation.router import get_bgm_separation_inferencer, bgm_separation_router
from backend.routers.task.router import task_router
from backend.common.config_loader import read_env, load_server_config
from backend.common.cache_manager import cleanup_old_files
from backend.common.logging import setup_json_logging
from backend.common.observability import init_sentry, generate_latest, CONTENT_TYPE_LATEST
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_json_logging()
    init_sentry()
    server_config = load_server_config()
    read_env("DB_URL")

    # Automatically initialize database tables
    from backend.db.db_instance import Base
    import backend.db.models
    Base.metadata.create_all(bind=engine)

    transcription_pipeline = get_pipeline()
    vad_inferencer = get_vad_model()
    bgm_separation_inferencer = get_bgm_separation_inferencer()

    cache_thread = clean_cache_thread(server_config["cache"]["ttl"], server_config["cache"]["frequency"])
    cache_thread.start()

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(transcription_router, prefix="/api")
app.include_router(vad_router, prefix="/api")
app.include_router(bgm_separation_router, prefix="/api")
app.include_router(task_router, prefix="/api")


@app.get("/health")
def health_check():
    db_ok = True
    redis_ok = True
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1") if hasattr(text, "__call__") else "SELECT 1")
    except Exception:
        db_ok = False

    status_code = 200 if (db_ok and redis_ok) else 503
    return Response(
        status_code=status_code,
        content=json.dumps({"status": "ok" if status_code == 200 else "degraded", "database": db_ok, "redis": redis_ok}),
        media_type="application/json"
    )


@app.get("/metrics")
def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


from fastapi.staticfiles import StaticFiles

app.mount("/", StaticFiles(directory="backend/static", html=True), name="static")

