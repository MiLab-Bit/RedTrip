from __future__ import annotations

from typing import Any

from .evidence import _road_of
from .intent import companions_enum
from .models import Intent, RoutePlan
from .storycraft import craft_route_voice, craft_stop_story, pick_hero


def _aesthetic(tone: str) -> str:
    if "硬核" in tone:
        return "史料密度优先、出处前置、克制修辞"
    if "文艺" in tone:
        return "克制、留白、海派明信片"
    return "轻量、具体、去说教"


def narrate(intent: Intent, plan: RoutePlan, sources_used: list[str]) -> dict[str, Any]:
    theme, logic, curator_note, why = craft_route_voice(plan, intent)

    # 道路脉络/容器层：把同一条马路上的站点聚成束，写入各 stop 的 road_context
    from collections import defaultdict

    _road_groups: dict[str, list] = defaultdict(list)
    for s in plan.stops:
        rn = _road_of(s.evidence)
        if rn:
            _road_groups[rn].append(s)
    for _rn, _stops in _road_groups.items():
        if len(_stops) >= 2:
            _names = "、".join(f"「{st.evidence.name}」" for st in _stops)
            for st in _stops:
                if not st.evidence.road_context:
                    st.evidence.road_context = (
                        f"{_rn}是这条线的容器：它把{_names}串成一段可被行走的脉络"
                        f"——楼是点，路才是把点连起来的那根线。"
                    )

    stops_out: list[dict[str, Any]] = []
    blocks: list[dict[str, Any]] = []
    for s in plan.stops:
        lat = s.evidence.lat if s.evidence.lat is not None else 31.22
        lng = s.evidence.lng if s.evidence.lng is not None else 121.45
        wid = s.evidence.whitelist_id or f"live-{s.order:03d}"
        pitfalls = (
            dict(s.evidence.pitfalls)
            if s.evidence.pitfalls
            else {
                "open_hours": "未收录",
                "enterable": "未收录",
                "need_reservation": "未收录",
            }
        )
        # Person layers first — relationships are the spine.
        # 关键修复：原先 layer_dicts[:10] 会把追加在最后的 geoname/literary
        # 等策展图层切掉（每栋楼有 40+ event 图层占满前 10 位）。改为保留
        # 全部非 event 图层（person/building/era/poem/geoname/literary 都是
        # 少数且重要），仅对 bulk event 图层封顶，避免策展图层被截断丢失。
        _all = [l.as_dict() for l in s.evidence.layers]
        _events = sorted(
            [d for d in _all if d.get("kind") == "event"],
            key=lambda d: {"event": 9}.get(d.get("kind"), 9),
        )
        _rest = sorted(
            [d for d in _all if d.get("kind") != "event"],
            key=lambda d: {
                "person": 0,
                "building": 2,
                "era": 3,
                "poem": 4,
                "geoname": 5,
                "literary": 6,
            }.get(d.get("kind", ""), 8),
        )
        layer_dicts = _rest + _events[:8]

        # B7：从 evidence.raw_detail 透传 landmark 字段（年份/风格/建筑设计师/简介）
        # + layers 人物，让前端可直接展示「这栋楼是何时/何人/什么风格」。
        rd = s.evidence.raw_detail or {}
        landmark = {
            k.removeprefix("landmark_"): v
            for k, v in rd.items()
            if k.startswith("landmark_") and v
        }
        characters = [
            l.label for l in s.evidence.layers if l.kind == "person"
        ]
        if landmark or characters:
            landmark["characters"] = characters

        stops_out.append(
            {
                "order": s.order,
                "whitelist_id": wid,
                "buri": s.evidence.buri,
                "name": s.evidence.name,
                "minutes": s.minutes,
                "meaning": s.meaning,
                "transition_to_next": s.transition_to_next,
                # 不再二次截断：_rest 已保留全部非 event 策展图层，
                # _events 已在上面封顶 [:8]，故 layer_dicts 已是「全量非 event + 限量 event」，
                # 此处若再 [:10] 会再次切掉低优先级的 geoname/literary。
                "layers": layer_dicts,
                "geo": {
                    "lat": lat,
                    "lng": lng,
                    "coord_source": s.evidence.coord_source
                    or ("upstream" if s.evidence.lat is not None else "none"),
                    "precision": s.evidence.precision
                    or ("approximate" if s.evidence.lat is not None else "schematic"),
                },
                "pitfalls": pitfalls,
                "landmark": landmark or None,
                # 透传 raw_detail（landmarks 已分离到 landmark 字段；raw_detail
                # 仍含 amap 内部字段如 location/type/address，前端可选展示）
                "raw_detail": rd or None,
            }
        )
        body, age, srcs, scene = craft_stop_story(s)
        persons = [l for l in s.evidence.layers if l.kind == "person"]
        events = [l for l in s.evidence.layers if l.kind == "event"]
        hero = pick_hero(persons, events, s.evidence.name)
        title = (
            f"{hero}与「{s.evidence.name}」"
            if hero
            else f"在「{s.evidence.name}」停一下"
        )
        card: dict[str, Any] = {
            "type": "story_card",
            "stop_order": s.order,
            "title": title,
            "body": body,
            "sources": srcs
            or [
                {
                    "dataset": "amap_poi",
                    # 高德 POI 点无 SLC buri；record_id 契约要求非空 string，
                    # 用 "amap:{name}" 占位（不虚构 SLC 馆藏号）。
                    "record_id": s.evidence.buri or f"amap:{s.evidence.name}",
                }
            ],
        }
        if age:
            card["age_parallel"] = age
        blocks.append(card)
        blocks.append(scene)

    people: list[str] = []
    seen: set[str] = set()
    for s in plan.stops:
        for l in s.evidence.layers:
            if l.kind == "person" and l.label not in seen:
                seen.add(l.label)
                people.append(l.label)

    blocks.append(
        {
            "type": "card",
            "title": theme,
            "lead": why,
            "keywords": [
                people[0] if people else "可溯源",
                "人物关系",
                intent.tone,
            ],
            "body": logic,
            "coda": "带一个名字离开，比带一张打卡照片离开，更接近这条线的目的。",
        }
    )

    walk_m = plan.walk_meters_est
    scenario = (
        f"{intent.audience} · {intent.companions} · "
        f"{plan.duration_min}分钟 · 步行约{walk_m}米 · {intent.scene}"
    )

    return {
        "envelope_version": "1.0",
        "intent": intent.message
        or f"{intent.companions} · {intent.duration_min}分钟 · {intent.scene} · {intent.tone}",
        "theme": theme,
        "logic_line": logic,
        "aesthetic": _aesthetic(intent.tone),
        "scenario": scenario,
        "why_visit": why,
        "curator_note": curator_note,
        "assumptions": list(intent.assumptions),
        "companions": companions_enum(intent.companions),
        "sources": list(dict.fromkeys([*sources_used, "R-20 whitelist"])),
        "route": {
            "duration_min": plan.duration_min,
            "walk_meters_est": walk_m,
            "stops": stops_out,
        },
        "blocks": blocks,
    }
