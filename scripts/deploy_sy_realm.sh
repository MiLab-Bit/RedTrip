#!/usr/bin/env bash
# Deploy RedTrip web + API to sy-realm.ltd/redtrip on SWAS 139.224.163.203
# Requires: SSH access (key or password), node/pnpm for local build optional.
#
# Usage:
#   export DEPLOY_HOST=root@139.224.163.203
#   export DEPLOY_PATH=/www/wwwroot/sy-realm.ltd/redtrip   # 宝塔站点根下的子目录
#   ./scripts/deploy_sy_realm.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HOST="${DEPLOY_HOST:-root@139.224.163.203}"
REMOTE_ROOT="${DEPLOY_PATH:-/www/wwwroot/sy-realm.ltd/redtrip}"
API_DIR="${REMOTE_API:-/opt/redtrip}"

echo "==> build web (base=/redtrip/)"
cd "$ROOT"
pnpm install --frozen-lockfile
pnpm --filter @redtrip/contracts build
VITE_BASE=/redtrip/ VITE_API_BASE=/redtrip pnpm --filter @redtrip/web build

DIST="$ROOT/apps/web/dist"
if [[ ! -d "$DIST" ]]; then
  echo "missing $DIST" >&2
  exit 1
fi

echo "==> rsync web → $HOST:$REMOTE_ROOT/"
ssh "$HOST" "mkdir -p '$REMOTE_ROOT'"
rsync -az --delete "$DIST/" "$HOST:$REMOTE_ROOT/"

echo "==> sync API source → $HOST:$API_DIR (if present)"
if ssh "$HOST" "test -d '$API_DIR'"; then
  rsync -az \
    --exclude '.venv' --exclude '__pycache__' --exclude '.curate_cache.json' \
    --exclude 'node_modules' --exclude '.git' \
    "$ROOT/" "$HOST:$API_DIR/"
  ssh "$HOST" "cd '$API_DIR' && (systemctl restart redtrip-api || supervisorctl restart redtrip || true)"
else
  echo "WARN: $API_DIR not found on remote — skipped API sync"
fi

echo "==> done. Open https://sy-realm.ltd/redtrip/"
echo "    Ensure nginx location /redtrip/ serves $REMOTE_ROOT and proxies /redtrip/v1 → 127.0.0.1:8799"
