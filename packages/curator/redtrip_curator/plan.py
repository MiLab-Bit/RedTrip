from __future__ import annotations

import math
import os
import sys
from pathlib import Path

# 单一阈值真相源在 gate 包（envelope.PLAN_ENVELOPE）。plan 与 gate 都读它，
# 谁都不准再硬编码站数/时长上限——否则又会静默互相打回（P0-1）。
_GATE = Path(__file__).resolve().parents[2] / "gate"
if str(_GATE) not in sys.path:
    sys.path.insert(0, str(_GATE))
from redtrip_gate import PLAN_ENVELOPE  # noqa: E402

from .evidence import _road_of  # noqa: E402
from .models import BuildingEvidence, EvidencePack, Intent, PlannedStop, RoutePlan  # noqa: E402

# 9 大类（与地标库 categories 对齐）：culture/historic/waterfront/persona/
# nature/religion/commercial/nightlife/suburb。类别多样性约束防止路线被单
# 一集群（如陆家嘴「东方明珠系」塔群）刷屏。
_AMAP_TYPE_CATEGORY: dict[str, str] = {
    "风景名胜": "nature", "公园广场": "nature", "旅游景点": "nature",
    "历史古迹": "historic", "科教文化服务": "culture", "博物馆": "culture",
    "宗教": "religion", "教堂": "religion",
    "餐饮服务": "commercial", "购物服务": "commercial", "休闲娱乐服务": "nightlife",
    "住宿服务": "commercial",
}


def _category(b: BuildingEvidence) -> str:
    """派生建筑类别，用于「每类最多 N 站」配额。

    优先用地标库写入的 raw_detail["category"]（9 大类之一）；高德 POI 用
    raw_detail["poi_type"] 前缀映射到粗分类；都没有则归为 uncategorized。
    """
    rd = b.raw_detail or {}
    c = rd.get("category")
    if isinstance(c, str) and c:
        return c
    t = rd.get("poi_type") or ""
    if isinstance(t, str) and t:
        for prefix, cat in _AMAP_TYPE_CATEGORY.items():
            if t.startswith(prefix):
                return cat
    return "uncategorized"


def _diversity_select(
    cands: list[BuildingEvidence], target_n: int, max_per_cat: int
) -> list[BuildingEvidence]:
    """按 _score 降序选点，但每类最多 max_per_cat 站，保证路线类别多样。

    若配额导致不足 5 站，则放宽配额补齐到 5（类别多样性是体验优化，不应
    牺牲用户硬要求的「最低 5 站」）。
    """
    ordered = sorted(cands, key=_score, reverse=True)
    selected: list[BuildingEvidence] = []
    seen_ids: set[int] = set()
    cat_count: dict[str, int] = {}
    # 第一遍：严格按配额选点（类别多样性硬约束）
    for b in ordered:
        if id(b) in seen_ids:
            continue
        cat = _category(b)
        if cat_count.get(cat, 0) < max_per_cat:
            selected.append(b)
            seen_ids.add(id(b))
            cat_count[cat] = cat_count.get(cat, 0) + 1
        if len(selected) >= target_n:
            break
    # 兜底：若配额导致不足 5 站，放宽配额补齐到 5（类别多样性不牺牲
    # 用户硬要求的「最低 5 站」；放宽只补到 5，不破坏已选的配额分布）
    if len(selected) < 5:
        for b in ordered:
            if id(b) in seen_ids:
                continue
            selected.append(b)
            seen_ids.add(id(b))
            if len(selected) >= 5:
                break
    return selected


def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _score(b: BuildingEvidence) -> float:
    events = sum(1 for l in b.layers if l.kind == "event")
    persons = sum(1 for l in b.layers if l.kind == "person")
    return events * 3.0 + persons * 1.5 + (1.0 if b.lat is not None else 0.0)


def _spread_once(
    geo: list[BuildingEvidence],
    target_n: int,
    *,
    min_leg: float,
    max_leg: float,
    target_walk: float,
    first: BuildingEvidence | None = None,
) -> list[BuildingEvidence]:
    if not geo:
        return []
    ordered = sorted(geo, key=_score, reverse=True)
    start = first if first is not None else ordered[0]
    if start not in geo:
        start = ordered[0]
    route = [start]
    used = {id(start)}
    walk = 0.0

    while len(route) < target_n:
        last = route[-1]
        best: BuildingEvidence | None = None
        best_key: tuple[float, float] | None = None
        for b in ordered:
            if id(b) in used:
                continue
            dist = _haversine_m(last.lat or 0, last.lng or 0, b.lat or 0, b.lng or 0)
            if dist < min_leg or dist > max_leg:
                continue
            remain = target_walk - walk
            slots_left = max(1, target_n - len(route))
            walk_fit = -abs(dist - max(120.0, remain / slots_left))
            key = (walk_fit + _score(b) * 40.0, dist)
            if best_key is None or key > best_key:
                best_key = key
                best = b
        if best is None:
            break
        dist = _haversine_m(
            last.lat or 0, last.lng or 0, best.lat or 0, best.lng or 0
        )
        route.append(best)
        used.add(id(best))
        walk += dist
    return route


