#!/usr/bin/env python3
"""Run live curate and freeze output to content/fixtures/.

Usage (requires .env with SLC_API_KEY + LLM):
  python scripts/freeze_live_demo.py --scene "一大—外滩" --out content/fixtures/demo-route-yida.json
  python scripts/freeze_live_demo.py --scene "武康路" --out content/fixtures/demo-route.json

After freeze, run enrich_demo_narratives.py to thicken story cards + sentence_provenance.
"""
from __future__ import annotations

import argparse
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

from redtrip_curator.pipeline import curate  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Live curate → freeze fixture JSON")
    parser.add_argument("--scene", required=True, help="Intent scene, e.g. 一大—外滩")
    parser.add_argument("--message", default="", help="Optional user message")
    parser.add_argument("--duration-min", type=int, default=90)
    parser.add_argument("--out", type=Path, required=True, help="Output fixture path")
    args = parser.parse_args()

    slots = {
        "audience": "成人",
        "scene": args.scene,
        "duration_min": args.duration_min,
        "tone": "轻社交",
        "delivery": "路线",
        "companions": "2人",
        "city": "shanghai",
    }
    message = args.message or f"带朋友走{args.duration_min}分钟，从{args.scene}看城市记忆"
    result = curate(slots=slots, message=message)
    if not result.ok or not result.envelope:
        print("curate failed:", result.reasons, file=sys.stderr)
        return 1

    envelope = dict(result.envelope)
    if result.hongyuan:
        envelope["_demo_hongyuan"] = result.hongyuan
    if result.assumptions:
        existing = list(envelope.get("assumptions") or [])
        envelope["assumptions"] = list(dict.fromkeys([*existing, *result.assumptions]))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(envelope, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.out} evidence={result.evidence_count} narrative={result.narrative}")
    print("next: PYTHONPATH=packages/curator:packages/gate python3 scripts/enrich_demo_narratives.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
