"""proposition.py 单测：propose/critique 两步分离 + 降级 + 启发式兜底。

运行：.venv/Scripts/python.exe -m pytest tests/test_proposition.py -q
"""
from unittest.mock import patch

from redtrip_curator.models import (
    BuildingEvidence,
    EvidencePack,
    IdentityLayer,
    Intent,
    PlannedStop,
    RoutePlan,
    SourceRef,
)
from redtrip_curator.proposition import decompose_intent


def _make_intent() -> Intent:
    return Intent(
        audience="成人", scene="外滩", duration_min=90, tone="文艺",
        delivery="路线", companions="2人", assumptions=[],
        message="想走一走外滩", daypart="day", city="shanghai",
    )


def _make_plan() -> RoutePlan:
    layer = IdentityLayer(
        kind="building", label="和平饭店", claim="1929年建成",
        source=SourceRef(dataset="curated", record_id="r1"),
    )
    be = BuildingEvidence(
        buri="u", name="和平饭店", address=None, lat=31.2, lng=121.4,
        layers=[layer], raw_detail={"category": "historic"},
    )
    stop = PlannedStop(order=1, evidence=be, minutes=10, meaning="m", transition_to_next=None)
    return RoutePlan(stops=[stop], duration_min=60, walk_meters_est=100)


def _make_pack() -> EvidencePack:
    return EvidencePack(buildings=[], gaps=[], fetched_at="2026-01-01T00:00:00Z", mode="indexed")


_PROPOSE = {
    "title": "外滩·江海关的世纪",
    "open_question": "外滩如何见证上海开埠",
    "scope_note": "聚焦外滩建筑群",
    "propositions": [
        {
            "axis": "建筑身份", "hypothesis": "同一栋楼的用途随年代被改写",
            "dimension": "building", "question": "和平饭店的用途如何变迁？",
        }
    ],
}


def test_critique_over_extended_applied():
    """critique 判 over_extended → 用 rewritten 收敛，status=rewritten。"""
    crit = {"verdicts": [
        {"index": 0, "verdict": "over_extended",
         "rewritten_hypothesis": "围绕建筑身份，以证据可核验的视角展开"},
    ]}
    with patch("redtrip_curator.proposition.llm_configured", return_value=True), \
         patch("redtrip_curator.proposition.chat_json", side_effect=[_PROPOSE, crit]) as cj:
        ps = decompose_intent(_make_intent(), _make_plan(), _make_pack(), ["building"])
    assert ps is not None
    assert ps.propositions[0].status == "rewritten"
    assert "证据可核验" in ps.propositions[0].hypothesis
    assert ps.redteam_applied is True
    assert cj.call_count == 2


def test_critique_allowed_passes_through():
    """critique 判 allowed → 保持原假设。"""
    crit = {"verdicts": [{"index": 0, "verdict": "allowed", "rewritten_hypothesis": ""}]}
    with patch("redtrip_curator.proposition.llm_configured", return_value=True), \
         patch("redtrip_curator.proposition.chat_json", side_effect=[_PROPOSE, crit]):
        ps = decompose_intent(_make_intent(), _make_plan(), _make_pack(), ["building"])
    assert ps is not None
    assert ps.propositions[0].status == "allowed"
    assert ps.propositions[0].hypothesis == "同一栋楼的用途随年代被改写"


def test_critique_failure_degrades_to_allowed():
    """critique 调用失败 → 全部 allowed，流程不阻断。"""
    with patch("redtrip_curator.proposition.llm_configured", return_value=True), \
         patch("redtrip_curator.proposition.chat_json",
               side_effect=[_PROPOSE, RuntimeError("boom")]):
        ps = decompose_intent(_make_intent(), _make_plan(), _make_pack(), ["building"])
    assert ps is not None
    assert ps.propositions[0].status == "allowed"


def test_propose_failure_returns_none():
    """propose 失败 → 返回 None（调用方回退规则）。"""
    with patch("redtrip_curator.proposition.llm_configured", return_value=True), \
         patch("redtrip_curator.proposition.chat_json", side_effect=RuntimeError("boom")):
        assert decompose_intent(_make_intent(), _make_plan(), _make_pack()) is None


def test_unconfigured_returns_none():
    """未配 LLM → 返回 None，且不发起任何调用。"""
    with patch("redtrip_curator.proposition.llm_configured", return_value=False), \
         patch("redtrip_curator.proposition.chat_json") as cj:
        assert decompose_intent(_make_intent(), _make_plan(), _make_pack()) is None
        cj.assert_not_called()


def test_heuristic_fallback_catches_missed_overextension():
    """critique 漏判（allowed）但假设含证据未覆盖的年份 → 启发式兜底收敛。"""
    propose = {
        "title": "t", "open_question": "q", "scope_note": "s",
        "propositions": [
            {"axis": "a", "hypothesis": "某某于1945年在此秘密创办商会",
             "dimension": "building", "question": "q?"},
        ],
    }
    crit = {"verdicts": [{"index": 0, "verdict": "allowed", "rewritten_hypothesis": ""}]}
    with patch("redtrip_curator.proposition.llm_configured", return_value=True), \
         patch("redtrip_curator.proposition.chat_json", side_effect=[propose, crit]):
        ps = decompose_intent(_make_intent(), _make_plan(), _make_pack(), ["building"])
    assert ps is not None
    # 证据摘要只含 1929；1945 未覆盖 → 启发式应 neutralize
    assert ps.propositions[0].status == "rewritten"
    assert "证据可核验" in ps.propositions[0].hypothesis


def test_thread_provider_enables_proposition_without_env():
    """Bug #1 修复的端到端验证：用户经 UI 配置的 provider 注入线程后，
    即使无环境变量，decompose_intent 也能跑通命题分解（不再静默回退规则）。
    """
    import os

    from redtrip_curator.llm import clear_thread_provider, set_thread_provider

    tp = {"api_base": "https://user.example/v1", "api_key": "sk-user", "model": "gpt-4o"}
    set_thread_provider(tp)
    try:
        # 清空环境变量，确保「能跑」完全由线程级 provider 驱动
        with patch.dict(
            os.environ, {"LLM_API_BASE": "", "LLM_API_KEY": "", "LLM_MODEL": ""},
            clear=False,
        ), patch(
            "redtrip_curator.proposition.chat_json",
            side_effect=[_PROPOSE, {"verdicts": [{"index": 0, "verdict": "allowed", "rewritten_hypothesis": ""}]}],
        ):
            ps = decompose_intent(_make_intent(), _make_plan(), _make_pack(), ["building"])
        assert ps is not None
        assert ps.propositions[0].status == "allowed"
        assert ps.title == "外滩·江海关的世纪"
        assert ps.redteam_applied is False
    finally:
        clear_thread_provider()


def test_chat_json_forwards_provider():
    """chat_json 把 provider 透传给 chat_completion（Bug #1 一致性修复）。"""
    from redtrip_curator import llm as llm_mod

    with patch.object(llm_mod, "chat_completion", return_value='{"x": 1}') as cc, \
         patch.object(llm_mod, "_resolve_backend_order", return_value=["cloud"]):
        out = llm_mod.chat_json(
            system="s", user="u",
            provider={"api_base": "b", "api_key": "k", "model": "m"},
        )
    assert out == {"x": 1}
    assert cc.call_count == 1
    assert cc.call_args.kwargs.get("provider") == {"api_base": "b", "api_key": "k", "model": "m"}
