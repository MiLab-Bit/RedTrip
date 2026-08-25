#!/usr/bin/env python3
"""竞赛演示包烟测：冻结武康线必须可核、可溯、过 Gate。

Usage:
  PYTHONPATH=packages/curator:packages/library-client:packages/gate \\
    python eval/smoke_demo.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "content" / "fixtures" / "demo-route.json"


def main() -> int:
    raw = json.loads(DEMO.read_text(encoding="utf-8"))
    raw.pop("_demo_hongyuan", None)
    stops = (raw.get("route") or {}).get("stops") or []
    blocks = raw.get("blocks") or []
    sp = raw.get("sentence_provenance") or {}
    errs: list[str] = []

    if len(stops) < 6:
        errs.append(f"stops < 6 ({len(stops)})")
    buri_n = sum(1 for s in stops if s.get("buri"))
    if buri_n < 6:
        errs.append(f"buri 覆盖 {buri_n}/6")
    if any(s.get("evidence_channel") != "slc" for s in stops):
        errs.append("存在非 slc evidence_channel")
    scenes = [b for b in blocks if b.get("type") == "scene"]
    cards = [b for b in blocks if b.get("type") == "story_card"]
    if len(scenes) < 6:
        errs.append(f"scene < 6 ({len(scenes)})")
    if len(cards) < 6:
        errs.append(f"story_card < 6 ({len(cards)})")
    event_stops = sum(
        1
        for s in stops
        if any(l.get("kind") == "event" for l in (s.get("layers") or []))
    )
    if event_stops < 4:
        errs.append(f"含 event 的站 < 4 ({event_stops})")
    per = sp.get("per_stop") or []
    if len(per) < 6:
        errs.append(f"sentence_provenance.per_stop < 6 ({len(per)})")
    if float(sp.get("coverage_ratio") or 0) < 1.0:
        errs.append(f"SP coverage_ratio={sp.get('coverage_ratio')}")
    if not raw.get("curator_review"):
        errs.append("缺 curator_review")
    if not raw.get("narrative_arc"):
        errs.append("缺 narrative_arc")

    sys.path[:0] = [
        str(ROOT / "packages" / "gate"),
        str(ROOT / "packages" / "curator"),
        str(ROOT / "packages" / "library-client"),
    ]
    from redtrip_gate.engine import evaluate_envelope

    verdict = evaluate_envelope(raw)
    if not verdict.passed:
        errs.append("Gate 未过: " + "; ".join(verdict.blockers[:5]))

    if errs:
        print("SMOKE_FAIL")
        for e in errs:
            print(" -", e)
        return 1
    print(
        "SMOKE_OK",
        f"stops={len(stops)} buri={buri_n} scenes={len(scenes)} "
        f"event_stops={event_stops} sp_ratio={sp.get('coverage_ratio')}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
