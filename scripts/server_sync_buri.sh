#!/usr/bin/env bash
# 在已配置 SLC_API_KEY 的服务器上（/opt/redtrip）一键同步 buri 并刷新 demo-yida。
# 本 Cloud Agent 无 SSH，请在 SWAS 上执行：
#   cd /opt/redtrip && bash scripts/server_sync_buri.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

if [[ -z "${SLC_API_KEY:-}" ]]; then
  echo "ERROR: SLC_API_KEY empty" >&2
  exit 1
fi

export PYTHONPATH="${PYTHONPATH:-}:packages/library-client:packages/gate:packages/curator"
python3 scripts/sync_buri_from_slc.py --district ALL
python3 scripts/refresh_demo_yida_buri.py
PYTHONPATH=packages/gate:packages/curator:packages/library-client python3 eval/smoke_demo.py
PYTHONPATH=packages/gate:packages/curator python3 eval/baseline.py
echo "OK — commit updated points.json / buri-map.json / demo-route-yida.json if improved"
