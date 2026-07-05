import pytest
from modules.whisper.presets import PRESETS, get_preset, resolve_smart_defaults

def test_three_presets_defined():
    assert "fast_draft" in PRESETS
    assert "balanced" in PRESETS
    assert "best_quality" in PRESETS

def test_get_preset_returns_correct_params():
    p = get_preset("fast_draft")
    assert p["model_size"] == "small"
    assert p["compute_type"] == "int8"
    assert p["beam_size"] == 1

def test_resolve_smart_defaults_cpu():
    defaults = resolve_smart_defaults(device="cpu")
    assert defaults["compute_type"] == "int8"
    assert defaults["model_size"] == "small"

def test_resolve_smart_defaults_gpu():
    defaults = resolve_smart_defaults(device="cuda")
    assert defaults["compute_type"] == "float16"
    assert defaults["model_size"] == "large-v2"
