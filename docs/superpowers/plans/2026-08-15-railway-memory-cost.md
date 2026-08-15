# Railway Memory Cost Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cut Railway GB-hours (especially web RSS) by slimming the CPU-tier import graph and image, then run Modal-bound transcribe work on a thread pool, without breaking v5 batch durability.

**Architecture:** Railway web + worker stay HTTP clients to Modal. Stop loading torch/gradio/faster-whisper/pyannote on that tier. Worker default becomes a lean always-on crew with Celery beat enabled. Transcribe queue uses `-P threads`; download stays prefork. Do not switch Modal calls from HTTP pool to SDK `Function.from_name`.

**Tech Stack:** FastAPI, Celery, Redis, Postgres, Modal HTTP endpoints, ffmpeg, pytest.

## Global Constraints

- Implement on a branch created from `origin/improvement-v5` (not `cursor/enterprise-batch-celery-8d1f`, which lacks the idle/batch worker script).
- Branch name: `cursor/railway-memory-opt-8d1f`.
- Do not move GPU inference off Modal. Do not replace Celery/Redis. Do not change the batch API contract or frontend polling.
- Do not use Modal SDK `Function.from_name` for pooled production traffic; keep HTTP POST through `ModalEndpointPool`.
- Keep Celery beat running in every worker profile (stuck-job reconcile).
- `worker_max_tasks_per_child` default is `50` until the slim image ships, then `10`. Never use a tight `worker_max_memory_per_child` that SIGKILLs a 2h Modal POST.
- Do not promise transcribe concurrency 30 in these PRs. Cap remains `POOL_PER_ENDPOINT_CAP` × endpoint count.
- One workstream per deploy. Each task below is independently revertible.
- Tests: `TEST_ENV=true DB_URL="sqlite:///:memory:" python -m pytest backend/tests` (see `pytest.ini`). Syntax check: `python -m compileall app.py backend modules`.
- Local Gradio (`app.py` + `requirements.txt`) may still import torch; Railway uses `requirements-railway.txt` only.
- VAD/BGM **HTTP routes** on Railway return 501 when local ML deps are absent; transcription diarization/VAD/BGM still run on Modal via the existing payload flags.

---

### Task 1: Branch from improvement-v5 and capture baseline notes

**Files:**
- Create: `docs/superpowers/plans/2026-08-15-railway-memory-baseline.md` (ops checklist only; no secrets)

**Interfaces:**
- Consumes: `origin/improvement-v5`
- Produces: working branch `cursor/railway-memory-opt-8d1f`

- [ ] **Step 1: Create the branch from production**

```bash
cd /workspace
git fetch origin improvement-v5
git checkout -b cursor/railway-memory-opt-8d1f origin/improvement-v5
```

Expected: `git rev-parse --abbrev-ref HEAD` prints `cursor/railway-memory-opt-8d1f`. `scripts/start_workers.sh` contains `WORKER_PROFILE`.

- [ ] **Step 2: Write the ops baseline checklist**

Create `docs/superpowers/plans/2026-08-15-railway-memory-baseline.md` with this exact content:

```markdown
# Railway memory baseline (ops, not code)

Capture before any deploy of this branch:

1. Railway Cost by Service: web RAM GB-hours, worker RAM GB-hours.
2. web Settings replica limits (CPU / Memory).
3. worker Settings replica limits (CPU / Memory).
4. worker Variables: WORKER_PROFILE, CELERY_* if set.
5. After web boot, note RSS from Metrics (or `ps` if SSH).

Do not lower web Memory below 4 GB until Task 8 (slim image) is deployed and RSS is confirmed down.
```

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/plans/2026-08-15-railway-memory-baseline.md
git commit -m "docs: Railway memory optimization baseline checklist"
```

---

### Task 2: Celery child recycle (W1)

**Files:**
- Modify: `backend/queue/celery_app.py`
- Modify: `backend/tests/unit/test_celery_config.py`
- Modify: `backend/configs/.env.example`

**Interfaces:**
- Consumes: existing `celery_app.conf.update(...)`
- Produces: `worker_max_tasks_per_child` from `CELERY_WORKER_MAX_TASKS_PER_CHILD` (int, default `50`)

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/unit/test_celery_config.py`:

```python
def test_worker_max_tasks_per_child_defaults_conservative():
    from backend.queue.celery_app import celery_app
    assert celery_app.conf.worker_max_tasks_per_child == 50


def test_worker_max_memory_per_child_unset():
    from backend.queue.celery_app import celery_app
    assert not celery_app.conf.worker_max_memory_per_child
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `TEST_ENV=true DB_URL="sqlite:///:memory:" python -m pytest backend/tests/unit/test_celery_config.py::test_worker_max_tasks_per_child_defaults_conservative -q`

Expected: FAIL (`assert None == 50` or AttributeError).

- [ ] **Step 3: Implement recycle config**

In `backend/queue/celery_app.py`, after `visibility_timeout = ...`, add:

```python
worker_max_tasks_per_child = int(os.environ.get("CELERY_WORKER_MAX_TASKS_PER_CHILD", "50"))
```

Inside `celery_app.conf.update(...)`, add:

```python
    worker_max_tasks_per_child=worker_max_tasks_per_child,
