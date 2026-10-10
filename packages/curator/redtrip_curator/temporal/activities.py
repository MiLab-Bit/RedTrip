"""Temporal Activities —— RedTrip 七段管线的 Activity 封装。

每个 Activity 包裹一个现有的管线阶段函数，处理 dataclass ↔ dict 的序列化转换。
Activity 全部是同步 def（temporalio 会放到线程池执行），因为底层管线函数都是同步的。
"""

from __future__ import annotations

import os
import sys
from typing import Any

from temporalio import activity

# 确保包路径可达
_CURATOR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PACKAGES = os.path.dirname(os.path.dirname(_CURATOR))
_GATE = os.path.join(_PACKAGES, "gate")
for p in [_CURATOR, _PACKAGES, _GATE, os.path.join(_PACKAGES, "library-client")]:
    if p not in sys.path:
        sys.path.insert(0, p)


def _heartbeat(*detail: str) -> None:
    """Activity 心跳；离线直调时忽略。"""
    try:
        activity.heartbeat(*detail)
    except RuntimeError:
        pass


# ======================================================================
# 七段管线 Activities
# ======================================================================

@activity.defn(name="parse_intent")
def parse_intent_activity(inp: dict[str, Any]) -> dict[str, Any]:
    """阶段 1: 意图解析。"""
    from redtrip_curator.intent import parse_intent
    from redtrip_curator.models import Intent

    _heartbeat("intent:start")
    intent = parse_intent(inp.get("slots"), inp.get("message"))
    _heartbeat("intent:done")
    return {
        "audience": intent.audience,
        "scene": intent.scene,
        "duration_min": intent.duration_min,
        "tone": intent.tone,
        "delivery": intent.delivery,
        "companions": intent.companions,
        "assumptions": intent.assumptions,
        "message": intent.message,
        "daypart": intent.daypart,
        "city": intent.city,
    }


@activity.defn(name="fetch_evidence")
def fetch_evidence_activity(inp: dict[str, Any]) -> dict[str, Any]:
    """阶段 2: 多源取证。"""
    from redtrip_library import SlcClient
    from redtrip_curator.evidence import fetch_evidence
    from redtrip_curator.models import Intent, EvidencePack

    _heartbeat("evidence:start")
    intent = Intent(**inp["intent"])
    limit = inp.get("limit", 12)
    client = SlcClient()
    pack = fetch_evidence(client, intent, limit=limit)
    _heartbeat(f"evidence:done buildings={len(pack.buildings)}")
    return _pack_to_dict(pack)


@activity.defn(name="join_layers")
def join_layers_activity(pack_dict: dict[str, Any]) -> dict[str, Any]:
    """阶段 2.5: 图层融合。"""
    from redtrip_curator.join import join_layers
    from redtrip_curator.models import EvidencePack

    _heartbeat("join:start")
    pack = _dict_to_pack(pack_dict)
    pack = join_layers(pack)
    _heartbeat("join:done")
    return _pack_to_dict(pack)


@activity.defn(name="draw_voice")
def draw_voice_activity(inp: dict[str, Any]) -> dict[str, Any]:
    """阶段 2.8: 红鸢词库抽签。"""
    from redtrip_curator.hongyuan import draw_voice_pack

    _heartbeat("voice:start")
    voice = draw_voice_pack(
        tone=inp.get("tone", "文学"),
        companions=inp.get("companions", "独自"),
        duration_min=inp.get("duration_min", 90),
        seed=inp.get("hongyuan_seed"),
    )
    _heartbeat("voice:done")
    return voice.as_dict()


@activity.defn(name="plan_route")
def plan_route_activity(inp: dict[str, Any]) -> dict[str, Any]:
    """阶段 3: 路线规划。"""
    from redtrip_curator.plan import plan_route
    from redtrip_curator.models import Intent, EvidencePack

    _heartbeat("plan:start")
    intent = Intent(**inp["intent"])
    pack = _dict_to_pack(inp["pack"])
    plan = plan_route(intent, pack)
    _heartbeat(f"plan:done stops={len(plan.stops)}")
    return {
        "stops": [
            {
                "order": s.evidence.order if hasattr(s.evidence, 'order') else i,
                "evidence": s.evidence.as_dict() if hasattr(s.evidence, 'as_dict') else {},
                "name": s.evidence.name,
                "minutes": s.minutes,
                "meaning": s.meaning,
                "transition_to_next": s.transition_to_next,
                "act": s.act,
            }
            for i, s in enumerate(plan.stops)
        ],
        "duration_min": plan.duration_min,
        "walk_meters_est": plan.walk_meters_est,
    }


