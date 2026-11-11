#!/bin/sh
# One container, two processes: Flask API (internal, :8000) + Next.js UI (public, :3000, proxies /api to Flask).
# SQLite => a single gunicorn worker (one writer); threads give concurrency, long AI jobs run in their own pool.
set -e
cd /app
gunicorn backend.app.main:app --workers 1 --worker-class gthread --threads 16 \
  --bind 127.0.0.1:8000 --timeout 300 --access-logfile - &
API_PID=$!
trap 'kill $API_PID 2>/dev/null' INT TERM EXIT
cd /app/web
HOSTNAME=0.0.0.0 PORT=3000 API_URL=http://127.0.0.1:8000 exec node server.js