```

Do **not** set `worker_max_memory_per_child`.

In `backend/configs/.env.example`, under the Celery comments, add:

```
# CELERY_WORKER_MAX_TASKS_PER_CHILD=50
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `TEST_ENV=true DB_URL="sqlite:///:memory:" python -m pytest backend/tests/unit/test_celery_config.py -q`

Expected: PASS (existing three tests plus the two new ones).

- [ ] **Step 5: Commit**

```bash
git add backend/queue/celery_app.py backend/tests/unit/test_celery_config.py backend/configs/.env.example
git commit -m "fix(celery): recycle worker children after 50 tasks"
```

---

### Task 3: Lean default worker profile with beat always on (W2)

**Files:**
- Modify: `scripts/start_workers.sh`
- Create: `backend/tests/unit/test_start_workers_script.py`
- Modify: `backend/configs/.env.example`

**Interfaces:**
- Consumes: `WORKER_PROFILE` env (`idle` | `batch`)
- Produces: default `idle`; `CELERY_ENABLE_BEAT=1` in **both** profiles; batch transcribe still prefork until Task 9

- [ ] **Step 1: Write the failing characterization tests**

Create `backend/tests/unit/test_start_workers_script.py`:

```python
from pathlib import Path

SCRIPT = Path("scripts/start_workers.sh").read_text()


def test_default_profile_is_idle():
    assert 'PROFILE="${WORKER_PROFILE:-idle}"' in SCRIPT


def test_idle_profile_enables_beat():
    idle_block = SCRIPT.split("idle)", 1)[1].split("batch)", 1)[0]
    assert 'CELERY_ENABLE_BEAT:=1' in idle_block
    assert 'CELERY_ENABLE_BEAT:=0' not in idle_block


def test_batch_profile_enables_beat():
    batch_block = SCRIPT.split("batch)", 1)[1].split("*)", 1)[0]
    assert 'CELERY_ENABLE_BEAT:=1' in batch_block
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `TEST_ENV=true python -m pytest backend/tests/unit/test_start_workers_script.py -q`

Expected: FAIL on default profile (`:-batch`) and/or idle beat `:=0`.

- [ ] **Step 3: Patch `scripts/start_workers.sh`**

Change the default and idle beat lines only:

```bash
PROFILE="${WORKER_PROFILE:-idle}"
```

In the `idle)` case, replace:

```bash
    : "${CELERY_ENABLE_BEAT:=0}"
```

with:

```bash
    : "${CELERY_ENABLE_BEAT:=1}"
```

Leave idle `CELERY_COMBINED_WORKER:=1` and combined concurrency `2`. Leave batch download 4 / transcribe 8 / control 2.

Update `.env.example` Celery block to:

```
# WORKER_PROFILE=idle|batch  (default idle = low RAM; set batch for large Drive jobs)
# Beat is always on (reconcile_stuck_tasks). Do not set CELERY_ENABLE_BEAT=0.
# CELERY_COMBINED_WORKER=1
# CELERY_COMBINED_CONCURRENCY=2
# CELERY_DOWNLOAD_CONCURRENCY=4
# CELERY_TRANSCRIBE_CONCURRENCY=8
# CELERY_CONTROL_CONCURRENCY=2
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `TEST_ENV=true python -m pytest backend/tests/unit/test_start_workers_script.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/start_workers.sh backend/tests/unit/test_start_workers_script.py backend/configs/.env.example
git commit -m "fix(railway): default idle workers and keep Celery beat enabled"
```

---

### Task 4: Strip torch/gradio/faster-whisper from CPU data_classes (W4a)

**Files:**
- Modify: `modules/utils/constants.py`
- Modify: `modules/whisper/data_classes.py`
- Create: `backend/tests/unit/test_cpu_import_graph.py`

**Interfaces:**
- Consumes: Pydantic param models used by FastAPI/Celery
- Produces: `modules.whisper.data_classes` importable with no `torch`, `gradio`, `gradio_i18n`, or `faster_whisper` at module load
- `AUTOMATIC_DETECTION` is the English string `"Automatic Detection"` (Gradio i18n labels stay in `to_gradio_*` via lazy `_()`)

- [ ] **Step 1: Write the failing AST tests**

Create `backend/tests/unit/test_cpu_import_graph.py`:

```python
import ast
from pathlib import Path

FORBIDDEN = {"torch", "torchaudio", "gradio", "gradio_i18n", "faster_whisper", "whisper", "pyannote"}


def _top_level_roots(path: str) -> set[str]:
    tree = ast.parse(Path(path).read_text())
    roots: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def test_constants_has_no_gradio_i18n():
    assert "gradio_i18n" not in _top_level_roots("modules/utils/constants.py")


def test_data_classes_has_no_ml_imports():
    roots = _top_level_roots("modules/whisper/data_classes.py")
    assert not (roots & FORBIDDEN)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `TEST_ENV=true python -m pytest backend/tests/unit/test_cpu_import_graph.py -q`

Expected: FAIL (`gradio_i18n` in constants, `torch`/`gradio`/`faster_whisper` in data_classes).

- [ ] **Step 3: Slim `modules/utils/constants.py` to**

```python
AUTOMATIC_DETECTION = "Automatic Detection"
GRADIO_NONE_STR = ""
GRADIO_NONE_NUMBER_MAX = 9999
GRADIO_NONE_NUMBER_MIN = 0
```

- [ ] **Step 4: Slim `modules/whisper/data_classes.py` imports**

Replace the top of the file (through the constants import) with:

```python
from typing import Optional, Dict, List, Union, NamedTuple, Any
from fastapi import Query
from pydantic import BaseModel, Field, field_validator, ConfigDict
from enum import Enum
from copy import deepcopy
import yaml

