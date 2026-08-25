"""P0-1 回归：规划器与门禁阈值同源，长路线不再被静默打回模板。

修复前：规划器产出 4h/8h/24h 路线（duration>120、最多 12 站），门禁硬拦
`n>10` 与 `duration>120` → pipeline 静默回退到模板（ok=True），LLM 海派润色
被丢掉，用户看到"电子垃圾"。修复后：两边只读 PLAN_ENVELOPE，互相不再误杀。
"""
from types import SimpleNamespace

from redtrip_gate import PLAN_ENVELOPE, evaluate_envelope


def _full_envelope(n_stops: int, duration_min: int) -> dict:
    """构造一个 Q4 之外的门禁项都通过的 envelope（只测 Q4 矛盾是否解决）。"""
    return {
        "intent": {"duration_min": duration_min},
        "theme": "海派建筑",
        "logic_line": "梧桐区叙事主线",
        "aesthetic": "出版级散文",
        "scenario": "周末漫步",
        "why_visit": "理解城市肌理",
        "sources": [],
        "curator_note": "",
        "blocks": [{"body": "正文", "title": "标题", "lead": "引子", "coda": "尾声"}],
        "route": {
            "stops": [
                {
                    "name": f"s{i}",
                    "meaning": "文化意涵",
                    "transition_to_next": "向下一站过渡",
                    "raw_detail": {"address": f"上海徐汇区第{i}号"},
                }
                for i in range(n_stops)
            ],
            "duration_min": duration_min,
        },
    }


def _q4(blockers):
    return [b for b in blockers if "Q4" in b]


def test_envelope_bounds_cover_planner_max():
    # 规划器满档 24h → 12 站 / 480min，必须落在门禁允许区间内
    assert PLAN_ENVELOPE.max_stops >= 12
    assert PLAN_ENVELOPE.max_duration_min >= 480


def test_4h_route_not_blocked_by_q4():
    v = evaluate_envelope(_full_envelope(n_stops=8, duration_min=240))
    assert not _q4(v.blockers), v.blockers


def test_8h_route_not_blocked_by_q4():
    # 历史上必被 duration>120 / n>10 误杀 → 静默降级。修复后必须放行。
    v = evaluate_envelope(_full_envelope(n_stops=10, duration_min=480))
    assert not _q4(v.blockers), v.blockers


def test_24h_route_not_blocked_by_q4():
    v = evaluate_envelope(_full_envelope(n_stops=12, duration_min=480))
    assert not _q4(v.blockers), v.blockers


def test_planner_tier_within_envelope():
    # 任意时长档位的站数都不越界门禁上限
    from redtrip_curator.plan import _plan_tier

    for dur in (30, 60, 120, 240, 480, 1440):
        n, _ = _plan_tier(SimpleNamespace(duration_min=dur))
        assert PLAN_ENVELOPE.min_stops <= n <= PLAN_ENVELOPE.max_stops, (dur, n)
