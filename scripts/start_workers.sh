#!/usr/bin/env bash
set -euo pipefail
DOWNLOAD_C=${CELERY_DOWNLOAD_CONCURRENCY:-4}
TRANSCRIBE_C=${CELERY_TRANSCRIBE_CONCURRENCY:-16}

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
            self.wfile.write(b'{\"status\":\"ok\",\"role\":\"worker\"}')
        else:
            self.send_response(404)
            self.end_headers()
    def log_message(self, *_):
        pass

ThreadingHTTPServer(('0.0.0.0', int(os.environ['PORT'])), HealthHandler).serve_forever()
" &
fi

celery -A backend.queue.celery_app worker -Q download -c "$DOWNLOAD_C" -n download@%h &
celery -A backend.queue.celery_app worker -Q transcribe -c "$TRANSCRIBE_C" -n transcribe@%h &
celery -A backend.queue.celery_app worker -Q orchestrate,reconcile -c 2 -n control@%h &
celery -A backend.queue.celery_app beat &

wait
