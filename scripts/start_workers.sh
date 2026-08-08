#!/usr/bin/env bash
# Celery worker entrypoint for Railway (RAILWAY_SERVICE_NAME=worker).
#
# Profiles (set WORKER_PROFILE on the worker service):
#   idle  — low RAM: one combined worker (concurrency 2), no beat
#   batch — throughput: separate queues, higher concurrency, beat enabled
#
# Override any default via CELERY_* env vars (see backend/configs/.env.example).

set -euo pipefail

PROFILE="${WORKER_PROFILE:-batch}"

case "$PROFILE" in
  idle)
    : "${CELERY_DOWNLOAD_CONCURRENCY:=1}"
    : "${CELERY_TRANSCRIBE_CONCURRENCY:=2}"
    : "${CELERY_CONTROL_CONCURRENCY:=1}"
    : "${CELERY_COMBINED_CONCURRENCY:=2}"
    : "${CELERY_ENABLE_BEAT:=0}"
    : "${CELERY_COMBINED_WORKER:=1}"
    ;;
  batch)
    : "${CELERY_DOWNLOAD_CONCURRENCY:=4}"
    : "${CELERY_TRANSCRIBE_CONCURRENCY:=8}"
    : "${CELERY_CONTROL_CONCURRENCY:=2}"
    : "${CELERY_ENABLE_BEAT:=1}"
    : "${CELERY_COMBINED_WORKER:=0}"
    ;;
  *)
    echo "Unknown WORKER_PROFILE=${PROFILE} (use idle or batch)" >&2
    exit 1
  esac

DOWNLOAD_C="${CELERY_DOWNLOAD_CONCURRENCY}"
TRANSCRIBE_C="${CELERY_TRANSCRIBE_CONCURRENCY}"
CONTROL_C="${CELERY_CONTROL_CONCURRENCY}"
COMBINED_C="${CELERY_COMBINED_CONCURRENCY:-2}"
ENABLE_BEAT="${CELERY_ENABLE_BEAT}"
COMBINED="${CELERY_COMBINED_WORKER}"

echo "start_workers: profile=${PROFILE} combined=${COMBINED} beat=${ENABLE_BEAT} download=${DOWNLOAD_C} transcribe=${TRANSCRIBE_C} control=${CONTROL_C}"

# Railway healthcheck expects HTTP on $PORT; Celery workers do not serve HTTP.
if [ -n "${PORT:-}" ]; then
  python3 -c "
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith('/health'):
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            profile = os.environ.get('WORKER_PROFILE', 'batch')
            body = f'{{\"status\":\"ok\",\"role\":\"worker\",\"profile\":\"{profile}\"}}'
            self.wfile.write(body.encode())
        else:
            self.send_response(404)
            self.end_headers()
    def log_message(self, *_):
        pass

ThreadingHTTPServer(('0.0.0.0', int(os.environ['PORT'])), HealthHandler).serve_forever()
" &
fi

if [ "$COMBINED" = "1" ] || [ "$COMBINED" = "true" ]; then
  celery -A backend.queue.celery_app worker \
    -Q download,transcribe,orchestrate,reconcile \
    -c "$COMBINED_C" \
    -n combined@%h &
else
  celery -A backend.queue.celery_app worker -Q download -c "$DOWNLOAD_C" -n download@%h &
  celery -A backend.queue.celery_app worker -Q transcribe -c "$TRANSCRIBE_C" -n transcribe@%h &
  celery -A backend.queue.celery_app worker -Q orchestrate,reconcile -c "$CONTROL_C" -n control@%h &
fi

if [ "$ENABLE_BEAT" = "1" ] || [ "$ENABLE_BEAT" = "true" ]; then
  celery -A backend.queue.celery_app beat &
fi

wait
