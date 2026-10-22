"""RedTrip CurateWorkflow 黄金测试 —— 仅覆盖「不调 LLM / 不联网」的确定性环节。

覆盖：
  - CurateInput 跨边界 dataclass 契约（asdict / 重建）
  - 七个阶段中纯本地、可复现的 Activity 映射：
      parse_intent / draw_voice / join_layers / plan_route / evaluate_gate / review_envelope
    （narrate / polish / fetch_evidence 依赖 LLM 或 SLC 网络，不在本文件断言）
  - CurateWorkflow 的 Query/快照结构（不启动 Temporal，仅校验确定性状态机初值）

运行（仓库根）：
    venv/bin/python -m pytest tests/test_curate_pipeline_golden.py -q
"""
from __future__ import annotations

from dataclasses import asdict

import pytest
from redtrip_curator.temporal.activities import (
    draw_voice_activity,
    evaluate_gate_activity,
    join_layers_activity,
    parse_intent_activity,
    plan_route_activity,
    review_envelope_activity,
)
from redtrip_curator.temporal.common import CurateInput


# ----------------------------------------------------------------------
# CurateInput 跨边界契约
# ----------------------------------------------------------------------
def test_curate_input_defaults():
    ci = CurateInput()
    assert ci.slots == {}
    assert ci.message is None
    assert ci.hongyuan_seed is None
    assert ci.workflow_id is None


def test_curate_input_roundtrip():
    ci = CurateInput(slots={"scene": "外滩"}, message="帮我规划", hongyuan_seed=7)
    d = asdict(ci)
    assert d["hongyuan_seed"] == 7
    assert d["message"] == "帮我规划"
    rebuilt = CurateInput(**d)
    assert rebuilt == ci


# ----------------------------------------------------------------------
# 阶段 1: parse_intent（确定性）
# ----------------------------------------------------------------------
def test_parse_intent_deterministic_defaults():
    out1 = parse_intent_activity({"slots": {}, "message": None})
    out2 = parse_intent_activity({"slots": {}, "message": None})
    assert out1 == out2
    assert out1["duration_min"] == 90          # 空槽 → 默认 90
    assert isinstance(out1["assumptions"], list) and len(out1["assumptions"]) > 0
    assert isinstance(out1["city"], str) and out1["city"]  # 非法城市回退 shanghai 键


def test_parse_intent_echoes_slots():
    out = parse_intent_activity({"slots": {"scene": "外滩", "tone": "学术", "duration_min": 120}, "message": "x"})
    assert out["scene"] == "外滩"
    assert out["tone"] == "学术"
    assert out["duration_min"] == 120


# ----------------------------------------------------------------------
# 阶段 2.8: draw_voice（固定 seed 确定性）
# ----------------------------------------------------------------------
def test_draw_voice_seed_deterministic():
    kw = {"tone": "文学", "companions": "独自", "duration_min": 90, "hongyuan_seed": 42}
    v1 = draw_voice_activity(kw)
    v2 = draw_voice_activity(kw)
    assert v1 == v2
    assert v1["seed"] == 42
    assert v1["agent"] == "红鸢"


def test_draw_voice_different_seed_differs():
    base = {"tone": "文学", "companions": "独自", "duration_min": 90}
    a = draw_voice_activity({**base, "hongyuan_seed": 1})
    b = draw_voice_activity({**base, "hongyuan_seed": 2})
    assert a != b


# ----------------------------------------------------------------------
# 阶段 2.5: join_layers（确定性，幂等）
# ----------------------------------------------------------------------
_MIN_PACK = {
    "buildings": [
        {
            "buri": "uri-1", "name": "和平饭店", "address": "中山东一路",
            "lat": 31.24, "lng": 121.49,
            "layers": [
                {"kind": "building", "label": "建筑", "claim": "1929年建",
                 "source": {"dataset": "building_detail", "record_id": "r1"}},
            ],
            "coord_source": "amap", "precision": "approximate",
            "evidence_channel": "manual", "road_context": None, "photo_spot": None,
        }
    ],
    "gaps": [], "fetched_at": "", "mode": "indexed", "sources_used": ["slc"],
}


def test_join_layers_deterministic():
    out1 = join_layers_activity(_MIN_PACK)
    out2 = join_layers_activity(_MIN_PACK)
    assert out1 == out2
    assert len(out1["buildings"]) == 1
    assert out1["buildings"][0]["name"] == "和平饭店"


