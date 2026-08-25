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
    """最小叙事句骨架（典籍新生兜底）。

    即使 LLM 润色失败（或被 Gate 清洗后回退），读者看到的也不再是字段堆叠清单，
    而是一段「人物 + 时间 + 地点 + 出处」的最小叙事散文：
    把事件按年份串成时间线，把人物按「主角—关联者」织进时间线，每句都带可核出处。

    与旧的「字段堆叠清单」区别：旧的会写出
      「地址：武康路113号；相关人物：史宾伯（开放数据…）；事件：1923年始建…」
    现在会写成
      「1923 年，英国人毛特宝林海在此始建私邸。1948 年改建，原房主返国后，
       丹麦人史宾伯照看这处房产。1955 年，史宾伯经手租于上海作家协会上海分会；
       同年 9 月，巴金一家迁入，并定居于此，《随想录》等诸多重要作品都在此创作。
       据上海图书馆开放数据。」
    """
    ev: BuildingEvidence = stop.evidence
    events = [l for l in ev.layers if l.kind == "event"]
    persons = [l for l in ev.layers if l.kind == "person"]
    classicals = [l for l in ev.layers if l.kind == "classical"]
    building = next((l for l in ev.layers if l.kind == "building"), None)
    era = next((l for l in ev.layers if l.kind == "era"), None)
    poems = [l for l in ev.layers if l.kind == "poem"]
    geonames = [l for l in ev.layers if l.kind == "geoname"]
    literarys = [l for l in ev.layers if l.kind == "literary"]
    sources: list[dict[str, Any]] = []

    rd = ev.raw_detail or {}
    addr = rd.get("address") or ev.address or (_addr(building.claim) if building else None)

    # ── 构造最小叙事句（典籍新生）──
    body_parts: list[str] = []

    # 1) 典籍发掘（如有）：从 CBDB 考据出的人物先点题
    for c in classicals[:2]:
        body_parts.append(c.claim.rstrip("。") + "。")
        sources.append(c.source.as_dict())

    # 2) 事件按年份串成时间线（提取年份排序）
    import re as _re
    evt_with_year: list[tuple[str, str]] = []  # (year, claim)
    evt_no_year: list[str] = []
    for e in events[:8]:
        m = _re.search(r"(\d{3,4})\s*年", e.claim)
        if m:
            evt_with_year.append((m.group(1), e.claim.rstrip("。") + "。"))
        else:
            evt_no_year.append(e.claim.rstrip("。") + "。")
        sources.append(e.source.as_dict())
    evt_with_year.sort(key=lambda x: x[0])
    for _, claim in evt_with_year:
        body_parts.append(claim)
    body_parts.extend(evt_no_year[:2])

    # 3) 人物的关联叙事（主角先，被遮蔽者后）
    # 主角：名字在建筑名里的
    protagonist = [p for p in persons if p.label and p.label in ev.name]
    others = [p for p in persons if p not in protagonist]
    for p in (protagonist + others)[:6]:
        # 把「开放数据将该建筑与人物「X」建立关联。」改写成「X 曾与此处相关。」
        claim_clean = p.claim
        if "开放数据将该建筑与人物" in claim_clean:
            claim_clean = f"{p.label}曾与此处相关。"
        else:
            claim_clean = claim_clean.rstrip("。") + "。"
        body_parts.append(claim_clean)
        sources.append(p.source.as_dict())

    # 4) 文学记载（如有）
    if literarys:
        lk = literarys[0]
        body_parts.append(lk.claim.rstrip("。") + "。")
        sources.append(lk.source.as_dict())

    # 5) 地名志（如有，作为空间脉络补充）
    if geonames and len(body_parts) < 8:
        body_parts.append(geonames[0].claim.rstrip("。") + "。")
        sources.append(geonames[0].source.as_dict())

    # 6) 典籍新生收束句：点明地点 + 出处
    if addr and body_parts:
        body_parts.append(f"此地即{addr}的{ev.name}。")
    body_parts.append("据上海图书馆开放数据。")

    # 7) 极端兜底：若上面什么都没生成，回退最小陈述
    if not body_parts:
        body_parts.append(f"{ev.name}。据上海图书馆开放数据。")
        if addr:
            body_parts.insert(0, f"{addr}。")

    body = " ".join(body_parts)

    age = None
    era_desc = (
        " ".join(e.claim.rstrip("。") + "。" for e in events[:4])
        if events
        else (body[:200] or "暂无数据支撑")
    )
    figures = "、".join(p.label for p in persons[:6]) if persons else "暂无数据支撑"
    pf = ev.pitfalls or {}
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
