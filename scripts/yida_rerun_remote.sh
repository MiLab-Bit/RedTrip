#!/usr/bin/env bash
# 服务器：重建外滩演示 fixture（结构正确）+ buri 同步 + 加厚 + 冒烟
set -euo pipefail
cd /opt/redtrip
set -a
source .env
set +a
export PYTHONPATH=packages/library-client:packages/gate:packages/curator
PY=/opt/redtrip/.venv/bin/python
LOG=/opt/redtrip/logs/yida_refresh.log
exec >>"$LOG" 2>&1
echo "=== START $(date -Is) ==="

echo "-- build demo scaffold --"
"$PY" scripts/build_demo_yida.py

echo "-- sync buri --"
"$PY" scripts/sync_buri_from_slc.py --district ALL
"$PY" scripts/refresh_demo_yida_buri.py

echo "-- enrich narratives --"
"$PY" scripts/enrich_demo_narratives.py

echo "-- LLM polish (fixed 6-stop scaffold) --"
REDTRIP_POLISH_WORKERS=2 REDTRIP_POLISH_ESSAYS=0 "$PY" scripts/polish_demo_yida.py

echo "-- smoke --"
"$PY" eval/smoke_demo.py

systemctl restart redtrip-api
echo "=== DONE $(date -Is) ==="
