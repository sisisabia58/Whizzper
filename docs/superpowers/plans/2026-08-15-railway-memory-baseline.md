# Railway memory baseline (ops, not code)

Capture before any deploy of this branch:

1. Railway Cost by Service: web RAM GB-hours, worker RAM GB-hours.
2. web Settings replica limits (CPU / Memory).
3. worker Settings replica limits (CPU / Memory).
4. worker Variables: WORKER_PROFILE, CELERY_* if set.
5. After web boot, note RSS from Metrics (or `ps` if SSH).

Do not lower web Memory below 4 GB until Task 8 (slim image) is deployed and RSS is confirmed down.