from modules.utils.constants import *
```

Change `Segment.from_faster_whisper` to duck-type (no `faster_whisper` import):

```python
    @classmethod
    def from_faster_whisper(cls, seg: Any):
        if seg.words is not None:
            words = [
                Word(
                    start=w.start,
                    end=w.end,
                    word=w.word,
                    probability=w.probability
                ) for w in seg.words
            ]
        else:
            words = None
        return cls(
            id=seg.id,
            seek=seg.seek,
            text=seg.text,
            start=seg.start,
            end=seg.end,
            tokens=seg.tokens,
            temperature=seg.temperature,
            avg_logprob=seg.avg_logprob,
            compression_ratio=seg.compression_ratio,
            no_speech_prob=seg.no_speech_prob,
            words=words
        )
```

Inside **each** `to_gradio_inputs` / `to_gradio_input` method, as the first lines of the method body, add:

```python
        import gradio as gr
        from gradio_i18n import gettext as _
```

Change any `to_gradio_*` return type hints that use `gr.components...` to `List[Any]` (or quote them) so `gr` is not needed at class-body evaluation.

Leave field definitions and FastAPI `Field(Query())` usage unchanged.

- [ ] **Step 5: Run tests to verify they pass**

Run: `TEST_ENV=true python -m pytest backend/tests/unit/test_cpu_import_graph.py backend/tests/test_backend_config.py -q`

Expected: PASS. If `test_backend_config.py` imported Gradio widgets, it should still construct Pydantic models.

- [ ] **Step 6: Commit**

```bash
git add modules/utils/constants.py modules/whisper/data_classes.py backend/tests/unit/test_cpu_import_graph.py
git commit -m "perf: stop importing torch and Gradio from CPU data_classes"
```

---

### Task 5: Modal pipeline without local UVR/VAD/diarizer constructors (W4b)

**Files:**
- Modify: `modules/whisper/modal_whisper_inference.py`
- Modify: `modules/whisper/whisper_factory.py`
- Modify: `backend/routers/transcription/router.py`
- Modify: `backend/tests/unit/test_cpu_import_graph.py`

**Interfaces:**
- Consumes: Task 4 slim `data_classes`
- Produces: `ModalWhisperInference` that does not call `BaseTranscriptionPipeline.__init__` (no Diarizer/UVR/Silero on Railway)
- Produces: `WhisperFactory.create_whisper_inference(...)` lazy-imports local backends only in non-Modal branches

- [ ] **Step 1: Extend the import-graph test**

Append to `backend/tests/unit/test_cpu_import_graph.py`:

```python
def test_modal_whisper_inference_has_no_base_pipeline_import():
    roots = _top_level_roots("modules/whisper/modal_whisper_inference.py")
    assert "gradio" not in roots
    src = Path("modules/whisper/modal_whisper_inference.py").read_text()
    assert "from modules.whisper.base_transcription_pipeline import" not in src


def test_whisper_factory_does_not_import_torch_at_module_level():
    roots = _top_level_roots("modules/whisper/whisper_factory.py")
    assert "torch" not in roots
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `TEST_ENV=true python -m pytest backend/tests/unit/test_cpu_import_graph.py -q`

Expected: FAIL.

- [ ] **Step 3: Rewrite `ModalWhisperInference` as a standalone class**

Remove:

```python
import gradio as gr
from modules.whisper.base_transcription_pipeline import BaseTranscriptionPipeline
```

Add:

```python
from modules.utils.constants import (
    AUTOMATIC_DETECTION,
    GRADIO_NONE_NUMBER_MAX,
    GRADIO_NONE_NUMBER_MIN,
    GRADIO_NONE_STR,
)
```

Change the class to **not** subclass `BaseTranscriptionPipeline`. Keep `transcribe`, `update_model`, and `run` method signatures, but:

- `__init__` must not call `super().__init__`. Set `self.output_dir`, `self.endpoint_url`, `self.device`, `self.available_models`, `self.available_compute_types`, `self.current_model_size = None`, `self.current_compute_type = None` locally (same URL parsing as today).
- Replace `progress: gr.Progress = gr.Progress()` defaults with `progress=None`.
- Replace `self.validate_gradio_values(params)` with a local static method that does **not** import `whisper`:

