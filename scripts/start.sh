#!/bin/bash
# 启动 Hermes Gateway + Dashboard

set -e

HERMES_VENV="${HERMES_VENV:-/data01/hermes/venvs/hermes}"
DASHBOARD_HOST="${DASHBOARD_HOST:-0.0.0.0}"
DASHBOARD_PORT="${DASHBOARD_PORT:-9119}"

if [[ -f "${HERMES_VENV}/bin/activate" ]]; then
    source "${HERMES_VENV}/bin/activate"
fi

echo "[$(date '+%F %T')] 启动 gateway..."
hermes gateway start --system

echo "[$(date '+%F %T')] 启动 dashboard..."
hermes dashboard --host "$DASHBOARD_HOST" --port "$DASHBOARD_PORT" --no-open &

echo "[$(date '+%F %T')] 完成"
hermes gateway status --system