# ----------------------------------------------------------------------
# 阶段 3: plan_route（确定性；候选不足 3 时按设计抛出 ValueError）
# ----------------------------------------------------------------------
_INTENT = {
    "audience": "家庭", "scene": "外滩", "duration_min": 90, "tone": "文学",
    "delivery": "导览", "companions": "独自", "assumptions": [],
    "message": None, "daypart": "day", "city": "shanghai",
}

# 三处地理分散、各自带 IdentityLayer 的建筑，足以通过多样性 + 间距筛选
_PACK3 = {
    "buildings": [
        {"buri": "uri-1", "name": "和平饭店", "address": "中山东一路", "lat": 31.239, "lng": 121.490,
         "layers": [{"kind": "building", "label": "建筑", "claim": "1929年建",
                     "source": {"dataset": "building_detail", "record_id": "r1"}}],
         "coord_source": "amap", "precision": "approximate", "evidence_channel": "manual", "road_context": None, "photo_spot": None},
        {"buri": "uri-2", "name": "东方明珠", "address": "世纪大道", "lat": 31.240, "lng": 121.500,
         "layers": [{"kind": "building", "label": "建筑", "claim": "1994年建",
                     "source": {"dataset": "building_detail", "record_id": "r2"}}],
         "coord_source": "amap", "precision": "approximate", "evidence_channel": "manual", "road_context": None, "photo_spot": None},
        {"buri": "uri-3", "name": "豫园", "address": "安仁街", "lat": 31.227, "lng": 121.492,
         "layers": [{"kind": "building", "label": "建筑", "claim": "明代园林",
                     "source": {"dataset": "building_detail", "record_id": "r3"}}],
         "coord_source": "amap", "precision": "approximate", "evidence_channel": "manual", "road_context": None, "photo_spot": None},
    ],
    "gaps": [], "fetched_at": "", "mode": "indexed", "sources_used": ["slc"],
}


def test_plan_route_returns_stops():
    out = plan_route_activity({"intent": _INTENT, "pack": _PACK3})
    assert "stops" in out
    assert isinstance(out["stops"], list)
    assert len(out["stops"]) >= 3
    assert out["duration_min"] == 90


def test_plan_route_raises_when_too_few():
    # 候选 < 3 → plan_route 抛 ValueError，由 CurateWorkflow.run 的 except 捕获置 failed
    with pytest.raises(ValueError):
        plan_route_activity({"intent": _INTENT, "pack": _MIN_PACK})


# ----------------------------------------------------------------------
# 阶段 6: evaluate_gate（Activity 映射契约；门禁逻辑见 test_gate.py）
# ----------------------------------------------------------------------
def test_evaluate_gate_mapping_shape():
    env = {
        "intent": _INTENT, "theme": "t", "logic_line": "并置", "aesthetic": "海派",
        "scenario": "外滩", "why_visit": "读建筑", "sources": [],
        "blocks": [], "curator_note": "", "route": {"duration_min": 90, "stops": []},
        "provenance": {"total_assertions": 0, "aligned_assertions": 0,
                       "coverage_ratio": 1.0, "per_stop": []},
    }
    out = evaluate_gate_activity(env)
    assert set(out.keys()) >= {"passed", "blockers", "warnings"}
    assert isinstance(out["passed"], bool)
    assert isinstance(out["blockers"], list)
    assert isinstance(out["warnings"], list)


# ----------------------------------------------------------------------
# 阶段 7: review_envelope（无 LLM 时确定性回退 {}）
# ----------------------------------------------------------------------
def test_review_envelope_no_llm_falls_back():
    # conftest 已清空 LLM_API_KEY → llm_configured() 为 False → review_envelope 返回 None
    out = review_envelope_activity(
        {"envelope": {}, "plan": {"stops": [], "duration_min": 90, "walk_meters_est": 0}, "voice": None},
    )
    assert out == {}


# ----------------------------------------------------------------------
# CurateWorkflow 状态机初值（不启动 Temporal）
# ----------------------------------------------------------------------
def test_workflow_initial_state_and_queries():
    from redtrip_curator.temporal.workflows.curate import CurateWorkflow

    wf = CurateWorkflow()
    assert wf.get_status() == "running"
    assert wf.get_progress() == []
    snap = wf.get_snapshot()
    assert snap["status"] == "running"
    for k in ("progress", "envelope", "intent", "assumptions", "warnings", "evidence_count", "hongyuan"):
        assert k in snap