@activity.defn(name="attach_layer3")
def attach_layer3_activity(inp: dict[str, Any]) -> dict[str, Any]:
    """阶段 3.5: L3 热词注入。"""
    from redtrip_curator.hongyuan import VoicePack, attach_layer3

    _heartbeat("layer3:start")
    voice = _voice_from_dict(inp["voice"]) if inp.get("voice") else None
    places = inp.get("places", [])
    tone = inp.get("tone", "文学")
    if voice:
        voice = attach_layer3(voice, places=places, tone=tone)
        _heartbeat("layer3:done")
        return voice.as_dict()
    return {}


@activity.defn(name="narrate")
def narrate_activity(inp: dict[str, Any]) -> dict[str, Any]:
    """阶段 4: 叙事初稿（模板）。"""
    from redtrip_curator.narrative import narrate
    from redtrip_curator.models import Intent

    _heartbeat("narrate:start")
    intent = Intent(**inp["intent"])
    plan_dict = inp["plan"]
    sources_used = inp.get("sources_used", [])
    draft = narrate(intent, _dict_to_plan(plan_dict), sources_used)
    _heartbeat("narrate:done")
    return draft


@activity.defn(name="build_artifacts")
def build_artifacts_activity(inp: dict[str, Any]) -> dict[str, Any]:
    """阶段 4.5: 构建中间产物。"""
    from redtrip_curator.artifacts import build_artifacts
    from redtrip_curator.models import Intent, EvidencePack

    _heartbeat("artifacts:start")
    intent = Intent(**inp["intent"])
    pack = _dict_to_pack(inp["pack"])
    plan = _dict_to_plan(inp["plan"])
    artifacts = build_artifacts(intent, plan, pack)
    _heartbeat("artifacts:done")
    # artifacts 是复杂对象，返回一个标记，实际 embed 在 Workflow 里做
    return {"built": True}


@activity.defn(name="polish_envelope")
def polish_envelope_activity(inp: dict[str, Any]) -> dict[str, Any]:
    """阶段 5: LLM 润色（元数据 + 逐卡并行 + 逐句溯源）。
    这是最耗时的阶段，可能跑几分钟。"""
    from redtrip_curator.polish import polish_envelope
    from redtrip_curator.hongyuan import VoicePack
    from redtrip_curator.plan import RoutePlan

    _heartbeat("polish:start")
    draft = inp["draft"]
    voice = _voice_from_dict(inp["voice"]) if inp.get("voice") else None
    plan = _dict_to_plan(inp["plan"])

    polished, notes, sp = polish_envelope(draft, voice=voice, plan=plan)
    _heartbeat("polish:done")
    return {
        "polished": polished,
        "notes": notes,
        "sp": sp.as_dict() if sp else None,
        "mode": "llm_polish" if polished else "template",
    }


@activity.defn(name="evaluate_gate")
def evaluate_gate_activity(envelope: dict[str, Any]) -> dict[str, Any]:
    """阶段 6: Gate 门禁检查。"""
    from redtrip_gate import evaluate_envelope

    _heartbeat("gate:start")
    verdict = evaluate_envelope(envelope)
    _heartbeat(f"gate:done passed={verdict.passed}")
    return {
        "passed": verdict.passed,
        "blockers": list(verdict.blockers),
        "warnings": list(verdict.warnings),
    }


@activity.defn(name="review_envelope")
def review_envelope_activity(inp: dict[str, Any]) -> dict[str, Any]:
    """阶段 7: 反方策展人评审（非阻断）。"""
    from redtrip_curator.review import review_envelope
    from redtrip_curator.hongyuan import VoicePack
    from redtrip_curator.plan import RoutePlan

    _heartbeat("review:start")
    envelope = inp["envelope"]
    plan = _dict_to_plan(inp["plan"])
    voice = _voice_from_dict(inp["voice"]) if inp.get("voice") else None
    review = review_envelope(envelope, plan=plan, voice=voice)
    _heartbeat("review:done")
    return review or {}


