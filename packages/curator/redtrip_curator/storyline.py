"""叙事主线检测（典籍新生 step③④ 共享）。

只基于已取证证据（人物 / 朝代 / 典籍出处 CBDB record_id）统计线索，
不臆造任何事实——与《书籍化架构》红线一致。

两个消费方：
- plan.py：narrative_bonus_map() 给每栋楼算「叙事契合度」加分，偏置选点，
  让路线自然沿一条主线铺开（城市记忆被放大、古老足迹被发掘溯源）。
- polish.py：detect_arc() 找出贯穿全本的「主线」，供润色写卷→章→节递进弧。
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from .models import BuildingEvidence

_CLASSICAL_PREFIX = "典籍 · "


def _person_names(be: BuildingEvidence) -> list[str]:
    """建筑上所有「人物 / 典籍人物」姓名（去前缀归一）。"""
    out: list[str] = []
    for l in be.layers:
        if l.kind == "person":
            out.append(l.label)
        elif l.kind == "classical" and l.label.startswith(_CLASSICAL_PREFIX):
            out.append(l.label[len(_CLASSICAL_PREFIX):])
    return out


def _dynasty_of(be: BuildingEvidence) -> str | None:
    """从 classical 图层的 source.excerpt 取朝代（_build_excerpt 把朝代放首位）。"""
    for l in be.layers:
        if l.kind == "classical" and l.source and l.source.excerpt:
            return l.source.excerpt.split("；")[0] or None
    return None


def _cbdb_ids(be: BuildingEvidence) -> list[str]:
    return [
        str(l.source.record_id)
        for l in be.layers
        if l.kind == "classical" and l.source and l.source.record_id
    ]


@dataclass
class NarrativeThreads:
    person_shared: dict[int, int] = field(default_factory=dict)
    dynasty_shared: dict[int, int] = field(default_factory=dict)
    cbdb_shared: dict[int, int] = field(default_factory=dict)
    person_count: dict[str, int] = field(default_factory=dict)
    dynasty_count: dict[str, int] = field(default_factory=dict)
    cbdb_count: dict[str, int] = field(default_factory=dict)


def collect_threads(cands: list[BuildingEvidence]) -> NarrativeThreads:
    """统计候选集内「人物 / 朝代 / 典籍出处」的共现关系。"""
    t = NarrativeThreads()
    names = {id(b): set(_person_names(b)) for b in cands}
    dyn = {id(b): _dynasty_of(b) for b in cands}
    cbdb = {id(b): set(_cbdb_ids(b)) for b in cands}

    pc: Counter = Counter()
    dc: Counter = Counter()
    cc: Counter = Counter()
    for b in cands:
        for n in names[id(b)]:
            pc[n] += 1
        if dyn[id(b)]:
            dc[dyn[id(b)]] += 1
        for r in cbdb[id(b)]:
            cc[r] += 1
    t.person_count = dict(pc)
    t.dynasty_count = dict(dc)
    t.cbdb_count = dict(cc)

    for b in cands:
        bid = id(b)
        shared_p = sum(
            1 for o in cands if o is not b and (names[bid] & names[id(o)])
        )
        shared_d = sum(
            1 for o in cands if o is not b and dyn[bid] and dyn[bid] == dyn[id(o)]
        )
        shared_c = sum(
            1 for o in cands if o is not b and (cbdb[bid] & cbdb[id(o)])
        )
        t.person_shared[bid] = shared_p
        t.dynasty_shared[bid] = shared_d
        t.cbdb_shared[bid] = shared_c
    return t


def narrative_bonus_map(cands: list[BuildingEvidence]) -> dict[int, float]:
    """每栋楼叙事主线契合度加分（典籍新生：放大城市记忆、溯源古老足迹）。

    权重：同典籍出处(CBDB 已验证溯源) 最高，其次同人物，再次同时代。
    上限封顶避免单一线索碾压类别多样性与地理连贯。
    """
    t = collect_threads(cands)
    out: dict[int, float] = {}
    for b in cands:
        bid = id(b)
        bonus = (
            min(t.cbdb_shared.get(bid, 0), 3) * 1.0
            + min(t.person_shared.get(bid, 0), 3) * 0.6
            + min(t.dynasty_shared.get(bid, 0), 3) * 0.4
        )
        out[bid] = bonus
    return out


def detect_arc(plan: Any) -> dict[str, Any]:
    """从已规划路线找出贯穿主线，供润色写「卷-章-节」叙事弧。

    仅基于证据（人物 / 朝代 / 典籍出处），不臆造。主线优先级：
    已验证典籍出处(CBDB) > 人物 > 朝代。
    """
    stops = getattr(plan, "stops", []) or []
    pc: Counter = Counter()
    dc: Counter = Counter()
    cc: Counter = Counter()
    thread_by_order: dict[int, dict[str, Any]] = {}
    for s in stops:
        be = s.evidence
        nm = set(_person_names(be))
        dy = _dynasty_of(be)
        cb = set(_cbdb_ids(be))
        thread_by_order[s.order] = {"names": nm, "dynasty": dy, "cbdb": cb}
        for n in nm:
            pc[n] += 1
        if dy:
            dc[dy] += 1
        for r in cb:
            cc[r] += 1

    main: dict[str, Any] | None = None
    if cc:
        rid, cnt = cc.most_common(1)[0]
        nm_for = ""
        for s in stops:
            if rid in thread_by_order[s.order]["cbdb"]:
                nm_for = next(iter(thread_by_order[s.order]["names"]), "")
                if nm_for:
                    break
        main = {
            "type": "classical_source",
            "key": rid,
            "label": nm_for or f"典籍人物#{rid}",
            "count": cnt,
            "orders": [s.order for s in stops if rid in thread_by_order[s.order]["cbdb"]],
        }
    elif pc:
        name, cnt = pc.most_common(1)[0]
        main = {
            "type": "person",
            "key": name,
            "label": name,
            "count": cnt,
            "orders": [s.order for s in stops if name in thread_by_order[s.order]["names"]],
        }
    elif dc:
        dy, cnt = dc.most_common(1)[0]
        main = {
            "type": "dynasty",
            "key": dy,
            "label": dy,
            "count": cnt,
            "orders": [
                s.order for s in stops if thread_by_order[s.order]["dynasty"] == dy
            ],
        }

    return {
        "main_thread": main,
        "total_stops": len(stops),
        "has_classical": any(thread_by_order[s.order]["cbdb"] for s in stops),
    }
