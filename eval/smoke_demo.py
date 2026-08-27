#!/usr/bin/env python3
"""竞赛演示包烟测：两条冻结演示线必须可核、可溯、过 Gate。

Usage:
  PYTHONPATH=packages/curator:packages/library-client:packages/gate \\
    python eval/smoke_demo.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEMOS = [
    ("wukang", ROOT / "content" / "fixtures" / "demo-route.json", {"min_buri": 6, "all_slc": True}),
    ("yida", ROOT / "content" / "fixtures" / "demo-route-yida.json", {"min_buri": 1, "all_slc": False}),
]


def _check(name: str, path: Path, rules: dict) -> list[str]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw.pop("_demo_hongyuan", None)
    stops = (raw.get("route") or {}).get("stops") or []
    blocks = raw.get("blocks") or []
    sp = raw.get("sentence_provenance") or {}
    errs: list[str] = []

    if len(stops) < 6:
        errs.append(f"{name}: stops < 6 ({len(stops)})")
    buri_n = sum(1 for s in stops if s.get("buri"))
    min_buri = int(rules.get("min_buri") or 6)
    if buri_n < min_buri:
        errs.append(f"{name}: buri 覆盖 {buri_n}/{min_buri}")
    if rules.get("all_slc") and any(s.get("evidence_channel") != "slc" for s in stops):
        errs.append(f"{name}: 存在非 slc evidence_channel")
    scenes = [b for b in blocks if b.get("type") == "scene"]
    cards = [b for b in blocks if b.get("type") == "story_card"]
    if len(scenes) < 6:
        errs.append(f"{name}: scene < 6 ({len(scenes)})")
    if len(cards) < 6:
        errs.append(f"{name}: story_card < 6 ({len(cards)})")
    event_stops = sum(
        1
        for s in stops
        if any(l.get("kind") == "event" for l in (s.get("layers") or []))
    )
    if event_stops < 4:
        errs.append(f"{name}: 含 event 的站 < 4 ({event_stops})")
    per = sp.get("per_stop") or []
    if len(per) < 6:
        errs.append(f"{name}: sentence_provenance.per_stop < 6 ({len(per)})")
    if float(sp.get("coverage_ratio") or 0) < 1.0:
        errs.append(f"{name}: SP coverage_ratio={sp.get('coverage_ratio')}")
    if not raw.get("curator_review"):
        errs.append(f"{name}: 缺 curator_review")
    if not raw.get("narrative_arc"):
        errs.append(f"{name}: 缺 narrative_arc")
    if not all(s.get("act") for s in stops):
        errs.append(f"{name}: 缺 plan.act")

    sys.path[:0] = [
        str(ROOT / "packages" / "gate"),
        str(ROOT / "packages" / "curator"),
        str(ROOT / "packages" / "library-client"),
    ]
    from redtrip_gate.engine import evaluate_envelope

    verdict = evaluate_envelope(raw)
    if not verdict.passed:
        errs.append(f"{name}: Gate 未过: " + "; ".join(verdict.blockers[:5]))
    return errs


def main() -> int:
    all_errs: list[str] = []
    summary: list[str] = []
    for name, path, rules in DEMOS:
        if not path.exists():
            all_errs.append(f"{name}: missing {path.name}")
            continue
        errs = _check(name, path, rules)
        all_errs.extend(errs)
        if not errs:
            summary.append(name)

    if all_errs:
        print("SMOKE_FAIL")
        for e in all_errs:
            print(" -", e)
        return 1
    print("SMOKE_OK", "demos=" + ",".join(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