```python
    @staticmethod
    def validate_gradio_values(params: TranscriptionPipelineParams) -> TranscriptionPipelineParams:
        if params.whisper.lang == AUTOMATIC_DETECTION:
            params.whisper.lang = None
        if params.whisper.initial_prompt == GRADIO_NONE_STR:
            params.whisper.initial_prompt = None
        if params.whisper.prefix == GRADIO_NONE_STR:
            params.whisper.prefix = None
        if params.whisper.hotwords == GRADIO_NONE_STR:
            params.whisper.hotwords = None
        if params.whisper.max_new_tokens == GRADIO_NONE_NUMBER_MIN:
            params.whisper.max_new_tokens = None
        if params.whisper.hallucination_silence_threshold == GRADIO_NONE_NUMBER_MIN:
            params.whisper.hallucination_silence_threshold = None
        if params.whisper.language_detection_threshold == GRADIO_NONE_NUMBER_MIN:
            params.whisper.language_detection_threshold = None
        if params.vad.max_speech_duration_s == GRADIO_NONE_NUMBER_MAX:
            params.vad.max_speech_duration_s = float("inf")
        return params
```

Keep the HTTP POST path when `self.endpoint_url` is set. Do not change it to `modal.Function.from_name`.

- [ ] **Step 4: Lazy-import in `whisper_factory.py`**

Replace the module with lazy backend imports. The Modal branch must be first and must import only `ModalWhisperInference`:

```python
from typing import Optional
import os

from modules.utils.paths import (
    FASTER_WHISPER_MODELS_DIR,
    DIARIZATION_MODELS_DIR,
    OUTPUT_DIR,
    INSANELY_FAST_WHISPER_MODELS_DIR,
    WHISPER_MODELS_DIR,
    UVR_MODELS_DIR,
)
from modules.whisper.data_classes import WhisperImpl
from modules.utils.logger import get_logger

logger = get_logger()


class WhisperFactory:
    @staticmethod
    def create_whisper_inference(
        whisper_type: str,
        whisper_model_dir: str = WHISPER_MODELS_DIR,
        faster_whisper_model_dir: str = FASTER_WHISPER_MODELS_DIR,
        insanely_fast_whisper_model_dir: str = INSANELY_FAST_WHISPER_MODELS_DIR,
        diarization_model_dir: str = DIARIZATION_MODELS_DIR,
        uvr_model_dir: str = UVR_MODELS_DIR,
        output_dir: str = OUTPUT_DIR,
        endpoint_url: Optional[str] = None,
    ):
        os.environ["KMP_DUPLICATE_LIB_OK"] = "True"
        whisper_type = whisper_type.strip().lower()

        if (
            whisper_type == WhisperImpl.MODAL.value
            or os.environ.get("MODAL_WEB_ENDPOINT_URL")
            or os.environ.get("MODAL_ENDPOINTS")
            or endpoint_url
        ):
            from modules.whisper.modal_whisper_inference import ModalWhisperInference
            logger.info("Using Modal serverless GPU inference pipeline.")
            return ModalWhisperInference(endpoint_url=endpoint_url, output_dir=output_dir)

        import torch
        from modules.whisper.faster_whisper_inference import FasterWhisperInference
        from modules.whisper.whisper_Inference import WhisperInference
        from modules.whisper.insanely_fast_whisper_inference import InsanelyFastWhisperInference

        if whisper_type == WhisperImpl.FASTER_WHISPER.value:
            if torch.xpu.is_available():
                logger.warning(
                    "XPU is detected but faster-whisper only supports CUDA. "
                    "Automatically switching to insanely-whisper implementation."
                )
                return InsanelyFastWhisperInference(
                    model_dir=insanely_fast_whisper_model_dir,
                    output_dir=output_dir,
                    diarization_model_dir=diarization_model_dir,
                    uvr_model_dir=uvr_model_dir,
                )
            return FasterWhisperInference(
                model_dir=faster_whisper_model_dir,
                output_dir=output_dir,
                diarization_model_dir=diarization_model_dir,
                uvr_model_dir=uvr_model_dir,
            )
        if whisper_type == WhisperImpl.WHISPER.value:
            return WhisperInference(
                model_dir=whisper_model_dir,
                output_dir=output_dir,
                diarization_model_dir=diarization_model_dir,
                uvr_model_dir=uvr_model_dir,
            )
        if whisper_type == WhisperImpl.INSANELY_FAST_WHISPER.value:
            return InsanelyFastWhisperInference(
                model_dir=insanely_fast_whisper_model_dir,
                output_dir=output_dir,
                diarization_model_dir=diarization_model_dir,
                uvr_model_dir=uvr_model_dir,
            )
        return FasterWhisperInference(
            model_dir=faster_whisper_model_dir,
            output_dir=output_dir,
            diarization_model_dir=diarization_model_dir,
            uvr_model_dir=uvr_model_dir,
        )
```

- [ ] **Step 5: Drop unused router import**

In `backend/routers/transcription/router.py`, delete:

```python
from modules.whisper.faster_whisper_inference import FasterWhisperInference
from modules.whisper.base_transcription_pipeline import BaseTranscriptionPipeline
```

Change `get_pipeline` return annotation to unquoted duck typing:

```python
def get_pipeline(endpoint_url: Optional[str] = None):
```

Keep the `Optional` import (already used). If `Optional` is only from `data_classes import *`, add `from typing import Optional` at the top (the file already imports `List, Dict` from typing — extend that import).

- [ ] **Step 6: Run tests**

