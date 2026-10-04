"""Temporal Worker 启动器。"""

from __future__ import annotations

import asyncio
import concurrent.futures
import dataclasses
import logging
import os
import sys

from temporalio.client import Client
from temporalio.worker import Worker
from temporalio.worker.workflow_sandbox import (
    SandboxedWorkflowRunner,
    SandboxRestrictions,
)

# 确保包路径
_HERE = os.path.dirname(os.path.abspath(__file__))
_PACKAGES = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(_HERE))))
for p in [
    os.path.join(_PACKAGES, "curator"),
    os.path.join(_PACKAGES, "gate"),
    os.path.join(_PACKAGES, "library-client"),
]:
    if p not in sys.path:
        sys.path.insert(0, p)

from redtrip_curator.temporal.activities import (
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
)
from redtrip_curator.temporal.workflows.curate import CurateWorkflow

log = logging.getLogger("redtrip.temporal.worker")

_ACTIVITY_WORKERS = 20

# 领域模块在导入期会做路径解析等副作用，对沙箱设为直通
_SANDBOX_RUNNER = SandboxedWorkflowRunner(
    restrictions=dataclasses.replace(
        SandboxRestrictions.default,
        passthrough_modules=SandboxRestrictions.default.passthrough_modules
        | {"redtrip_curator", "redtrip_gate", "redtrip_library"},
    )
)


async def _run() -> None:
    address = os.getenv("TEMPORAL_ADDRESS", "127.0.0.1:7233")
    namespace = os.getenv("TEMPORAL_NAMESPACE", "redtrip")
    task_queue = os.getenv("TEMPORAL_TASK_QUEUE", "redtrip-task-queue")

    log.info("starting Temporal worker | tq=%s ns=%s addr=%s", task_queue, namespace, address)
    client = await Client.connect(address, namespace=namespace)

    with concurrent.futures.ThreadPoolExecutor(max_workers=_ACTIVITY_WORKERS) as pool:
        worker = Worker(
            client,
            task_queue=task_queue,
            workflows=[CurateWorkflow],
            workflow_runner=_SANDBOX_RUNNER,
            activities=[
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
            activity_executor=pool,
        )
        await worker.run()


def run() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(_run())


if __name__ == "__main__":
    run()
