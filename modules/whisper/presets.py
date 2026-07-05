PRESETS = {
    "fast_draft": {
        "model_size": "small",
        "compute_type": "int8",
        "beam_size": 1,
        "vad_filter": True
    },
    "balanced": {
        "model_size": "medium",
        "compute_type": "float16",
        "beam_size": 2,
        "vad_filter": True
    },
    "best_quality": {
        "model_size": "large-v3",
        "compute_type": "float16",
        "beam_size": 5,
        "vad_filter": True
    }
}

def get_preset(name: str) -> dict:
    return PRESETS.get(name.lower(), PRESETS["balanced"])

def resolve_smart_defaults(device: str = "cpu") -> dict:
    if device.lower() == "cpu":
        return {
            "model_size": "small",
            "compute_type": "int8",
            "beam_size": 1
        }
    return {
        "model_size": "large-v2",
        "compute_type": "float16",
        "beam_size": 2
    }
