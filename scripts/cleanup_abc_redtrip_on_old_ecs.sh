#!/usr/bin/env bash
# 在旧 ECS 上彻底卸掉 abc-ai.cn 上的 RedTrip：nginx 挂载、systemd 单元、模板。
# 不删 /opt/redtrip 数据目录（需手动确认后再 rm -rf）。
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
# Strip any RedTrip locations (proxy, auth, hard 404)
patterns = [
    re.compile(
        r"\n?#\s*=+\s*RedTrip[\s\S]*?location\s+/redtrip/\s*\{[\s\S]*?\n\}\n?",
        re.I,
    ),
    re.compile(
        r"\n?\s*#\s*RedTrip retired[\s\S]*?location\s+\^~\s+/redtrip/\s*\{[^}]*\}\n?",
        re.I,
    ),
    re.compile(r"\n?location\s+/redtrip/v1/[\s\S]*?\n\}\n?", re.I),
    re.compile(r"\n?location\s+/redtrip/auth/v1/[\s\S]*?\n\}\n?", re.I),
    re.compile(r"\n?location\s+\^~\s+/redtrip/\s*\{[^}]*\}\n?", re.I),
    re.compile(r"\n?location\s+/redtrip/\s*\{\s*return\s+404;\s*\}\n?", re.I),
    re.compile(r"\n?location\s+=\s+/redtrip\s*\{[^}]*\}\n?", re.I),
    re.compile(r"\n?location\s+/redtrip/[\s\S]*?\n\}\n?", re.I),
]
new = text
for p in patterns:
    new = p.sub("\n", new)
new = re.sub(r"\n{3,}", "\n\n", new)
if new != text:
    path.write_text(new, encoding="utf-8")
    print("OK: stripped /redtrip locations from", path)
else:
    print("OK: no /redtrip locations left in", path)
PY

nginx -t
systemctl reload nginx || nginx -s reload
echo "==> nginx reloaded (no dedicated /redtrip; may fall through to FastToken)"

for svc in redtrip-api redtrip-auth; do
  systemctl stop "${svc}.service" 2>/dev/null || true
  systemctl disable "${svc}.service" 2>/dev/null || true
  for d in /etc/systemd/system /usr/lib/systemd/system /lib/systemd/system; do
    if [[ -f "$d/${svc}.service" ]]; then
      mv "$d/${svc}.service" "$d/${svc}.service.removed.${STAMP}"
      echo "==> removed $d/${svc}.service"
    fi
  done
done
systemctl daemon-reload
systemctl reset-failed redtrip-api redtrip-auth 2>/dev/null || true

for f in \
  /etc/nginx/conf.d/redtrip-direct.conf \
  /etc/nginx/conf.d/redtrip-backend.conf \
  /etc/nginx/conf.d/redtrip-tunnel.conf
do
  if [[ -f "$f" ]]; then
    mv "$f" "${f}.removed.${STAMP}"
    echo "==> removed $f"
  fi
done
if [[ -d /etc/nginx/redtrip-templates ]]; then
  mv /etc/nginx/redtrip-templates "/etc/nginx/redtrip-templates.removed.${STAMP}"
  echo "==> removed /etc/nginx/redtrip-templates"
fi

echo "==> verify (expect no redtrip unit; /redtrip may be FastToken 200)"
systemctl list-unit-files 2>/dev/null | grep redtrip || echo "no redtrip unit files"
curl -sI -o /dev/null -w "https://www.abc-ai.cn/redtrip/ → %{http_code}\n" https://www.abc-ai.cn/redtrip/ || true
echo "done. FastToken 本体勿动。"
echo "optional: rm -rf /opt/redtrip   # only after confirming accounts live on sy-realm"
