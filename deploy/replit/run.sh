#!/usr/bin/env bash
set -euo pipefail

export APP_ENV=production

python deploy/replit/preflight.py
exec python -m uvicorn shema_platform.experience.production:app \
  --host 0.0.0.0 \
  --port "${PORT:-8080}" \
  --proxy-headers