Run: `TEST_ENV=true DB_URL="sqlite:///:memory:" python -m pytest backend/tests/unit/test_cpu_import_graph.py backend/tests/unit/test_pool_select.py backend/tests/unit/test_batch_router.py -q`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add modules/whisper/modal_whisper_inference.py modules/whisper/whisper_factory.py backend/routers/transcription/router.py backend/tests/unit/test_cpu_import_graph.py
git commit -m "perf: Modal pipeline skips local UVR/VAD/diarizer imports"
```

---

### Task 6: Skip eager ML init on web; stub VAD/BGM when deps missing (W4c)

**Files:**
- Modify: `backend/main.py`
- Modify: `backend/routers/vad/router.py`
- Modify: `backend/routers/bgm_separation/router.py`
- Create: `backend/tests/unit/test_modal_lifespan_skips_ml.py`

**Interfaces:**
- Consumes: `MODAL_WEB_ENDPOINT_URL` / `MODAL_ENDPOINTS`
- Produces: lifespan does not call `get_pipeline` / `get_vad_model` / `get_bgm_separation_inferencer` when Modal is configured
- Produces: `/api/vad` and `/api/bgm-separation` return HTTP 501 if local inferencers cannot be imported

- [ ] **Step 1: Write the failing test for lifespan skip**

Create `backend/tests/unit/test_modal_lifespan_skips_ml.py`:

```python
import os
from unittest.mock import patch


def test_lifespan_skips_local_ml_when_modal_configured():
    os.environ["MODAL_WEB_ENDPOINT_URL"] = "https://mock-endpoint.modal.run"
    with patch("backend.main.get_pipeline") as gp, \
         patch("backend.main.get_vad_model") as gv, \
         patch("backend.main.get_bgm_separation_inferencer") as gb:
        from backend.main import maybe_skip_local_ml_warmup
        maybe_skip_local_ml_warmup()
        gp.assert_not_called()
        gv.assert_not_called()
        gb.assert_not_called()
```

This test expects a helper. If you prefer not to extract a helper, patch lifespan by calling the helper you will add in Step 3.

- [ ] **Step 2: Run test to verify it fails**

Run: `TEST_ENV=true DB_URL="sqlite:///:memory:" python -m pytest backend/tests/unit/test_modal_lifespan_skips_ml.py -q`

Expected: FAIL (`maybe_skip_local_ml_warmup` missing).

- [ ] **Step 3: Add helper and use it in lifespan**

In `backend/main.py`:

```python
def modal_inference_configured() -> bool:
    return bool(os.environ.get("MODAL_WEB_ENDPOINT_URL") or os.environ.get("MODAL_ENDPOINTS"))
```

Replace the three warmup lines in `lifespan` with:

```python
    transcription_pipeline = None
    vad_inferencer = None
    bgm_separation_inferencer = None
    if not modal_inference_configured():
        transcription_pipeline = get_pipeline()
        vad_inferencer = get_vad_model()
        bgm_separation_inferencer = get_bgm_separation_inferencer()
```

Add `maybe_skip_local_ml_warmup` used by the test as an alias that documents the branch:

```python
def maybe_skip_local_ml_warmup():
    """No-op marker for tests: warmup is gated by modal_inference_configured()."""
    if modal_inference_configured():
        return
    get_pipeline()
    get_vad_model()
    get_bgm_separation_inferencer()
```

- [ ] **Step 4: Lazy-import VAD/BGM inferencers; 501 if missing**

In `backend/routers/vad/router.py`, remove top-level `from modules.vad.silero_vad import SileroVAD` and `from faster_whisper.vad import VadOptions`.

Change `get_vad_model` to:

```python
@functools.lru_cache
def get_vad_model():
    from modules.vad.silero_vad import SileroVAD
    inferencer = SileroVAD()
    if not os.environ.get("MODAL_WEB_ENDPOINT_URL"):
        inferencer.update_model()
    return inferencer
```

In the POST handler, wrap `get_vad_model()` in:

```python
    try:
        get_vad_model()
    except ImportError as exc:
        raise HTTPException(
            status_code=501,
            detail="Local VAD is not installed on this host; use Modal transcription.",
        ) from exc
```

Add `HTTPException` to the fastapi imports.

Mirror the same pattern in `backend/routers/bgm_separation/router.py` for `MusicSeparator` / `get_bgm_separation_inferencer`.

- [ ] **Step 5: Fix the unit test if the helper name differs, then run**

Run: `TEST_ENV=true DB_URL="sqlite:///:memory:" python -m pytest backend/tests/unit/test_modal_lifespan_skips_ml.py backend/tests/unit/test_pool_metrics.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/main.py backend/routers/vad/router.py backend/routers/bgm_separation/router.py backend/tests/unit/test_modal_lifespan_skips_ml.py
git commit -m "perf: skip web ML warmup under Modal; 501 local VAD/BGM"
```

---

### Task 7: Decode uploaded audio with ffmpeg, not faster-whisper (W4d)

**Files:**
- Modify: `backend/common/audio.py`
- Create: `backend/tests/unit/test_read_audio_ffmpeg.py`

**Interfaces:**
- Consumes: uploaded bytes
- Produces: `read_audio` returns `(np.ndarray dtype=float32, AudioInfo)` at 16 kHz mono via ffmpeg, with no `faster_whisper` import

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/test_read_audio_ffmpeg.py`:

