"""Temporal Worker 启动器（统一到 hermes_core.temporal.run_worker）。"""
from __future__ import annotations

import os
import sys

# 确保包路径（curator 导入期依赖 gate / library-client）
_HERE = os.path.dirname(os.path.abspath(__file__))
_PACKAGES = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(_HERE))))
for _p in [
    os.path.join(_PACKAGES, "curator"),
    os.path.join(_PACKAGES, "gate"),
    os.path.join(_PACKAGES, "library-client"),
]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from hermes_core.temporal import run_worker

from redtrip_curator.temporal.activities import (  # noqa: E402 - 需先注入 sys.path 再导入
    attach_layer3_activity,
    build_artifacts_activity,
    draw_voice_activity,
    evaluate_gate_activity,
    fetch_evidence_activity,
    join_layers_activity,
    narrate_activity,
    parse_intent_activity,
    plan_route_activity,
    polish_envelope_activity,
    review_envelope_activity,
)
from redtrip_curator.temporal.workflows.curate import CurateWorkflow  # noqa: E402 - 同上前置路径注入


def run() -> None:
    run_worker(
        [CurateWorkflow],
        [
            parse_intent_activity,
            fetch_evidence_activity,
            join_layers_activity,
            draw_voice_activity,
            plan_route_activity,
            attach_layer3_activity,
            narrate_activity,
            build_artifacts_activity,
            polish_envelope_activity,
            evaluate_gate_activity,
            review_envelope_activity,
        ],
        task_queue="redtrip-task-queue",
        namespace="redtrip",
        address="127.0.0.1:7233",
        activity_workers=20,
        passthrough_modules={"redtrip_curator", "redtrip_gate", "redtrip_library"},
    )


if __name__ == "__main__":
    run()
