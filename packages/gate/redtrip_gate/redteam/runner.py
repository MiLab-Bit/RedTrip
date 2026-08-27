from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from ..engine import evaluate_envelope

ROOT = Path(__file__).resolve().parents[4]  # RedTrip/
CASES_PATH = Path(__file__).with_name("cases.json")
FIXTURES = {
    "curated-live": ROOT / "content" / "fixtures" / "curated-live.json",
    "demo-route": ROOT / "content" / "fixtures" / "demo-route.json",
}


def _get_path(obj: Any, path: str) -> Any:
    cur = obj
    for part in path.split("."):
        if part.isdigit():
            cur = cur[int(part)]
        else:
            cur = cur[part]
    return cur


def _set_path(obj: Any, path: str, value: Any) -> None:
    parts = path.split(".")
    cur = obj
    for part in parts[:-1]:
        if part.isdigit():
            cur = cur[int(part)]
        else:
            cur = cur[part]
    last = parts[-1]
    if last.isdigit():
        cur[int(last)] = value
    else:
        cur[last] = value


def _apply_mutate(envelope: dict[str, Any], mutate: list[dict[str, Any]]) -> dict[str, Any]:
    env = copy.deepcopy(envelope)
    for step in mutate:
        op = step.get("op")
        if op == "set":
            _set_path(env, step["path"], step.get("value"))
        elif op == "truncate_stops":
            count = int(step.get("count", 2))
            env["route"]["stops"] = env["route"]["stops"][:count]
            for i, s in enumerate(env["route"]["stops"]):
                s["order"] = i + 1
                if i == len(env["route"]["stops"]) - 1:
                    s["transition_to_next"] = None
        elif op == "patch_first_story_sources":
            for b in env.get("blocks") or []:
                if isinstance(b, dict) and b.get("type") == "story_card":
                    b["sources"] = step.get("value")
                    break
        elif op == "building_layers_only":
            # 剥掉 person/event，仅留建筑层（若无则合成一条），用于 I1 实体层红队。
            for s in env.get("route", {}).get("stops") or []:
                if not isinstance(s, dict):
                    continue
                layers = [
                    l
                    for l in (s.get("layers") or [])
                    if isinstance(l, dict) and l.get("kind") == "building"
                ]
                if not layers:
                    layers = [
                        {
                            "kind": "building",
                            "label": "建筑",
                            "claim": f"{s.get('name') or '该站'}建筑轮廓",
                            "source": {
                                "dataset": "amap",
                                "record_id": "poi-placeholder",
                            },
                        }
                    ]
                s["layers"] = layers
    return env


def _load_base(name: str) -> dict[str, Any]:
    path = FIXTURES.get(name)
    if not path or not path.exists():
        # Fallback demo-route if curated-live missing
        path = FIXTURES["demo-route"]
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def run_redteam(cases_path: Path | None = None) -> dict[str, Any]:
    path = cases_path or CASES_PATH
    cases = json.loads(path.read_text(encoding="utf-8"))
    results = []
    failed = 0
    for case in cases:
        base = _load_base(case.get("base", "curated-live"))
        envelope = _apply_mutate(base, case.get("mutate") or [])
        verdict = evaluate_envelope(envelope)
        expect_pass = bool(case.get("expect_pass"))
        ok = verdict.passed == expect_pass
        needle = case.get("expect_blocker_contains")
        if needle and not expect_pass:
            ok = ok and any(needle in b for b in verdict.blockers)
        if not ok:
            failed += 1
        results.append(
            {
                "id": case["id"],
                "ok": ok,
                "expect_pass": expect_pass,
                "passed": verdict.passed,
                "blockers": verdict.blockers,
                "warnings": verdict.warnings,
                "description": case.get("description"),
            }
        )
    return {
        "total": len(results),
        "failed": failed,
        "passed": len(results) - failed,
        "results": results,
        "ok": failed == 0,
    }


def main() -> int:
    report = run_redteam()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print("REDTEAM_OK" if report["ok"] else "REDTEAM_FAIL")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
