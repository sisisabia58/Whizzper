# AGENTS.md

## Cursor Cloud specific instructions

Whisper-WebUI is a Python (3.10–3.12) Gradio app that transcribes audio/video into subtitles. There are three surfaces of the same `modules/` pipeline; only one needs to run to test end-to-end:

- Gradio Web UI — `app.py` (primary product, port 7860)
- REST API backend — `backend/main.py` (FastAPI, optional alternative, port 8000)
- Modal GPU backend — `modal_app.py` (optional serverless cloud inference)

### Environment notes (non-obvious)

- CPU-only VM (no GPU). The repo's `requirements.txt` pins PyTorch CUDA 12.8 wheels (`--extra-index-url .../cu128`), which are broken on this box. The dev environment is installed with CPU wheels instead: `torch`/`torchaudio`/`torchvision` come from `https://download.pytorch.org/whl/cpu`. If you `pip install` torch-related packages yourself, always use the CPU index or you'll pull a `+cu128` build that fails with `operator torchvision::nms does not exist`.
- The git-based deps in `requirements.txt` (`jhj0517-whisper`, `ultimatevocalremover_api`, `pyrubberband`) need `setuptools<70` and `--no-build-isolation`; otherwise they fail with `ModuleNotFoundError: No module named 'pkg_resources'`. This mirrors `nixpacks.toml`.
- Everything lives in a project-local `venv/` (activate with `source venv/bin/activate`). System deps `ffmpeg`, `git`, `node`, and `python3.12-venv` are already present.
- Model weights and test audio download from HuggingFace/GitHub on first use (network required initially), then cache under `models/`.

### Run

- Web UI: `source venv/bin/activate && python app.py --server_name 0.0.0.0 --server_port 7860` → http://localhost:7860. Default whisper backend is `faster-whisper`; default model is large — pick `tiny` in the Model dropdown for fast CPU runs.
- REST API (optional): `source venv/bin/activate && uvicorn backend.main:app --host 0.0.0.0 --port 8000` (needs `pip install -r backend/requirements-backend.txt`; Swagger at `/docs`). Backend uses SQLite (`backend/records.db`), auto-created.

### Lint / Test

- No linter is configured in this repo (CI runs only `pytest`). Use `python -m compileall app.py backend modules` for a syntax sanity check.
- Tests: `source venv/bin/activate && python -m pytest -rs tests` (needs `jiwer`, already installed). On CPU, expect ~9 passed and ~11 skipped: BGM-separation and diarization tests are GPU-only (`is_cuda_available()` gated) and the DeepL test is skipped without `DEEPL_API_KEY`.
- Backend tests: `TEST_ENV=true python -m pytest -rs backend/tests`.

### Optional secrets

- `HF_TOKEN` — only needed for pyannote speaker diarization (also requires accepting model licenses on HuggingFace). Not needed for core transcription.
- `DEEPL_API_KEY` — only for the DeepL text-translation feature/test. NLLB translation works without any key.
