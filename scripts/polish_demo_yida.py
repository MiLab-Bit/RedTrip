#!/usr/bin/env python3
"""在冻结外滩 demo 的 6 站 scaffold 上做 LLM 逐站润色（不改路线结构）。

前置：先跑 build_demo_yida.py + enrich_demo_narratives.py，保证 Gate 与加厚模板就绪。

Usage:
  REDTRIP_POLISH_WORKERS=2 REDTRIP_POLISH_ESSAYS=0 \\
  PYTHONPATH=packages/library-client:packages/gate:packages/curator \\
    python scripts/polish_demo_yida.py

  python scripts/polish_demo_yida.py --fixture content/fixtures/demo-route-yida.json
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_env = ROOT / ".env"
if _env.exists():
    for line in _env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"'))

for d in ("packages/curator", "packages/library-client", "packages/gate"):
    sys.path.insert(0, str(ROOT / d))

from redtrip_curator.fixture_plan import plan_from_envelope  # noqa: E402
from redtrip_curator.hongyuan import attach_layer3, draw_voice_pack  # noqa: E402
from redtrip_curator.llm import llm_configured  # noqa: E402
from redtrip_curator.pipeline import _finalize_narrative  # noqa: E402
from redtrip_gate import evaluate_envelope  # noqa: E402

DEFAULT_FIXTURE = ROOT / "content" / "fixtures" / "demo-route-yida.json"

# 冻结包级 meta / 路线结构字段：LLM 只润色 story_card，不改主题与通道标注
_PRESERVE_TOP = (
    "theme",
    "logic_line",
    "why_visit",
    "curator_note",
    "scenario",
    "intent",
    "aesthetic",
    "envelope_version",
    "sources",
)
_PRESERVE_STOP = (
    "order",
    "whitelist_id",
    "buri",
    "name",
    "minutes",
    "layers",
    "geo",
    "pitfalls",
    "evidence_channel",
    "act",
)


def _voice_for_polish(backup: dict, seed: int):
    voice = draw_voice_pack(
        tone="轻社交",
        companions="duo",
        duration_min=90,
        seed=seed,
    )
    return attach_layer3(voice, places=["外滩", "一大会址", "兴业路"], tone="轻社交")

def _restore_scaffold(polished: dict, backup: dict) -> None:
    for key in _PRESERVE_TOP:
        if key in backup:
            polished[key] = copy.deepcopy(backup[key])
    backup_stops = {
        int(s.get("order")): s
        for s in (backup.get("route") or {}).get("stops") or []
        if isinstance(s, dict) and s.get("order") is not None
    }
    for stop in (polished.get("route") or {}).get("stops") or []:
        if not isinstance(stop, dict):
            continue
        src = backup_stops.get(int(stop.get("order") or 0))
        if not src:
            continue
        for field in _PRESERVE_STOP:
            if field in src:
                stop[field] = copy.deepcopy(src[field])


def _strip_essays(blocks: list[dict]) -> list[dict]:
    return [b for b in blocks if not (isinstance(b, dict) and b.get("type") == "essay")]


def main() -> int:
    parser = argparse.ArgumentParser(description="LLM polish frozen yida demo on fixed scaffold")
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--seed", type=int, default=42, help="hongyuan draw seed when fixture has no voice")
    args = parser.parse_args()

    if not llm_configured():
        print("LLM not configured (LLM_API_BASE / LLM_API_KEY)", file=sys.stderr)
        return 1
    if not args.fixture.exists():
        print(f"missing fixture: {args.fixture}", file=sys.stderr)
        return 1

    backup = json.loads(args.fixture.read_text(encoding="utf-8"))
    draft = copy.deepcopy(backup)
    # 去掉旧 essay，避免重复 append
    draft["blocks"] = _strip_essays(list(draft.get("blocks") or []))

    plan = plan_from_envelope(draft)
    if len(plan.stops) < 1:
        print("plan has no stops", file=sys.stderr)
        return 1

    voice = _voice_for_polish(backup, args.seed)
    print(f"polish {args.fixture.name}: {len(plan.stops)} stops, workers={os.getenv('REDTRIP_POLISH_WORKERS', '4')}")
    polished, notes, narrative_mode, sp = _finalize_narrative(draft, voice, plan)
    for n in notes:
        print(" ", n)

    _restore_scaffold(polished, backup)
    if voice:
        polished["_demo_hongyuan"] = voice.as_dict()

    verdict = evaluate_envelope(polished)
    if not verdict.passed:
        print("gate failed after polish:", verdict.blockers, file=sys.stderr)
        return 1

    args.fixture.write_text(json.dumps(polished, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    bodies = [
        len(str(b.get("body") or ""))
        for b in polished.get("blocks") or []
        if isinstance(b, dict) and b.get("type") == "story_card"
    ]
    avg = sum(bodies) // max(len(bodies), 1)
    sp_ratio = (polished.get("sentence_provenance") or {}).get("coverage_ratio")
    print(f"OK narrative={narrative_mode} avg_body={avg} sp_ratio={sp_ratio}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