```python
import ast
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from fastapi import UploadFile


def test_audio_module_does_not_import_faster_whisper():
    tree = ast.parse(Path("backend/common/audio.py").read_text())
    roots = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            roots.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    assert "faster_whisper" not in roots


@pytest.mark.asyncio
async def test_read_audio_uses_ffmpeg(tmp_path, monkeypatch):
    from backend.common.audio import read_audio

    pcm = (np.zeros(16000, dtype=np.float32)).tobytes()

    class FakeProc:
        def __init__(self):
            self.stdout = pcm
            self.returncode = 0
            self.stderr = b""

    upload = MagicMock(spec=UploadFile)
    upload.read = MagicMock(return_value=b"fake-bytes")

    async def _read():
        return b"fake-bytes"

    upload.read = _read

    with patch("backend.common.audio.subprocess.run", return_value=FakeProc()):
        audio, info = await read_audio(file=upload)
    assert audio.dtype == np.float32
    assert info.duration == pytest.approx(1.0)
```

If pytest-asyncio is missing, write a sync helper `_decode_audio_bytes(data: bytes) -> np.ndarray` and test that instead; keep `read_audio` as a thin async wrapper.

- [ ] **Step 2: Run tests to verify they fail**

Run: `TEST_ENV=true python -m pytest backend/tests/unit/test_read_audio_ffmpeg.py -q`

Expected: FAIL on faster_whisper import.

- [ ] **Step 3: Replace `backend/common/audio.py` decode path**

Keep `httpx` + `UploadFile` validation. Replace `faster_whisper.audio.decode_audio` with:

```python
import subprocess
import numpy as np


def decode_audio_bytes(file_content: bytes) -> np.ndarray:
    proc = subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-i",
            "pipe:0",
            "-f",
            "f32le",
            "-acodec",
            "pcm_f32le",
            "-ac",
            "1",
            "-ar",
            "16000",
            "pipe:1",
        ],
        input=file_content,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0 or not proc.stdout:
        raise HTTPException(status_code=422, detail="Could not decode audio")
    audio = np.frombuffer(proc.stdout, dtype=np.float32)
    return audio
```

`read_audio` then:

```python
    audio = decode_audio_bytes(file_content)
    duration = len(audio) / 16000
    return audio, AudioInfo(duration=duration)
```

Remove `import faster_whisper`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `TEST_ENV=true python -m pytest backend/tests/unit/test_read_audio_ffmpeg.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/common/audio.py backend/tests/unit/test_read_audio_ffmpeg.py
git commit -m "perf: decode uploads with ffmpeg instead of faster-whisper"
```

---

### Task 8: Slim `requirements-railway.txt` and add import-smoke (W4e)

**Files:**
- Modify: `requirements-railway.txt`
- Create: `backend/tests/unit/test_railway_import_smoke.py`
- Modify: `backend/tests/unit/test_cpu_import_graph.py` (forbidden list already used)

**Interfaces:**
- Consumes: Tasks 4–7 (CPU path must not import removed packages)
- Produces: Railway image without torch/torchaudio/openai-whisper/faster-whisper/transformers/pyannote/gradio/matplotlib
- Keep: fastapi, uvicorn, celery, redis, sqlalchemy, sqlmodel, psycopg2-binary, numpy, requests, httpx, soundfile, python-multipart, pydantic, prometheus-client, sentry-sdk, python-dotenv, google-api-python-client, cryptography, google-auth-oauthlib, yt-dlp, ruamel.yaml, modal
- Modal GPU image in `modal_app.py` is unchanged

- [ ] **Step 1: Write the failing requirements test**

Append to `backend/tests/unit/test_cpu_import_graph.py`:

```python
def test_requirements_railway_omits_gpu_stack():
    text = Path("requirements-railway.txt").read_text().lower()
    for pkg in ("torch", "torchaudio", "openai-whisper", "faster-whisper", "transformers", "pyannote", "gradio", "matplotlib"):
        assert pkg not in text, pkg
```

Note: `torch` as a substring can false-positive on unrelated names. Assert line-wise:

```python
def test_requirements_railway_omits_gpu_stack():
    lines = [
        ln.strip().lower().split("==")[0].split(">=")[0].split("[")[0]
        for ln in Path("requirements-railway.txt").read_text().splitlines()
        if ln.strip() and not ln.strip().startswith("#") and not ln.strip().startswith("--")
    ]
    forbidden = {
        "torch",
        "torchaudio",
        "openai-whisper",
        "faster-whisper",
        "transformers",
        "pyannote.audio",
        "gradio",
        "gradio-i18n",
        "matplotlib",
    }
    assert not (set(lines) & forbidden)
```

Create `backend/tests/unit/test_railway_import_smoke.py`:

