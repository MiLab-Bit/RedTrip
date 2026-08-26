# Vesta｜迹与寻 · sy-realm.ltd

Vesta is a separate static SPA (Vite/React, GitHub Trace engine). It lives alongside RedTrip on the same SWAS / Cloudflare tunnel.

| Item | Value |
|------|--------|
| URL | `https://sy-realm.ltd/vesta/` |
| Web root | `/www/wwwroot/sy-realm.ltd/vesta/` |
| Source on SWAS | `/opt/vesta-build` (vite `base: '/vesta/'`) |
| Nginx | `sy-realm.ltd.conf` + `00-redtrip-default.conf` — SPA locations under `/vesta/` |

Redeploy:

```bash
export DEPLOY_HOST=root@YOUR_SWAS_HOST
export DEPLOY_SSH_KEY=/path/to/key   # if needed
# either upload a local dist:
export VESTA_SRC=/path/to/vesta-build
bash scripts/deploy_vesta_sy_realm.sh
# or rebuild on the server (omit VESTA_SRC)
```

Notes:

- Pure frontend; optional `VITE_GITHUB_TOKEN` / `VITE_GEMINI_API_KEY` are build-time only.
- Old ECS may still hold a copy under `/opt/vesta-build`; production serving is on `sy-realm.ltd` only.
- Do not mount `/vesta` on `abc-ai.cn` (FastToken host).
