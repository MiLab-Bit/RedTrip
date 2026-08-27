---
name: redtrip-harness
description: >-
  RedTrip code-quality harness for the Shanghai red-study curator demo.
  Use when writing or changing RedTrip apps/web, apps/api, packages/*,
  contracts, curator pipeline, gates, fixtures, or MCP/library-client code.
  Enforces contract-first development, evidence-before-narrative, demo stability,
  Haipai design tokens, and verification before claiming done.
---

# RedTrip Harness

## When this skill applies

Any implementation work under `RedTrip/`. Read this fully before large edits.

## Non-negotiables

1. **Contract-first**  
   Change `packages/contracts` (Zod) before UI or API shapes. `RouteEnvelope` is the only Web↔API boundary.

2. **Evidence before narrative**  
   Never invent years, people, addresses, or events. Missing facts → `暂无数据支撑` / `gaps`. LLM may only rewrite claims that already have `source.dataset` + `source.record_id`.

3. **Web never holds secrets**  
   `SLC_API_KEY` only in API process env. Browser talks only to `apps/api`.

4. **NG-10**  
   Geo fields stay `lat/lng/coord_source/precision`. Renderers must not branch business logic on `coord_source`.

5. **Haipai 6 colors only**  
   `#33333A` `#B9824F` `#7C8A8D` `#EDE4D3` `#A8322A` `#F2EBDD`. No purple SaaS defaults, no efficiency copy（一键/省事/省时）.

6. **Demo path stays alive**  
   Prefer `snapshot` / fixtures when upstream is flaky. Do not break the click-through: brief → map → walk → source → done.

## Implementation loop (mandatory)

```
1. Read Doc/14-dev-tasks.md — know which W-task you are on
2. Smallest change that moves the demo forward
3. Verify (below) before saying done
4. Update Doc only if architecture or task status changed
```

## Verify before "done"

For **web** changes:

- Typecheck / build does not error
- Manual: load app → generate/load demo route → open ≥1 stop → open source drawer
- No new seventh brand color in CSS

For **api/curator** changes:

- `GET /v1/health` works or explicit skip reason
- Envelope parses with `RouteEnvelopeSchema`
- Gate rules not bypassed

For **data/MCP** changes:

- Prefer ASCII `buri`/`uri` on hot path
- Document NO_PROXY need if TLS fails
- Do not commit real API keys

## File ownership

| Area | Own | Do not |
|---|---|---|
| `apps/web` | UI, FSM, map, cards | Call library.sh.cn / hold Key |
| `apps/api` | HTTP, wire curator | Hand-written history prose |
| `packages/curator` | Pipeline stages | 3D/geo rendering |
| `packages/library-client` | SLC HTTP | Copy tone |
| `packages/gate` | Block rules | Soft-pass missing sources |
| `content/` | whitelist + fixtures | Runtime guesses for open hours |

## Copy red lines (UI + generated)

Forbidden: 一键生成, 省时, 省事, 口号体, 表态动员, 神剧化.  
Preferred: concrete detail + human situation; second person on story cards.

## Architecture pointers

- `Doc/13-architecture-freeze.md`
- `Doc/06-api-contracts.md`
- `Doc/11-mcp-integration.md`
- `Doc/12-frontend-architecture.md`
- `Doc/14-dev-tasks.md`
