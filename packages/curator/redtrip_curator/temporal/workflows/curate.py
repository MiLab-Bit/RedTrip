"""CurateWorkflow —— RedTrip 七段管线（Temporal 底座）。

把原来的同步 curate() 函数迁移为可持久化、可重试、可观测的 Temporal Workflow：

  intent → evidence → join → voice → plan → layer3 → narrate
    → artifacts → story_ready → polish → gate → review → done

确定性约束：Workflow 内不得直接调用 LLM / 网络 / 随机。
所有"会变"的操作必须经 workflow.execute_activity 落到 Activity。
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy

from redtrip_curator.temporal.common import CurateInput

# 默认 Activity 超时 / 重试
_ACT_SHORT = timedelta(seconds=30)    # 纯本地计算
_ACT_MEDIUM = timedelta(seconds=120)  # SLC 查询
_ACT_LONG = timedelta(minutes=10)     # LLM 润色
_ACT_RETRY = RetryPolicy(maximum_attempts=3, non_retryable_error_types=["ValueError"])


@workflow.defn(name="CurateWorkflow")
class CurateWorkflow:
    """城市策展工作流。"""

    def __init__(self) -> None:
        self.progress: list[dict[str, Any]] = []
        self.status: str = "running"
        self.envelope: dict[str, Any] | None = None
        self.intent_dict: dict[str, Any] = {}
        self.pack_dict: dict[str, Any] = {}
        self.voice_dict: dict[str, Any] = {}
        self.plan_dict: dict[str, Any] = {}
        self.assumptions: list[str] = []
        self.warnings: list[str] = []

    def _emit(self, stage: str, pct: float, msg: str = "") -> None:
        self.progress.append({"stage": stage, "progress": pct, "message": msg})

    @workflow.run
    async def run(self, inp: CurateInput) -> dict[str, Any]:
        self._emit("init", 2.0, "已接收策展请求")

        # 1) intent
        self._emit("intent", 6.0, "解析出行意图")
        self.intent_dict = await workflow.execute_activity(
            "parse_intent",
            {"slots": inp.slots, "message": inp.message},
            start_to_close_timeout=_ACT_SHORT,
            retry_policy=_ACT_RETRY,
        )
        self.assumptions = self.intent_dict.get("assumptions", [])

        # 2) evidence
        self._emit("evidence", 20.0, "多源取证")
        dur = self.intent_dict.get("duration_min", 90)
        limit = max(12, 20 if dur <= 240 else 28 if dur <= 480 else 36)
        self.pack_dict = await workflow.execute_activity(
            "fetch_evidence",
            {"intent": self.intent_dict, "limit": limit},
            start_to_close_timeout=_ACT_MEDIUM,
            retry_policy=_ACT_RETRY,
        )
        bcount = len(self.pack_dict.get("buildings", []))
        self._emit("evidence", 20.0, f"SLC 取证完成（{bcount} 处建筑）")

        if bcount < 3:
            self.status = "failed"
            self._emit("failed", 100.0, "取证候选不足（<3），无法策展")
            return self._snapshot()

        # 2.5) join
        self._emit("join", 24.0, "图层融合")
        self.pack_dict = await workflow.execute_activity(
            "join_layers",
            self.pack_dict,
            start_to_close_timeout=_ACT_SHORT,
            retry_policy=_ACT_RETRY,
        )

        # 2.8) voice
        self._emit("voice", 28.0, "红鸢词库抽签")
        self.voice_dict = await workflow.execute_activity(
            "draw_voice",
            {
                "tone": self.intent_dict.get("tone", "文学"),
                "companions": self.intent_dict.get("companions", "独自"),
                "duration_min": dur,
                "hongyuan_seed": inp.hongyuan_seed,
            },
            start_to_close_timeout=_ACT_SHORT,
            retry_policy=_ACT_RETRY,
        )

        # 3) plan
        self._emit("plan", 34.0, "路线规划")
        try:
            self.plan_dict = await workflow.execute_activity(
                "plan_route",
                {"intent": self.intent_dict, "pack": self.pack_dict},
                start_to_close_timeout=_ACT_SHORT,
                retry_policy=_ACT_RETRY,
            )
        except Exception as e:
            self.status = "failed"
            self._emit("failed", 100.0, f"路线规划失败：{e}")
            return self._snapshot()

        # 3.5) layer3
        self._emit("layer3", 38.0, "L3 热词注入")
        places = [self.intent_dict.get("scene", "")]
        places += [s.get("name", "") for s in self.plan_dict.get("stops", [])]
        self.voice_dict = await workflow.execute_activity(
            "attach_layer3",
            {"voice": self.voice_dict, "places": places, "tone": self.intent_dict.get("tone", "文学")},
            start_to_close_timeout=_ACT_SHORT,
            retry_policy=_ACT_RETRY,
        )

        # 4) narrate
        self._emit("narrate", 50.0, "命题与叙事初稿")
        self.envelope = await workflow.execute_activity(
            "narrate",
            {
                "intent": self.intent_dict,
                "plan": self.plan_dict,
                "sources_used": self.pack_dict.get("sources_used", []),
            },
            start_to_close_timeout=_ACT_SHORT,
            retry_policy=_ACT_RETRY,
        )

        # 4.5) artifacts
        await workflow.execute_activity(
            "build_artifacts",
            {"intent": self.intent_dict, "pack": self.pack_dict, "plan": self.plan_dict},
            start_to_close_timeout=_ACT_SHORT,
            retry_policy=_ACT_RETRY,
        )
        self._emit("artifacts", 52.0, "中间产物生成完成")

        # 5) polish（最耗时）
        self._emit("polish", 55.0, "LLM 润色进行中")
        try:
            polish_result = await workflow.execute_activity(
                "polish_envelope",
                {"draft": self.envelope, "voice": self.voice_dict, "plan": self.plan_dict},
                start_to_close_timeout=_ACT_LONG,
                retry_policy=_ACT_RETRY,
            )
            polished = polish_result.get("polished")
            if polished:
                self.envelope = polished
                self.warnings.extend(polish_result.get("notes", []))
                narrative_mode = polish_result.get("mode", "template")
            else:
                narrative_mode = "template"
        except Exception as e:
            self.warnings.append(f"LLM 润色失败，保留模板：{e}")
            narrative_mode = "template"

        # 6) gate
        self._emit("gate", 92.0, "Gate 门禁检查")
        verdict = await workflow.execute_activity(
            "evaluate_gate",
            self.envelope,
            start_to_close_timeout=_ACT_SHORT,
            retry_policy=_ACT_RETRY,
        )

        degraded = not verdict.get("passed", True)
        self.warnings.extend(verdict.get("warnings", []))

        # 7) review（非阻断，仅通过 Gate 后跑）
        if not degraded and self.envelope:
            self._emit("review", 95.0, "反方策展人评审")
            try:
                review = await workflow.execute_activity(
                    "review_envelope",
                    {"envelope": self.envelope, "plan": self.plan_dict, "voice": self.voice_dict},
                    start_to_close_timeout=_ACT_LONG,
                    retry_policy=_ACT_RETRY,
                )
                if review:
                    self.envelope["curator_review"] = review
                    r_warn = review.get("warnings", [])
                    self.warnings.extend(r_warn)
            except Exception as e:
                self.warnings.append(f"反方策展人评审跳过：{e}")

        self.status = "completed"
        self._emit("done", 100.0, "策展完成")

        return self._snapshot()

    # ==================================================================
    # Query：供 API 网关轮询
    # ==================================================================

    @workflow.query
    def get_progress(self) -> list[dict[str, Any]]:
        return self.progress

    @workflow.query
    def get_status(self) -> str:
        return self.status

    @workflow.query
    def get_envelope(self) -> dict[str, Any] | None:
        return self.envelope

    @workflow.query
    def get_snapshot(self) -> dict[str, Any]:
        return self._snapshot()

    def _snapshot(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "progress": self.progress,
            "envelope": self.envelope,
            "intent": self.intent_dict,
            "assumptions": self.assumptions,
            "warnings": self.warnings,
            "evidence_count": len(self.pack_dict.get("buildings", [])),
            "hongyuan": self.voice_dict,
        }
