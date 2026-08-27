#!/usr/bin/env bash
set -euo pipefail
cd /opt/redtrip
set -a
source .env
set +a
export PYTHONPATH=packages/library-client:packages/gate:packages/curator
export REDTRIP_POLISH_WORKERS=2
export REDTRIP_POLISH_ESSAYS=0
PY=/opt/redtrip/.venv/bin/python
LOG=/opt/redtrip/logs/yida_polish.log
exec >>"$LOG" 2>&1
echo "=== POLISH START $(date -Is) ==="
"$PY" scripts/polish_demo_yida.py
"$PY" eval/smoke_demo.py
systemctl restart redtrip-api
echo "=== POLISH DONE $(date -Is) ==="
