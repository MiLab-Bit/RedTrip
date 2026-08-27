#!/usr/bin/env python3
"""量化基线：套话率、溯源率、Gate 一次过率、buri 覆盖率。

Usage:
  PYTHONPATH=packages/curator:packages/library-client:packages/gate \\
    python eval/baseline.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = ("必去", "不容错过", "打卡圣地", "绝绝子", "宝藏")
DEMOS = [
    ROOT / "content" / "fixtures" / "demo-route.json",
    ROOT / "content" / "fixtures" / "demo-route-yida.json",
]
WHITELIST = ROOT / "content" / "whitelist" / "points.json"


def _text_blob(env: dict) -> str:
    parts: list[str] = []
    for key in ("theme", "logic_line", "curator_note", "why_visit"):
        parts.append(str(env.get(key) or ""))
    for b in env.get("blocks") or []:
        if isinstance(b, dict):
            parts.append(str(b.get("body") or ""))
            parts.append(str(b.get("title") or ""))
    return "\n".join(parts)


def _cliche_hits(blob: str) -> list[str]:
    return [w for w in FORBIDDEN if w in blob]


def buri_coverage() -> dict:
    doc = json.loads(WHITELIST.read_text(encoding="utf-8"))
    points = doc.get("points") or []
    total = len(points)
    with_buri = sum(1 for p in points if p.get("buri"))
    wutong = [p for p in points if p.get("district_tag") == "梧桐区"]
    wutong_buri = sum(1 for p in wutong if p.get("buri"))
    yida = [p for p in points if p.get("district_tag") == "一大周边"]
    yida_buri = sum(1 for p in yida if p.get("buri"))
    return {
        "whitelist_total": total,
        "whitelist_buri": with_buri,
        "whitelist_buri_pct": round(100 * with_buri / total, 1) if total else 0,
        "wutong_total": len(wutong),
        "wutong_buri": wutong_buri,
        "wutong_buri_pct": round(100 * wutong_buri / len(wutong), 1) if wutong else 0,
        "yida_total": len(yida),
        "yida_buri": yida_buri,
    }


def eval_demo(path: Path) -> dict:
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw.pop("_demo_hongyuan", None)
    blob = _text_blob(raw)
    cliche = _cliche_hits(blob)
    sp = raw.get("sentence_provenance") or {}
    factual = int(sp.get("factual_sentences") or 0)
    aligned = int(sp.get("aligned_factual") or 0)
    sp_ratio = float(sp.get("coverage_ratio") or 0)
    stops = (raw.get("route") or {}).get("stops") or []
    buri_n = sum(1 for s in stops if s.get("buri"))
    slc_n = sum(1 for s in stops if s.get("evidence_channel") == "slc")

    sys.path[:0] = [
        str(ROOT / "packages" / "gate"),
        str(ROOT / "packages" / "curator"),
        str(ROOT / "packages" / "library-client"),
    ]
    from redtrip_gate.engine import evaluate_envelope

    verdict = evaluate_envelope(raw)
    return {
        "file": path.name,
        "theme": raw.get("theme"),
        "stops": len(stops),
        "buri_stops": buri_n,
        "slc_stops": slc_n,
        "cliche_hits": cliche,
        "cliche_rate": len(cliche),
        "sp_factual": factual,
        "sp_aligned": aligned,
        "sp_ratio": sp_ratio,
        "gate_passed": verdict.passed,
        "gate_blockers": len(verdict.blockers),
        "gate_warnings": len(verdict.warnings),
    }


def main() -> int:
    cov = buri_coverage()
    demos = [eval_demo(p) for p in DEMOS if p.exists()]
    report = {"buri_coverage": cov, "demos": demos}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    bad = []
    for d in demos:
        if not d["gate_passed"]:
            bad.append(f"{d['file']} gate fail")
        if d["cliche_rate"]:
            bad.append(f"{d['file']} cliche={d['cliche_hits']}")
    if bad:
        print("BASELINE_FAIL", "; ".join(bad))
        return 1
    print("BASELINE_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
