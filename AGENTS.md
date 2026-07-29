# AGENTS.md

## Cursor Cloud specific instructions

Whizzper (branch `Improvement-v3`) is a hybrid transcription app. Production topology: **Modal** runs GPU inference (`modal_app.py`), **Railway** runs the FastAPI web app which serves the React frontend and talks to a **Postgres** DB (+ **Redis**). Gradio (`app.py`) is legacy and no longer used on this branch.

### Services

- FastAPI backend — `uvicorn backend.main:app --host 0.0.0.0 --port 8000`. Serves the built frontend from `backend/static` at `/`, REST API under `/api`, plus `/health`, `/metrics`, `/docs`. DB tables auto-create on startup (no manual migration needed; `alembic` migrations also exist under `backend/migrations`).
- Frontend — `frontend/` (React 19 + Vite + Tailwind). Build with `cd frontend && npm run build` (emits to `backend/static`, which the backend serves same-origin). `npm run dev` starts a Vite dev server, but its proxy rewrites `/api`→`/` while the backend expects the `/api` prefix, so prefer the build-and-serve flow for a faithful end-to-end run. There is no working `lint`/test runner (eslint/vitest are not in `devDependencies`).
- Postgres + Redis — local services (installed system-wide). systemd is not running in this container, so start them directly:
  - `sudo pg_ctlcluster 16 main start`
  - `sudo redis-server /etc/redis/redis.conf --daemonize yes`
  - Local DB was created as role/db `whizzper`/`whizzper` (password `whizzper`). Recreate if missing: `sudo -u postgres createdb -O whizzper whizzper` (create the role first if needed).

### Required env vars (read at import time)

`backend/db/db_instance.py`, `backend/queue/celery_app.py`, and the Modal pool in `backend/routers/transcription/router.py` read env vars at **import** (before the `.env` is loaded inside `lifespan`), so these must be in the process env at launch. Put them in `backend/configs/.env` (gitignored) and source it before `uvicorn`, e.g.:

```
source venv/bin/activate
set -a; source backend/configs/.env; set +a
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

- `DB_URL` — e.g. `postgresql+psycopg2://whizzper:whizzper@127.0.0.1:5432/whizzper` (falls back to `DATABASE_URL`, then `sqlite:///./whizzper.db`).
- `REDIS_URL` — e.g. `redis://localhost:6379/0` (Celery broker/backend; the transcription path uses FastAPI `BackgroundTasks`, not Celery, so a Celery worker is not required for transcription).
- `MODAL_WEB_ENDPOINT_URL` (or `MODAL_ENDPOINTS`) — deployed Modal inference endpoint(s), comma-separated for a pool. Provided via a Cursor secret; sourcing `.env` puts it in the process env so the Modal pool is built at import. Verify with `/health` (shows `pool` with healthy endpoints). See "Two run modes" below.

### Two run modes (important CPU gotcha)

This VM is CPU-only. `backend/main.py` eagerly initializes the whisper/VAD/BGM inferencers on startup.

- Modal mode (matches production): set `MODAL_WEB_ENDPOINT_URL`. The startup then **skips** loading local model weights (see `get_bgm_separation_inferencer`/`get_pipeline`), so the committed `config.yaml` (`bgm_separation.device: cuda`, `whisper.compute_type: float16`) is fine and inference is offloaded to Modal. This is the preferred local dev mode; provide the endpoint via `MODAL_WEB_ENDPOINT_URL`.
- Local-CPU mode (no Modal): without `MODAL_WEB_ENDPOINT_URL`, startup tries to load the UVR model on `cuda` and crashes with `Torch not compiled with CUDA enabled`. To run fully local on CPU, temporarily set in `backend/configs/config.yaml`: `bgm_separation.device: cpu`, `whisper.compute_type: float32`, `whisper.model_size: tiny` (do NOT commit — these are production GPU settings). Also pass `?compute_type=float32&model_size=tiny` when calling `/api/transcription/`, because request params override the server config.

Known caveat (local-CPU mode + Postgres): the local inference path passes a numpy progress value into a DB update, which psycopg2 cannot adapt (`InvalidSchemaName: schema "np" does not exist`), so tasks stall at 5%. This does NOT affect production, because the Modal path passes `progress_callback=None`. For fully-local end-to-end transcription, use SQLite (`DB_URL="sqlite:///backend/records_dev.db"`).

### Lint / Test

- Backend tests: `TEST_ENV=true DB_URL="sqlite:///:memory:" python -m pytest backend/tests` (config in `pytest.ini`). Expect ~51 passing; a few are pre-existing failures on this branch (transcription/vad tests POST to `/transcription` but the route is `/api/transcription/`; some batch/drive tests hit SQLite's cross-thread limitation). `torch` is CPU-only here (see below).
- No configured linter for Python; use `python -m compileall app.py backend modules` for a syntax check.

### Python deps note

`requirements.txt` pins CUDA (`cu128`) torch wheels which are broken on this CPU VM; the venv installs CPU wheels for `torch`/`torchaudio`/`torchvision` instead. Git-based deps require `setuptools<70` + `--no-build-isolation` (mirrors `nixpacks.toml`). Everything runs in the project-local `venv/` (`source venv/bin/activate`).
