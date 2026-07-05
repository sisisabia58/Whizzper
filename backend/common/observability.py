import os
import sentry_sdk
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

# Metrics
TASKS_TOTAL = Counter("whizzper_tasks_total", "Total tasks processed", ["status"])
TASK_DURATION = Histogram("whizzper_task_duration_seconds", "Task duration in seconds")
QUEUE_DEPTH = Gauge("whizzper_queue_depth", "Current queue depth")

def init_sentry():
    dsn = os.environ.get("SENTRY_DSN")
    if dsn:
        sentry_sdk.init(
            dsn=dsn,
            traces_sample_rate=1.0
        )
