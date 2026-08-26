#!/usr/bin/env bash
# Deploy Vesta (迹与寻) static SPA to sy-realm.ltd/vesta/
#
# Expects a built Vite dist with base=/vesta/ either from:
#   - SOURCE_DIR (local path containing dist/), or
#   - rebuilding at REMOTE_SRC on the SWAS (needs node/npm there)
#
# Usage:
#   export DEPLOY_HOST=root@YOUR_SWAS_HOST
#   export DEPLOY_SSH_KEY=/path/to/key   # optional
#   # optional: export VESTA_SRC=/path/to/vesta-build  (must contain dist/)
#   bash scripts/deploy_vesta_sy_realm.sh
set -euo pipefail

HOST="${DEPLOY_HOST:?set DEPLOY_HOST e.g. root@your-host}"
REMOTE_ROOT="${DEPLOY_PATH:-/www/wwwroot/sy-realm.ltd/vesta}"
REMOTE_SRC="${REMOTE_VESTA_SRC:-/opt/vesta-build}"
SSH=(ssh -o StrictHostKeyChecking=accept-new)
SCP=(scp -o StrictHostKeyChecking=accept-new)
if [[ -n "${DEPLOY_SSH_KEY:-}" ]]; then
  SSH=(ssh -i "$DEPLOY_SSH_KEY" -o StrictHostKeyChecking=accept-new)
  SCP=(scp -i "$DEPLOY_SSH_KEY" -o StrictHostKeyChecking=accept-new)
fi

if [[ -n "${VESTA_SRC:-}" ]]; then
  [[ -f "$VESTA_SRC/dist/index.html" ]] || {
    echo "missing $VESTA_SRC/dist/index.html — build with base=/vesta/ first" >&2
    exit 1
  }
  echo "==> upload dist from $VESTA_SRC/dist"
  "${SSH[@]}" "$HOST" "mkdir -p '$REMOTE_ROOT'"
  tar czf - -C "$VESTA_SRC/dist" . | "${SSH[@]}" "$HOST" \
    "tar xzf - -C '$REMOTE_ROOT' && chown -R www:www '$REMOTE_ROOT' 2>/dev/null || true"
else
  echo "==> rebuild on remote $REMOTE_SRC (base=/vesta/)"
  "${SSH[@]}" "$HOST" "bash -s" <<REMOTE
set -euo pipefail
cd '$REMOTE_SRC'
python3 - <<'PY'
from pathlib import Path
p = Path("vite.config.ts")
t = p.read_text()
if "base: '/vesta/'" not in t:
    t2 = t.replace("base: '/GitHub-Headhunter/'", "base: '/vesta/'")
    if t2 == t:
        raise SystemExit("could not set vite base to /vesta/")
    p.write_text(t2)
print("vite base ok")
PY
npm install
npm run build
mkdir -p '$REMOTE_ROOT'
rm -rf '${REMOTE_ROOT:?}/'*
cp -a dist/. '$REMOTE_ROOT'/
chown -R www:www '$REMOTE_ROOT' 2>/dev/null || true
REMOTE
fi

echo "==> ensure nginx locations (idempotent)"
"${SSH[@]}" "$HOST" "bash -s" <<'REMOTE'
set -euo pipefail
python3 <<'PY'
from pathlib import Path

BLOCK = """
    location = /vesta { return 301 /vesta/; }

    location /vesta/ {
        alias /www/wwwroot/sy-realm.ltd/vesta/;
        index index.html;
        try_files $uri $uri/ @vesta_spa;
    }

    location @vesta_spa {
        rewrite ^ /vesta/index.html last;
    }

    location = /vesta/index.html {
        alias /www/wwwroot/sy-realm.ltd/vesta/index.html;
    }
"""

def ensure(path: Path) -> None:
    text = path.read_text()
    if "location /vesta/" in text:
        print("ok", path)
        return
    needle = "\n    location / {"
    if needle not in text:
        raise SystemExit(f"cannot patch {path}: no location /")
    path.write_text(text.replace(needle, BLOCK + needle, 1))
    print("patched", path)

for p in (
    Path("/etc/nginx/conf.d/sy-realm.ltd.conf"),
    Path("/etc/nginx/conf.d/00-redtrip-default.conf"),
):
    if p.exists():
        ensure(p)
PY
nginx -t
systemctl reload nginx || nginx -s reload
REMOTE

echo "==> done. Open https://sy-realm.ltd/vesta/"
