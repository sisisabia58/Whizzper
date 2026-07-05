class ProgressReporter:
    STAGE_WEIGHTS = {
        "queued": 0.0,
        "downloading": 0.05,
        "bgm_separation": 0.15,
        "vad": 0.10,
        "transcribing": 0.55,
        "diarizing": 0.10,
        "writing_output": 0.05,
        "done": 1.0,
        "failed": 0.0
    }

    def __init__(self):
        self.last_percent = 0

    def calculate_progress(self, stage_name: str, stage_fraction: float) -> int:
        stages_keys = list(self.STAGE_WEIGHTS.keys())
        if stage_name not in self.STAGE_WEIGHTS:
            return self.last_percent

        stage_idx = stages_keys.index(stage_name)
        base_weight = sum([self.STAGE_WEIGHTS[k] for k in stages_keys[:stage_idx]])
        current_weight = self.STAGE_WEIGHTS[stage_name] * max(0.0, min(1.0, stage_fraction))
        
        percent = int((base_weight + current_weight) * 100)
        percent = max(self.last_percent, min(100, percent))
        self.last_percent = percent
        return percent

    def calculate_eta(self, elapsed_seconds: float, progress_percent: int) -> int | None:
        if progress_percent <= 0 or progress_percent >= 100 or elapsed_seconds <= 0:
            return None
        total_estimated = (elapsed_seconds / progress_percent) * 100
        eta = int(total_estimated - elapsed_seconds)
        return max(0, eta)
