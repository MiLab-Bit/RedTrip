#!/usr/bin/env bash
# RedTrip sy-realm 发版后 5 分钟自检：health / 演示线 / favicon / 前端 bundle。
# Usage:
#   ./scripts/smoke_sy_realm.sh
#   BASE=https://sy-realm.ltd/redtrip ./scripts/smoke_sy_realm.sh
set -euo pipefail

BASE="${BASE:-https://sy-realm.ltd/redtrip}"
BASE="${BASE%/}"
ROOT_HOST="${ROOT_HOST:-https://sy-realm.ltd}"
fail=0

say() { printf '%s\n' "$*"; }
ok() { say "OK  $*"; }
bad() { say "FAIL $*"; fail=1; }

say "==> smoke against $BASE"

# 1) health
health="$(curl -fsS --max-time 20 "$BASE/v1/health" || true)"
if [[ -n "$health" ]] && echo "$health" | grep -q '"ok"[[:space:]]*:[[:space:]]*true'; then
  ok "health ok=true"
else
  bad "health not ok: ${health:0:200}"
fi

# 2) demo wukang
code="$(curl -sS -o /tmp/redtrip-smoke-wukang.json -w '%{http_code}' --max-time 30 "$BASE/v1/demo/wukang" || true)"
if [[ "$code" == "200" ]] && grep -q '"theme"' /tmp/redtrip-smoke-wukang.json 2>/dev/null; then
  ok "demo/wukang HTTP 200 + theme"
else
  bad "demo/wukang HTTP $code"
fi

# 3) favicon (subpath) — 拒绝 Cloudflare 31B 占位
ico_len="$(curl -sS -o /tmp/redtrip-smoke.ico -w '%{size_download}' --max-time 15 "$BASE/favicon.ico?v=smoke" || echo 0)"
if [[ "${ico_len:-0}" -gt 200 ]]; then
  ok "favicon.ico size=${ico_len}"
else
  bad "favicon.ico too small (${ico_len}) — 可能是缓存占位或未部署"
fi

# 4) index bundle hash
html="$(curl -fsS --max-time 15 "$BASE/" || true)"
bundle="$(printf '%s' "$html" | grep -oE 'assets/index-[^"]+\.js' | head -1 || true)"
if [[ -n "$bundle" ]]; then
  ok "index references $bundle"
else
  bad "index.html missing assets/index-*.js"
fi

# 5) hub favicon (optional)
hub_len="$(curl -sS -o /tmp/hub-smoke.ico -w '%{size_download}' --max-time 15 "$ROOT_HOST/favicon.ico?v=kite1" || echo 0)"
if [[ "${hub_len:-0}" -gt 200 ]]; then
  ok "hub favicon.ico size=${hub_len}"
else
  say "WARN hub favicon small/missing (${hub_len}) — 不影响 /redtrip/"
fi

say "==> done"
if [[ "$fail" -ne 0 ]]; then
  say "smoke FAILED"
  exit 1
fi
say "smoke PASSED"
