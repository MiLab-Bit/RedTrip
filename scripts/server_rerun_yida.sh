#!/usr/bin/env bash
# 在 SWAS /opt/redtrip 上一键：同步上图 buri →  live LLM 策展冻结外滩 demo → 加厚叙事 → 冒烟。
#
#   cd /opt/redtrip && bash scripts/server_rerun_yida.sh
#
# 需要 .env：SLC_API_KEY、LLM_API_BASE、LLM_API_KEY、LLM_MODEL
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
LOG="${ROOT}/logs/server_rerun_yida.log"
mkdir -p "${ROOT}/logs"
PY="${ROOT}/.venv/bin/python"

exec > >(tee -a "$LOG") 2>&1
echo "=== server_rerun_yida $(date -Is) ==="

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

for v in SLC_API_KEY LLM_API_BASE LLM_API_KEY; do
  if [[ -z "${!v:-}" ]]; then
    echo "ERROR: $v empty" >&2
    exit 1
  fi
done

export PYTHONPATH=packages/library-client:packages/gate:packages/curator

echo "-- sync buri from SLC --"
"$PY" scripts/sync_buri_from_slc.py --district ALL
"$PY" scripts/refresh_demo_yida_buri.py

echo "-- live curate + freeze 一大—外滩 --"
"$PY" scripts/freeze_live_demo.py \
  --scene "一大—外滩" \
  --message "带朋友走半天，从一大到外滩，看城市记忆与建筑天际线" \
  --out content/fixtures/demo-route-yida.json

echo "-- enrich narratives --"
PYTHONPATH=packages/library-client:packages/gate:packages/curator "$PY" scripts/enrich_demo_narratives.py

echo "-- LLM polish yida demo --"
REDTRIP_POLISH_WORKERS=2 REDTRIP_POLISH_ESSAYS=0 PYTHONPATH=packages/library-client:packages/gate:packages/curator "$PY" scripts/polish_demo_yida.py

echo "-- smoke + baseline --"
PYTHONPATH=packages/library-client:packages/gate:packages/curator "$PY" eval/smoke_demo.py
PYTHONPATH=packages/library-client:packages/gate:packages/curator "$PY" eval/baseline.py

echo "-- restart API --"
systemctl restart redtrip-api
sleep 2
curl -sf "http://127.0.0.1:8799/v1/health?probe=true" | head -c 400
echo
echo "OK — demo-route-yida.json refreshed at $(date -Is)"
