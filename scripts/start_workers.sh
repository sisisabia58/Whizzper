#!/usr/bin/env bash
set -euo pipefail
DOWNLOAD_C=${CELERY_DOWNLOAD_CONCURRENCY:-4}
TRANSCRIBE_C=${CELERY_TRANSCRIBE_CONCURRENCY:-16}

celery -A backend.queue.celery_app worker -Q download -c "$DOWNLOAD_C" -n download@%h &
celery -A backend.queue.celery_app worker -Q transcribe -c "$TRANSCRIBE_C" -n transcribe@%h &
celery -A backend.queue.celery_app worker -Q orchestrate,reconcile -c 2 -n control@%h &
celery -A backend.queue.celery_app beat -n beat@%h &

wait
