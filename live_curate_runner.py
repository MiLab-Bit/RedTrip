"""Live end-to-end runner for RedTrip curate().

Loads .env (SLC_API_KEY + LLM config), then calls the real
``curate()`` pipeline against the live Shanghai Library (上图) open data
API plus an OpenAI-compatible LLM channel. Saves the full envelope + artifacts
to a JSON file and prints a concise summary.

Usage:
    python live_curate_runner.py
    python live_curate_runner.py --scene "武康路—华山路一带" --message "周末想带朋友走走武康路"
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT  # this file lives at RedTrip/

# --- load .env into process env (llm.py / SlcClient read os.getenv) ---
_env_path = REPO / ".env"
if _env_path.exists():
    for _line in _env_path.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if not _line or _line.startswith("#") or "=" not in _line:
            continue
        _k, _v = _line.split("=", 1)
        os.environ.setdefault(_k.strip(), _v.strip().strip('"'))

for _d in ("packages/curator", "packages/library-client", "packages/gate"):
    sys.path.insert(0, str(REPO / _d))

from redtrip_curator.pipeline import curate  # noqa: E402


def _summarize(result, elapsed_s: float) -> dict:
    out: dict[str, object] = {
        "ok": result.ok,
        "mode": result.mode,
        "evidence_count": result.evidence_count,
        "narrative": result.narrative,
        "assumptions": result.assumptions,
        "reasons": result.reasons,
        "warnings": result.warnings,
        "elapsed_s": round(elapsed_s, 1),
    }
    if result.envelope is not None:
        out["envelope"] = result.envelope
    if result.artifacts is not None:
        out["artifacts"] = result.artifacts.to_dict()
    return out


def _print_console(out: dict, elapsed_s: float | None, out_path: Path) -> None:
    """Consume the serialized ``out`` dict (str keys) for robust printing."""
    print("\n" + "=" * 60)
    print("LIVE CURATE — RESULT")
    print("=" * 60)
    print(f"ok={out.get('ok')}  mode={out.get('mode')}  narrative={out.get('narrative')}")
    print(f"evidence_count={out.get('evidence_count')}  "
          f"elapsed={out.get('elapsed_s', elapsed_s)}s")
    art = out.get("artifacts") or {}
    if art:
        th = art.get("theme", {})
        print("\n[G1 Theme]")
        print("  title        :", th.get("title"))
        print("  open_question:", th.get("open_question"))
        print("  scope_note   :", th.get("scope_note"))
        for ax in th.get("research_axes", []):
            print(f"   - axis[{ax.get('axis')}] -> {ax.get('evidence_cluster_ids')}")
            print(f"       {ax.get('hypothesis')}")
        eg = art.get("evidence_graph", {})
        print("\n[G2 EvidenceGraph]")
        print("  clusters:", [(c.get("id"), len(c.get("facts", []))) for c in eg.get("clusters", [])])
        print("  joins   :", len(eg.get("joins", [])))
        cov = eg.get("coverage", {})
        print("  coverage:", cov.get("uri_coverage"), "dims:", cov.get("dimensions_covered"))
        na = art.get("narrative_arc", {})
        print("\n[G3 NarrativeArc]")
        print("  nodes:", [(n.get("stop_index"), n.get("role")) for n in na.get("nodes", [])])
        print("  tension:", na.get("tension_curve"))
        pr = art.get("provenance", {})
        print("\n[G4 provenance (layer-level)]")
        print(f"  assertions={pr.get('total_assertions')} "
              f"aligned={pr.get('aligned_assertions')} ratio={pr.get('coverage_ratio')}")
        sp = art.get("sentence_provenance")
        if sp:
            print("\n[G4-sentence (post-polish)]")
            print(f"  stops={len(sp.get('per_stop', []))} factual={sp.get('factual_sentences')}"
                  f" aligned={sp.get('aligned_factual')} ratio={sp.get('coverage_ratio')}")
    if out.get("warnings"):
        print("\n[warnings]")
        for w in out["warnings"][:8]:
            print("  -", w)
    if out.get("reasons"):
        print("\n[reasons/blockers]")
        for r in out["reasons"][:8]:
            print("  -", r)
    print("\n[saved]", out_path)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", default="武康路—华山路一带")
    ap.add_argument("--message", default="周末想带朋友走走武康路，感受老上海梧桐区里的文人气息和建筑故事")
    ap.add_argument("--duration-min", type=int, default=90)
    ap.add_argument("--tone", default="轻社交")
    ap.add_argument("--companions", default="2人")
    ap.add_argument("--audience", default="成人")
    ap.add_argument("--delivery", default="路线")
    ap.add_argument(
        "--from-file",
        default=None,
        help="跳过 live curate，直接读取并展示已保存的 JSON 结果",
    )
    args = ap.parse_args()

    if args.from_file:
        fp = Path(args.from_file)
        if not fp.is_absolute():
            fp = REPO / fp
        data = json.loads(fp.read_text(encoding="utf-8"))
        _print_console(data, data.get("elapsed_s"), fp)
        return 0

    slots = {
        "audience": args.audience,
        "scene": args.scene,
        "duration_min": args.duration_min,
        "tone": args.tone,
        "delivery": args.delivery,
        "companions": args.companions,
    }
    print(f"[runner] scene={args.scene!r} message={args.message!r}")
    print(f"[runner] SLC_API_KEY set={bool(os.getenv('SLC_API_KEY'))} "
          f"LLM_API_BASE={os.getenv('LLM_API_BASE')} model={os.getenv('LLM_MODEL')}")

    t0 = time.time()
    try:
        result = curate(slots=slots, message=args.message)
    except Exception:  # noqa: BLE001
        elapsed = time.time() - t0
        tb = traceback.format_exc()
        print("[runner] curate() raised:\n", tb)
        err_path = REPO / "live_curate_error_2026-08-09.txt"
        err_path.write_text(tb, encoding="utf-8")
        print("[saved error]", err_path)
        return 2
    elapsed = time.time() - t0

    out = _summarize(result, elapsed)
    out_path = REPO / "live_curate_output_2026-08-09.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    _print_console(out, elapsed, out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