def _spread_route(
    cands: list[BuildingEvidence],
    target_n: int,
    *,
    target_walk: float,
) -> list[BuildingEvidence]:
    """候选排序 + NN 路径化。

    用户硬要求最低 5 站；外滩等密集区候选彼此相距 100-200m，原 greedy
    spread 一旦起点选错或中途被 min_leg 卡死就只能出 4 站。改为：先按
    _score 取 top_n 真地标（用户场景的候选都是真地标，去重已做完），
    再用 nearest-neighbor 路径化保证路线连贯。
    """
    geo = [b for b in cands if b.lat is not None and b.lng is not None]
    if len(geo) < 2:
        return cands[:target_n]

    target_n = min(target_n, len(geo))
    top = sorted(geo, key=_score, reverse=True)[:target_n]

    # 起点：选"距其他点中位距离最小"的中心化候选，让 NN 不易走出死胡同
    def _med_dist(b: BuildingEvidence) -> float:
        ds = sorted(
            _haversine_m(b.lat or 0, b.lng or 0, o.lat or 0, o.lng or 0)
            for o in top if o is not b
        )
        return ds[len(ds) // 2] if ds else 0.0

    start = min(top, key=_med_dist)
    rest = [b for b in top if id(b) != id(start)]
    order: list[BuildingEvidence] = [start]
    while rest:
        last = order[-1]
        rest.sort(
            key=lambda b: _haversine_m(
                last.lat or 0, last.lng or 0, b.lat or 0, b.lng or 0
            )
        )
        order.append(rest.pop(0))
    return order


def _clip(text: str, n: int = 36) -> str:
    t = text.strip()
    if len(t) <= n:
        return t
    return t[: n - 1] + "…"


def _meaning(b: BuildingEvidence) -> str:
    event = next((l for l in b.layers if l.kind == "event"), None)
    person = next((l for l in b.layers if l.kind == "person"), None)
    if person and event:
        return f"以{person.label}为主人公，在「{b.name}」读一段仍留在馆藏里的情节"
    if person:
        return f"先认{person.label}，再认「{b.name}」这栋楼"
    if event:
        return f"在「{b.name}」读用途更替：谁来过，谁离开"
    return f"辨认「{b.name}」仍可被路过的建筑身份"


def _transition(a: BuildingEvidence, b: BuildingEvidence) -> str:
    a_ev = next((l for l in a.layers if l.kind == "event"), None)
    b_ev = next((l for l in b.layers if l.kind == "event"), None)
    a_ps = [l.label for l in a.layers if l.kind == "person"]
    b_ps = [l.label for l in b.layers if l.kind == "person"]
    a_p = a_ps[0] if a_ps else None
    b_p = b_ps[0] if b_ps else None

    # 跨楼关系网：同一人物同时钉在两栋楼上 → 暗线
    shared = [n for n in a_ps if n in set(b_ps)]
    if shared:
        name = shared[0]
        return (
            f"带着{name}的名字离开「{a.name}」，去「{b.name}」——"
            f"你会发现{name}的痕迹也钉在下一站。同一个人，把两栋楼串成一条暗线。"
        )

    # 同一条马路 → 容器关系
    a_road = _road_of(a)
    b_road = _road_of(b)
    if a_road and a_road == b_road:
        return (
            f"沿着{a_road}继续走，下一站「{b.name}」也在这条路上。"
            f"同一条马路把分散的楼收成一束，你走的不是点，是一条线。"
        )

    if a_p and b_p and a_p != b_p:
        return (
            f"带着{a_p}的名字离开「{a.name}」，去「{b.name}」见{b_p}。"
            f"换的是人，连起来的是同一座城里不同的命运落点。"
        )
    if a_p and b_ev:
        return (
            f"还想着{a_p}时，下一站「{b.name}」用一句记载接住你："
            f"「{_clip(b_ev.claim, 32)}」。人退去，情节继续。"
        )
    if a_ev and b_p:
        return (
            f"刚读完「{_clip(a_ev.claim, 24)}」，去「{b.name}」找{b_p}——"
            f"从情节走到人物，故事才算立住。"
        )
    if a_ev and b_ev:
        return (
            f"上一站的情节是「{_clip(a_ev.claim, 24)}」；"
            f"下一站换成「{_clip(b_ev.claim, 24)}」。两段冲突并置，对照着读。"
        )
    return (
        f"从「{a.name}」走到「{b.name}」：舞台换了，你要找的仍是人与记载，不是距离。"
    )


def _plan_tier(intent: Intent) -> tuple[int, float]:
    """档位：短程 → 长程（4h / 8h / 24h，站点数随时长放宽）。

    返回的站数上限受 PLAN_ENVELOPE.max_stops 约束——与门禁同源，杜绝互相误杀。
    """
    if intent.duration_min <= 60:
        return 5, 1100.0
    elif intent.duration_min <= 120:
        return 6, 1700.0
    elif intent.duration_min <= 240:   # 4h
        return 8, 2600.0
    elif intent.duration_min <= 480:   # 8h
        return 10, 3400.0
    else:                              # 24h
        return 12, 4200.0


def plan_route(intent: Intent, pack: EvidencePack) -> RoutePlan:
    n, target_walk = _plan_tier(intent)

    # 最低 5 站：用户硬要求 + 步行连贯性。不足 5 时返回 Info 日志，让上层决定
    # 是否要拉更多候选（而非默默降到 3）。上限严格对齐门禁（PLAN_ENVELOPE）。
    n = max(PLAN_ENVELOPE.min_stops, min(PLAN_ENVELOPE.max_stops, n, len(pack.buildings)))
    if n < PLAN_ENVELOPE.min_stops:
        # 候选不足：把全部都上，仍要凑足下限才舒服；让 _spread_route 自然处理。
        n = min(PLAN_ENVELOPE.max_stops, len(pack.buildings))

    # 类别多样性：先按每类最多 N 站配额筛选候选，再交给 NN 路径化。
    # 陆家嘴「东方明珠系」塔群若同属一类，配额会逼出其它类别（历史/公园/商业），
    # 避免路线被单一种族刷屏。最低 5 站由 _diversity_select 兜底保证。
    max_per_cat = int(os.getenv("REDTRIP_MAX_PER_CATEGORY", "2") or 2)
    diversified = _diversity_select(pack.buildings, n, max_per_cat)
    ordered = _spread_route(diversified, n, target_walk=target_walk)
    if len(ordered) < 3:
        raise ValueError("可规划点位不足（间距筛选后 <3）")

    # 用户硬要求最低 5 站：spread 过滤后不足时，从落选候选中按「离起点最远优先」
    # 补足（最大化路线覆盖，而非就近追加）。建筑无坐标的排在末尾。
    if len(ordered) < n and len(pack.buildings) > len(ordered):
        used = {id(b) for b in ordered}
        anchor = ordered[0] if ordered and ordered[0].lat is not None else None
        rest = [b for b in pack.buildings if id(b) not in used]
        def _key(b: BuildingEvidence) -> tuple[float, int]:
            if (
                anchor is None
                or b.lat is None
                or b.lng is None
                or anchor.lat is None
                or anchor.lng is None
            ):
                return (float("-inf"), 0)  # 无坐标排最前
            # 距离最远优先 → 主路程覆盖更广
            return (-_haversine_m(b.lat, b.lng, anchor.lat, anchor.lng), 0)
        rest.sort(key=_key)
        for b in rest:
            if len(ordered) >= n:
                break
            ordered.append(b)

    walk = 0.0
    for i in range(len(ordered) - 1):
        a, b = ordered[i], ordered[i + 1]
        if a.lat is None or a.lng is None or b.lat is None or b.lng is None:
            continue
        walk += _haversine_m(a.lat, a.lng, b.lat, b.lng)

    walk_min = int(round(walk / 70.0)) if walk else 0
    walk_min = max(8, min(intent.duration_min // 3, walk_min))
    dwell_pool = max(intent.duration_min - walk_min, len(ordered) * 8)
    weights = [_score(b) + 1.0 for b in ordered]
    wsum = sum(weights) or 1.0
    raw = [max(8, int(dwell_pool * (w / wsum))) for w in weights]
    dwell_total = sum(raw) or 1
    scale = dwell_pool / dwell_total
    minutes = [max(8, min(28, int(round(m * scale)))) for m in raw]
    # 总时长压缩上限严格对齐门禁（PLAN_ENVELOPE.max_duration_min）：长程用
    # intent 本身（4h/8h/24h），但绝不越过门禁上限，避免产出被静默打回模板。
    _cap = max(PLAN_ENVELOPE.min_duration_min, min(intent.duration_min, PLAN_ENVELOPE.max_duration_min))
    while sum(minutes) + walk_min > _cap and max(minutes) > 8:
        minutes[minutes.index(max(minutes))] -= 1

    stops: list[PlannedStop] = []
    for i, b in enumerate(ordered):
        nxt = ordered[i + 1] if i + 1 < len(ordered) else None
        stops.append(
            PlannedStop(
                order=i + 1,
                evidence=b,
                minutes=minutes[i],
                meaning=_meaning(b),
                transition_to_next=_transition(b, nxt) if nxt else None,
            )
        )

    return RoutePlan(
        stops=stops,
        # 时长 cap 随档位放宽：90min 内仍收 120 上限（防溢出），
        # 4h/8h/24h 用真实合计（sum(minutes)+walk_min 本身受 stops 数约束）。
        duration_min=max(
            60, min(max(120, intent.duration_min), sum(minutes) + walk_min)
        ),
        walk_meters_est=int(round(walk)),
    )