```python
def test_whisper_factory_modal_path_does_not_import_torch(monkeypatch):
    monkeypatch.setenv("MODAL_WEB_ENDPOINT_URL", "https://mock-endpoint.modal.run")
    import sys
    sys.modules.pop("torch", None)
    from modules.whisper.whisper_factory import WhisperFactory
    inf = WhisperFactory.create_whisper_inference("faster-whisper", output_dir="/tmp")
    assert inf.device == "modal-gpu"
    assert "torch" not in sys.modules or sys.modules["torch"] is None
```

The last assert is fragile if another test imported torch. Isolate with a subprocess:

```python
import subprocess
import sys


def test_modal_factory_subprocess_has_no_torch():
    code = r"""
import os
os.environ["MODAL_WEB_ENDPOINT_URL"] = "https://mock-endpoint.modal.run"
from modules.whisper.whisper_factory import WhisperFactory
inf = WhisperFactory.create_whisper_inference("faster-whisper", output_dir="/tmp")
assert inf.device == "modal-gpu"
import sys
assert "torch" not in sys.modules
assert "faster_whisper" not in sys.modules
assert "gradio" not in sys.modules
"""
    proc = subprocess.run([sys.executable, "-c", code], cwd=".", capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `TEST_ENV=true python -m pytest backend/tests/unit/test_cpu_import_graph.py::test_requirements_railway_omits_gpu_stack backend/tests/unit/test_railway_import_smoke.py -q`

Expected: FAIL on requirements contents; smoke may fail if factory still pulls torch.

- [ ] **Step 3: Replace `requirements-railway.txt` with**

```
yt-dlp[default,curl-cffi]
ruamel.yaml==0.18.6
modal
python-multipart
celery>=5.3.0
redis>=5.0.0
sqlalchemy>=2.0.0
fastapi>=0.100.0
pydantic>=2.0.0
prometheus-client>=0.19.0
sentry-sdk>=1.39.0
sqlmodel>=0.0.22
python-dotenv
uvicorn>=0.20.0
psycopg2-binary>=2.9.5
google-api-python-client>=2.198.0
cryptography==42.0.5
google-auth-oauthlib==1.2.0
numpy
httpx
requests
soundfile
```

Remove `--extra-index-url https://download.pytorch.org/whl/cpu`.

Add `httpx` if not already pulled transitively; keep it explicit.

- [ ] **Step 4: Run the import-graph, smoke, and a slice of backend unit tests**

Run:

```
TEST_ENV=true DB_URL="sqlite:///:memory:" python -m pytest \
  backend/tests/unit/test_cpu_import_graph.py \
  backend/tests/unit/test_railway_import_smoke.py \
  backend/tests/unit/test_celery_config.py \
  backend/tests/unit/test_batch_router.py \
  backend/tests/unit/test_enqueue.py \
  backend/tests/unit/test_counters.py \
  backend/tests/unit/test_modal_pool_factory.py \
  backend/tests/unit/test_start_workers_script.py \
  backend/tests/unit/test_read_audio_ffmpeg.py \
  backend/tests/unit/test_modal_lifespan_skips_ml.py -q
```

Expected: PASS. Then:

```
python -m compileall app.py backend modules
```

Expected: exit 0.

If smoke fails because `soundfile` pulls nothing related to torch, fix remaining imports shown in the subprocess stderr — do not re-add torch.

- [ ] **Step 5: Lower recycle threshold now that imports are cheap**

In `backend/queue/celery_app.py`, change default `CELERY_WORKER_MAX_TASKS_PER_CHILD` from `"50"` to `"10"`.

Update `test_worker_max_tasks_per_child_defaults_conservative` to expect `10`.

- [ ] **Step 6: Run celery config tests**

Run: `TEST_ENV=true python -m pytest backend/tests/unit/test_celery_config.py -q`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add requirements-railway.txt backend/tests/unit/test_cpu_import_graph.py backend/tests/unit/test_railway_import_smoke.py backend/queue/celery_app.py backend/tests/unit/test_celery_config.py
git commit -m "perf: drop GPU Python stack from Railway image"
```

Deploy this commit to Railway **before** lowering web replica Memory. After RSS drops, set web to 4 GB / 2 vCPU and worker idle to 2 GB / 2 vCPU.

---

### Task 9: Transcribe queue on thread pool; raise DB pool (W3)

**Files:**
- Modify: `scripts/start_workers.sh`
- Modify: `backend/tests/unit/test_start_workers_script.py`
- Modify: `backend/db/db_instance.py`
- Create: `backend/tests/unit/test_db_pool_config.py`
- Modify: `backend/configs/.env.example`

**Interfaces:**
- Consumes: Task 8 slim image (threads still work before that, but RSS win is smaller)
- Produces: batch/idle transcribe workers started with `-P threads`; download and control stay default prefork
- Produces: Postgres engine `pool_size` default `20`, `max_overflow` default `40`, overridable via `DB_POOL_SIZE` / `DB_MAX_OVERFLOW`
- Combined idle worker (`CELERY_COMBINED_WORKER=1`) stays **prefork** because it also consumes `download`

- [ ] **Step 1: Write failing tests**

Append to `backend/tests/unit/test_start_workers_script.py`:

```python
def test_transcribe_worker_uses_threads_pool():
    assert "-P threads" in SCRIPT
    assert "-Q transcribe" in SCRIPT


