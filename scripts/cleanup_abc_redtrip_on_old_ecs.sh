#!/usr/bin/env bash
# 在旧 ECS 47.103.102.36 上执行：卸掉 abc-ai.cn 上的 /redtrip 挂载与相关服务。
# 用法（在旧机上）：
#   sudo bash scripts/cleanup_abc_redtrip_on_old_ecs.sh
set -euo pipefail

CONF="${FASTTOKEN_CONF:-/etc/nginx/conf.d/fasttoken.conf}"
STAMP="$(date +%Y%m%d%H%M%S)"

if [[ ! -f "$CONF" ]]; then
  echo "missing $CONF" >&2
  exit 1
fi

cp -a "$CONF" "${CONF}.bak.${STAMP}"
echo "==> backup ${CONF}.bak.${STAMP}"

python3 - "$CONF" <<'PY'
from pathlib import Path
import re, sys
path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8", errors="replace")
# Remove RedTrip location blocks inserted for pages.dev CORS / API proxy
patterns = [
    re.compile(
        r"\n?#\s*=+\s*RedTrip[\s\S]*?location\s+/redtrip/\s*\{[\s\S]*?\n\}\n?",
        re.I,
    ),
    re.compile(r"\n?location\s+/redtrip/v1/[\s\S]*?\n\}\n?", re.I),
    re.compile(r"\n?location\s+/redtrip/auth/v1/[\s\S]*?\n\}\n?", re.I),
    re.compile(r"\n?location\s+/redtrip/\s*\{\s*return\s+404;\s*\}\n?", re.I),
    re.compile(r"\n?location\s+=\s+/redtrip\s*\{[\s\S]*?\n\}\n?", re.I),
    re.compile(r"\n?location\s+/redtrip/[\s\S]*?\n\}\n?", re.I),
]
new = text
for p in patterns:
    new = p.sub("\n", new)
# collapse excess blank lines
new = re.sub(r"\n{3,}", "\n\n", new)
if new == text:
    print("WARN: no /redtrip blocks matched — inspect", path, "manually")
else:
    path.write_text(new, encoding="utf-8")
    print("OK: stripped /redtrip locations from", path)
PY

nginx -t
systemctl reload nginx || nginx -s reload
echo "==> nginx reloaded"

for svc in redtrip-api redtrip-auth cloudflared; do
  if systemctl list-unit-files "${svc}.service" 2>/dev/null | grep -q "${svc}.service"; then
    systemctl stop "${svc}.service" || true
    systemctl disable "${svc}.service" || true
    echo "==> stopped/disabled ${svc}"
  fi
done

# Optional leftovers listed in 部署清单 §6
for f in \
  /etc/nginx/conf.d/redtrip-direct.conf \
  /etc/nginx/conf.d/redtrip-backend.conf \
  /etc/nginx/conf.d/redtrip-tunnel.conf
do
  if [[ -f "$f" ]]; then
    mv "$f" "${f}.disabled.${STAMP}"
    echo "==> disabled $f"
  fi
done

echo "==> verify (expect non-200 or empty redtrip):"
curl -sI -o /dev/null -w "https://www.abc-ai.cn/redtrip/ → %{http_code}\n" https://www.abc-ai.cn/redtrip/ || true
curl -sI -o /dev/null -w "https://www.abc-ai.cn/redtrip/v1/health → %{http_code}\n" https://www.abc-ai.cn/redtrip/v1/health || true
echo "done. FastToken 本体勿动；仅卸 RedTrip 挂载。"