# ======================================================================
# 序列化辅助
# ======================================================================

def _pack_to_dict(pack) -> dict[str, Any]:
    """EvidencePack → dict（跨 Temporal 边界）。"""
    return {
        "buildings": [
            {
                "buri": b.buri,
                "name": b.name,
                "address": b.address,
                "lat": b.lat,
                "lng": b.lng,
                "layers": [l.as_dict() for l in b.layers],
                "coord_source": b.coord_source,
                "precision": b.precision,
                "evidence_channel": b.evidence_channel,
                "road_context": b.road_context,
                "photo_spot": b.photo_spot,
            }
            for b in pack.buildings
        ],
        "gaps": pack.gaps,
        "fetched_at": pack.fetched_at,
        "mode": pack.mode,
        "sources_used": pack.sources_used,
    }


def _dict_to_pack(d: dict[str, Any]):
    """dict → EvidencePack。"""
    from redtrip_curator.models import EvidencePack, BuildingEvidence, IdentityLayer, SourceRef

    buildings = []
    for bd in d.get("buildings", []):
        layers = []
        for ld in bd.get("layers", []):
            src = ld.get("source", {})
            layers.append(IdentityLayer(
                kind=ld["kind"],
                label=ld["label"],
                claim=ld["claim"],
                source=SourceRef(
                    dataset=src.get("dataset", ""),
                    record_id=src.get("record_id", ""),
                    excerpt=src.get("excerpt"),
                ),
            ))
        buildings.append(BuildingEvidence(
            buri=bd["buri"],
            name=bd["name"],
            address=bd.get("address"),
            lat=bd.get("lat"),
            lng=bd.get("lng"),
            layers=layers,
            coord_source=bd.get("coord_source", "none"),
            precision=bd.get("precision", "schematic"),
            evidence_channel=bd.get("evidence_channel", "manual"),
            road_context=bd.get("road_context"),
            photo_spot=bd.get("photo_spot"),
        ))
    return EvidencePack(
        buildings=buildings,
        gaps=d.get("gaps", []),
        fetched_at=d.get("fetched_at", ""),
        mode=d.get("mode", "indexed"),
        sources_used=d.get("sources_used", []),
    )


def _dict_to_plan(d: dict[str, Any]):
    """dict → RoutePlan。"""
    from redtrip_curator.models import BuildingEvidence, SourceRef
    from redtrip_curator.plan import RoutePlan, PlannedStop

    stops = []
    for sd in d.get("stops", []):
        ev_d = sd.get("evidence", {})
        be = BuildingEvidence(
            buri=ev_d.get("buri", sd.get("name", "")),
            name=sd.get("name", ev_d.get("name", "")),
            address=ev_d.get("address"),
            lat=ev_d.get("lat"),
            lng=ev_d.get("lng"),
        )
        stops.append(PlannedStop(
            evidence=be,
            order=sd.get("order", len(stops)),
            minutes=sd.get("minutes", 30),
            meaning=sd.get("meaning", ""),
            transition_to_next=sd.get("transition_to_next"),
            act=sd.get("act", "focus"),
        ))
    return RoutePlan(
        stops=stops,
        duration_min=d.get("duration_min", 90),
        walk_meters_est=d.get("walk_meters_est", 0),
    )


# ======================================================================
# VoicePack 反序列化辅助
# ======================================================================

def _voice_from_dict(d: dict[str, Any]) -> "VoicePack":
    """dict -> VoicePack（反序列化，用于跨 Temporal 边界重建）。"""
    from redtrip_curator.hongyuan.draw import VoicePack, DrawnSlot

    def _slot(sd: dict) -> DrawnSlot:
        return DrawnSlot(
            category=sd.get("category", ""),
            id=sd.get("id", ""),
            label=sd.get("label", ""),
            hint=sd.get("hint", ""),
        )

    return VoicePack(
        agent=d.get("agent", "红鸢"),
        seed=d.get("seed", 0),
        emotion=_slot(d.get("emotion", {})),
        voice_style=_slot(d.get("voice_style", {})),
        narrative=_slot(d.get("narrative", {})),
        knowledge_angle=_slot(d.get("knowledge_angle", {})),
        pacing=_slot(d.get("pacing", {})),
        layer3_week=d.get("layer3_week"),
    )
