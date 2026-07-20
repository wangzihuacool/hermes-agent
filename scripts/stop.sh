#!/bin/bash
# 停止 Hermes Dashboard + Gateway

set -e

HERMES_VENV="${HERMES_VENV:-/data01/hermes/venvs/hermes}"

if [[ -f "${HERMES_VENV}/bin/activate" ]]; then
    source "${HERMES_VENV}/bin/activate"
fi

echo "[$(date '+%F %T')] 停止 dashboard..."
hermes dashboard --stop || true

echo "[$(date '+%F %T')] 停止 gateway..."
hermes gateway stop --system

echo "[$(date '+%F %T')] 完成"
hermes gateway status --system || true
