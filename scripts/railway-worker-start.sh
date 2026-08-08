# Worker service start command for Railway (separate service from web)
# Set the same env vars as web: DB_URL, REDIS_URL, MODAL_WEB_ENDPOINT_URL, etc.
exec bash scripts/start_workers.sh