def test_download_worker_does_not_use_threads_pool():
    download_line = [ln for ln in SCRIPT.splitlines() if "-Q download " in ln][0]
    assert "-P threads" not in download_line
```

Create `backend/tests/unit/test_db_pool_config.py`:

```python
def test_postgres_pool_defaults_allow_threaded_workers(monkeypatch):
    monkeypatch.setenv("DB_URL", "postgresql+psycopg2://u:p@localhost/db")
    monkeypatch.delenv("DB_POOL_SIZE", raising=False)
    monkeypatch.delenv("DB_MAX_OVERFLOW", raising=False)
    import importlib
    import backend.db.db_instance as db
    importlib.reload(db)
    assert db.engine_args["pool_size"] == 20
    assert db.engine_args["max_overflow"] == 40
```

Reload is process-global; run this test file **alone** so other tests do not keep a poisoned engine. If reload is too brittle, extract:

```python
def postgres_pool_kwargs() -> dict:
    return {
        "pool_pre_ping": True,
        "pool_size": int(os.environ.get("DB_POOL_SIZE", "20")),
        "max_overflow": int(os.environ.get("DB_MAX_OVERFLOW", "40")),
    }
```

and unit-test `postgres_pool_kwargs()` without reloading the engine. Prefer the extract.

- [ ] **Step 2: Run tests to verify they fail**

Run: `TEST_ENV=true python -m pytest backend/tests/unit/test_start_workers_script.py::test_transcribe_worker_uses_threads_pool backend/tests/unit/test_db_pool_config.py -q`

Expected: FAIL.

- [ ] **Step 3: Implement thread pool on the transcribe worker only**

In `scripts/start_workers.sh`, in the non-combined branch, change the transcribe line to:

```bash
  celery -A backend.queue.celery_app worker -Q transcribe -P threads -c "$TRANSCRIBE_C" -n transcribe@%h &
```

Leave download and control lines without `-P threads`.

- [ ] **Step 4: Implement DB pool helper in `backend/db/db_instance.py`**

```python
def postgres_pool_kwargs() -> dict:
    return {
        "pool_pre_ping": True,
        "pool_size": int(os.environ.get("DB_POOL_SIZE", "20")),
        "max_overflow": int(os.environ.get("DB_MAX_OVERFLOW", "40")),
    }
```

Replace the postgres `engine_args.update({"pool_size": 10, "max_overflow": 20})` with `engine_args.update(postgres_pool_kwargs())`.

Add to `.env.example`:

```
# DB_POOL_SIZE=20
# DB_MAX_OVERFLOW=40
```

- [ ] **Step 5: Run tests**

Run: `TEST_ENV=true python -m pytest backend/tests/unit/test_start_workers_script.py backend/tests/unit/test_db_pool_config.py backend/tests/unit/test_celery_config.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/start_workers.sh backend/tests/unit/test_start_workers_script.py backend/db/db_instance.py backend/tests/unit/test_db_pool_config.py backend/configs/.env.example
git commit -m "perf: run transcribe Celery queue on threads; enlarge DB pool"
```

Do **not** raise `POOL_PER_ENDPOINT_CAP` or transcribe concurrency to 30 in this task.

---

### Task 10: W5 audio path is deferred (measurement gate, no code unless evidence)

**Files:** none unless the gate trips.

**Interfaces:**
- Consumes: production transcribe worker RSS during one job after Task 8
- Produces: either skip, or MP3-at-download **without** switching to Modal SDK

- [ ] **Step 1: Measure**

After Task 8/9 are on Railway, transcribe one file and note worker RSS delta. If the delta is small versus the torch drop already shipped, **stop**. Do not implement W5.

- [ ] **Step 2: Only if WAV float32 dominates RSS**, implement MP3-at-download as follows (keep HTTP pool):

In `download_drive_file_task`, after `manager.download_and_extract_audio`, run ffmpeg to 32k mono MP3 beside the wav path, store the mp3 path, and have `transcribe_audio_task` pass a **file path string** into `ModalWhisperInference.run` instead of `np.ndarray` from `load_audio_from_wav`. Duration can come from ffprobe. Do not call `modal.Function.from_name`.

- [ ] **Step 3: Commit only if Step 2 ran**

```bash
git commit -m "perf: compress Drive audio to mp3 before Modal HTTP upload"
```

---

## Self-review

**Spec coverage**

- W1 recycle → Task 2, then default 10 in Task 8 Step 5
- W2 idle default + beat always on → Task 3
- Expanded W4 import graph + slim image → Tasks 4–8
- W3 transcribe threads + DB pool → Task 9
- W5 deferred / no SDK pool bypass → Task 10
- Web is the cost lever → Tasks 4–8 plus ops note in Task 8 Step 7
- Rebase onto improvement-v5 → Task 1
- v5 beat/reconcile preserved → Task 3
- Concurrency 30 not in scope → Task 9 constraint

**Placeholder scan:** no TBD/TODO/implement-later steps.

**Type consistency:** `postgres_pool_kwargs()`, `modal_inference_configured()`, `decode_audio_bytes()`, `CELERY_WORKER_MAX_TASKS_PER_CHILD`, `WORKER_PROFILE:-idle` are named the same in tests and implementation steps.
