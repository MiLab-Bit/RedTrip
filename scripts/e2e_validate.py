"""RedTrip 端到端验证：用真实 LLM 网关跑完整 curate 管线。

不入库：脚本与产出均放 /tmp，避免把网关 key 提交到仓库。
前置：LLM_API_BASE / LLM_API_KEY / LLM_MODEL 通过环境变量传入。
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

# 强制直连（本机 Clash 代理会让网关超时；llm.py 内部 ProxyHandler({}) 也会强制直连）
for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
    os.environ.pop(k, None)
os.environ["NO_PROXY"] = "*"
os.environ["PYTHONUTF8"] = "1"
os.environ.setdefault("REDTRIP_MODE", "indexed")
os.environ.setdefault("REDTRIP_LLM_POLICY", "cloud")  # 强走云端网关

ROOT = Path(__file__).resolve().parents[1]
for p in (
    ROOT / "packages" / "curator",
    ROOT / "packages" / "gate",
    ROOT / "packages" / "library-client",
):
    sys.path.insert(0, str(p))

from redtrip_curator.pipeline import curate  # noqa: E402


# 无 SLC key → 触发 RAG 全量 POI 兜底（这正是修复「空路线/电子垃圾」的关键路径）
class DeadClient:
    def search(self, *a, **k):
        raise RuntimeError("no SLC key -> expect RAG fallback")
    def building_detail(self, *a, **k):
        raise RuntimeError("no SLC key -> expect RAG fallback")


def main() -> int:
    slots = {
        "scene": "外滩 南京东路 历史文化漫步",
        "duration_min": 240,          # 4h，验证 P0-1 修复后长路线不再被门禁误杀
        "tone": "文艺",
        "audience": "深度文化爱好者",
        "companions": "独自",
        "daypart": "day",
    }

    t0 = time.time()
    progress_log: list[str] = []

    def on_progress(stage: str, frac: float, msg: str = "") -> None:
        line = f"[{frac:5.1f}%] {stage}: {msg}"
        progress_log.append(line)
        print(line, flush=True)

    try:
        res = curate(
            slots=slots,
            client=DeadClient(),
            on_progress=on_progress,
        )
    except Exception as e:  # noqa: BLE001
        print("FATAL during curate:", repr(e))
        Path("/tmp/redtrip_e2e_error.txt").write_text(repr(e), encoding="utf-8")
        return 2

    elapsed = time.time() - t0
    env = res.envelope or {}
    route = env.get("route", {}) if isinstance(env, dict) else {}
    stops = route.get("stops", []) if isinstance(route, dict) else []
    story_cards = [
        b for b in (env.get("blocks") or [])
        if isinstance(b, dict) and b.get("type") == "story_card"
    ]

    print("\n==================== E2E SUMMARY ====================")
    print(f"elapsed:            {elapsed:.1f}s")
    print(f"ok:                 {res.ok}")
    print(f"narrative mode:     {res.narrative}  (期望 llm_polish，证明润色真实生效)")
    print(f"evidence_count:     {res.evidence_count}")
    print(f"stops in route:     {len(stops)}")
    print(f"story_cards:        {len(story_cards)}")
    print(f"assumptions:        {res.assumptions}")
    print(f"warnings:           {res.warnings}")
    theme = env.get("theme")
    print(f"theme:              {str(theme)[:80] if theme else None}")

    out = {
        "elapsed_s": round(elapsed, 1),
        "ok": res.ok,
        "narrative": res.narrative,
        "evidence_count": res.evidence_count,
        "stop_count": len(stops),
        "story_card_count": len(story_cards),
        "assumptions": res.assumptions,
        "warnings": res.warnings,
        "envelope": env,
    }
    workspace = ROOT.parents[1]  # .../2026-08-14-09-16-03 (outside repo)
    deliverable = workspace / "redtrip_e2e_result.json"
    deliverable.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"SAVED {deliverable}")
    # 仓库内留一份（不含 key），便于后续比对；已被 .gitignore 忽略
    e2e_dir = ROOT / "content" / "e2e"
    e2e_dir.mkdir(parents=True, exist_ok=True)
    (e2e_dir / "last_run.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("SAVED content/e2e/last_run.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
