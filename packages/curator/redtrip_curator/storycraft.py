"""Evidence-bound micro-story craft, informed by Reedsy short-story craft:

- Character first (goals / distinct cast), then conflict over time
- Classic beats: hook → rising action → insight → now
- 2nd person immersion; start close to the action
- One theme-question per stop; no catalog / meta-data jargon

Facts may only come from Evidence layers. Missing life detail → honest gap.
"""
from __future__ import annotations

from typing import Any

from .evidence import _road_of
from .models import BuildingEvidence, PlannedStop

META_FORBIDDEN = (
    "关系边",
    "字段",
    "开放数据把",
    "数据里",
    "馆藏字段",
    "主键",
)


def _addr(building_claim: str | None) -> str:
    if not building_claim or "地址：" not in building_claim:
        return ""
    return building_claim.split("地址：", 1)[1].split("；", 1)[0].strip()


def _year_hint(claim: str) -> str:
    # pull leading year-ish token for pacing, not invention
    for i, ch in enumerate(claim):
        if ch.isdigit():
            j = i
            while j < len(claim) and (claim[j].isdigit() or claim[j] in "-–—"):
                j += 1
            return claim[i:j]
    return ""


def _role_for_person(name: str, events: list) -> str:
    """Assign a reading role from event text only — no biography invention."""
    for e in events:
        if not name or name not in e.claim:
            continue
        # More specific predicates first (avoid「原房主…史宾伯照看」误判)
        if "照看" in e.claim:
            return "曾被记载为照看这处房产的人"
        if "迁入" in e.claim or "定居" in e.claim:
            return "曾被记载迁入并定居于此"
        if "创作" in e.claim or "作品" in e.claim:
            return "曾被记载在此创作"
        if "房主" in e.claim and name in e.claim.split("房主", 1)[-1][:12]:
            return "曾被记载为房主"
        if "始建" in e.claim:
            return "名字出现在始建记载里"
        return "名字写进与此楼相关的记载"
    return "被馆藏写进这栋楼的人物关系"


def pick_hero(persons: list, events: list, building_name: str) -> str | None:
    if not persons:
        return None
    for p in persons:
        if p.label and p.label in building_name:
            return p.label
    for p in persons:
        if any(p.label in e.claim for e in events):
            return p.label
    return persons[0].label


TENSION_KW = (
    "拆", "毁", "迁", "改", "争议", "查封", "关闭", "停业", "文革", "战争",
    "火灾", "事故", "更名", "抗争", "保护", "拆除", "重建", "荒废", "腾退",
    "征用", "没收", "批斗", "轰炸", "占领", "沦陷", "枪决", "冤案", "禁令",
)


def craft_stop_story(stop: PlannedStop) -> tuple[str, str | None, list[dict[str, Any]], dict[str, Any]]:
    """档案卡骨架（非叙事）。

    模板腔已彻底删除：此函数只把该站的**可核对档案事实**陈列成清单，
    不写任何叙事句/抒情句。story_ready 预览与 LLM 润色失败时，读者看到的
    是一张诚实的事实卡（地址/类型/类别/年代/风格/人物/事件/出处），
    而不是套话。叙事正文一律由 polish 的 LLM 逐卡生成。
    """
    ev: BuildingEvidence = stop.evidence
    events = [l for l in ev.layers if l.kind == "event"]
    persons = [l for l in ev.layers if l.kind == "person"]
    building = next((l for l in ev.layers if l.kind == "building"), None)
    era = next((l for l in ev.layers if l.kind == "era"), None)
    poems = [l for l in ev.layers if l.kind == "poem"]
    geonames = [l for l in ev.layers if l.kind == "geoname"]
    literarys = [l for l in ev.layers if l.kind == "literary"]
    sources: list[dict[str, Any]] = []

    lines: list[str] = []
    rd = ev.raw_detail or {}
    addr = rd.get("address") or ev.address or (_addr(building.claim) if building else None)
    if addr:
        lines.append(f"地址：{addr}")
    if rd.get("poi_type"):
        lines.append(f"场所类型：{rd['poi_type']}")
    if rd.get("category"):
        lines.append(f"场所类别：{rd['category']}")
    if rd.get("landmark_year_built"):
        lines.append(f"建造年份：{rd['landmark_year_built']}")
    if rd.get("landmark_style"):
        lines.append(f"建筑风格：{rd['landmark_style']}")
    if rd.get("landmark_architect"):
        lines.append(f"建筑师：{rd['landmark_architect']}")
    if rd.get("landmark_description"):
        lines.append(f"建筑沿革：{rd['landmark_description']}")
    for p in persons[:4]:
        lines.append(f"相关人物：{p.label}（{p.claim}）")
        sources.append(p.source.as_dict())
    for e in events[:5]:
        lines.append(f"事件：{e.claim}")
        sources.append(e.source.as_dict())
    if era:
        lines.append(f"年代：{era.claim}")
        sources.append(era.source.as_dict())
    if poems:
        lines.append(f"诗词：{poems[0].claim}")
        sources.append(poems[0].source.as_dict())
    if geonames:
        lines.append(f"地名志：{geonames[0].claim}")
        sources.append(geonames[0].source.as_dict())
    if literarys:
        lines.append(f"文学记载：{literarys[0].claim}")
        sources.append(literarys[0].source.as_dict())
    if ev.road_context:
        lines.append(f"路段：{ev.road_context}")
    pf = ev.pitfalls or {}
    lines.append(
        f"开放：{pf.get('open_hours', '未收录')} · "
        f"可入内：{pf.get('enterable', '未收录')} · "
        f"预约：{pf.get('need_reservation', '未收录')}"
    )

    body = "；\n".join(lines) if lines else f"（{ev.name}：档案整理中）"

    age = None
    era_desc = (
        " ".join(e.claim.rstrip("。") + "。" for e in events[:4])
        if events
        else ("；".join(lines) or "暂无数据支撑")
    )
    figures = "、".join(p.label for p in persons[:6]) if persons else "暂无数据支撑"
    scene = {
        "type": "scene",
        "stop_order": stop.order,
        "place": ev.name,
        "era_desc": era_desc,
        "figures": figures,
        "city_thread": stop.meaning,
        "today": (
            f"开放 {pf.get('open_hours', '未收录')} · "
            f"可入内 {pf.get('enterable', '未收录')} · "
            f"预约 {pf.get('need_reservation', '未收录')}"
        ),
        "visual_note": "建议退至人行道外侧，将人名与年份对照着看立面，勿扰仍在使用的空间。",
    }

    # dedupe sources
    seen: set[tuple[str, str]] = set()
    uniq: list[dict[str, Any]] = []
    for s in sources:
        key = (str(s.get("dataset")), str(s.get("record_id")))
        if key in seen:
            continue
        seen.add(key)
        uniq.append(s)

    return body, age, uniq[:6], scene


def craft_route_voice(plan, intent) -> tuple[str, str, str, str]:
    """Route-level theme/logic with character as spine."""
    names = [s.evidence.name for s in plan.stops]
    people: list[str] = []
    seen: set[str] = set()
    # Prefer heroes named in building titles first
    for s in plan.stops:
        events = [l for l in s.evidence.layers if l.kind == "event"]
        persons = [l for l in s.evidence.layers if l.kind == "person"]
        h = pick_hero(persons, events, s.evidence.name)
        if h and h not in seen:
            seen.add(h)
            people.append(h)
    for s in plan.stops:
        for l in s.evidence.layers:
            if l.kind == "person" and l.label not in seen:
                seen.add(l.label)
                people.append(l.label)

    # 跨楼关系网：同一人物 或 同一条马路，把分散的点连成网
    from collections import defaultdict

    stop_persons: dict[str, list[int]] = defaultdict(list)
    stop_roads: dict[str, list[int]] = defaultdict(list)
    for each_s in plan.stops:
        for l in each_s.evidence.layers:
            if l.kind == "person":
                stop_persons[l.label].append(plan.stops.index(each_s) + 1)
        rn = _road_of(each_s.evidence)
        if rn:
            stop_roads[rn].append(plan.stops.index(each_s) + 1)
    threads = {n: st for n, st in stop_persons.items() if len(st) >= 2}
    road_threads = {r: st for r, st in stop_roads.items() if len(st) >= 2}
    thread_note = ""
    parts: list[str] = []
    for n, st in list(threads.items())[:1]:
        parts.append(f"{n}同时出现在第{'、'.join(map(str, st))}站")
    for r, st in list(road_threads.items())[:1]:
        parts.append(f"第{'、'.join(map(str, st))}站都落在{r}上")
    if parts:
        thread_note = "这条线里，" + "；".join(parts) + "——同一个名字或同一条路，把分散的楼连成一张网。"

    if people:
        theme = f"以{people[0]}为线，旁及{('、'.join(people[1:3])) or '更多名字'}"
        if len(people) == 1:
            theme = f"跟着{people[0]}的名字走一段路"
    elif any("丁香" in n for n in names):
        theme = "丁香花园那一侧的名字与年份"
    elif names:
        # 无人物时的命题兜底：用站名本身构成一个可被行走的具体命题
        theme = f"从{'到'.join(names[:3])}：{('、'.join(names[:3]))}之间的街道在发生什么"
    else:
        theme = "一条待被命名的街道"

    if people:
        logic = (
            f"整条线的主人公不是建筑目录，而是人："
            f"{'、'.join(people[:4])}的名字如何先后钉进「{names[0]}」到「{names[-1]}」。"
            f"建筑是舞台，事件是情节，人物关系才是这条线真正的张力。"
        )
        if thread_note:
            logic = logic + " " + thread_note
        curator_note = (
            f"我按『人物—冲突—年份』选这 {len(plan.stops)} 站："
            f"每站至少能叫出一个名字或一句带年的记载。"
            f"这条线先引出{people[0]}，再与其他名字对照。"
            f"衔接靠人物与记载的对照，不靠『顺路』。"
        )
    else:
        logic = "人物关系暂薄处，用事件的更替充当冲突；仍拒绝空话。"
        curator_note = (
            f"这条线人物层偏少，故以用途更替为冲突主轴，共 {len(plan.stops)} 站。"
        )

    walk_km = plan.walk_meters_est / 1000.0
    why = (
        f"约 {intent.duration_min} 分钟，步行大约 {walk_km:.1f} 公里。"
        f"像读一组短篇：每一站一个人（或一群人）的名字，"
        f"加一段仍能核对的情节，构成一次完整的行走。"
    )
    return theme, logic, curator_note, why
