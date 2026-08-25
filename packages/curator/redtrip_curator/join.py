from __future__ import annotations

import math
import re

from .models import BuildingEvidence, EvidencePack


def _norm_name(name: str) -> str:
    """规范化建筑名用于同名判据：去空格/标点/书名号/常见后缀。"""
    n = re.sub(r"[\s\u3000《》「」『』（）()·\-—·]", "", name or "")
    # 去掉常见后缀让"武康大楼"与"武康大楼（武康路）"匹配
    n = re.sub(r"(故居|纪念馆|旧址|遗址|旧居|别墅|公馆|大楼|大厦|花园|洋房)$", "", n)
    return n


def _haversine_m(a: BuildingEvidence, b: BuildingEvidence) -> float:
    """两建筑间距离（米）。无坐标返回 inf。"""
    if a.lat is None or a.lng is None or b.lat is None or b.lng is None:
        return float("inf")
    r = 6371000.0
    p1, p2 = math.radians(a.lat), math.radians(b.lat)
    dphi = math.radians(b.lat - a.lat)
    dlmb = math.radians(b.lng - a.lng)
    x = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(x))


# 同坐标近邻阈值（米）：小于此距离视为同一实体
_GEO_MERGE_THRESHOLD_M = 50.0


def _merge_pair(keep: BuildingEvidence, drop: BuildingEvidence) -> BuildingEvidence:
    """把 drop 合并进 keep：layers 取并集（按 label 去重）、坐标取精度更高、raw_detail 合并。"""
    # layers 并集（按 (kind, label) 去重）
    seen = {(l.kind, l.label) for l in keep.layers}
    for l in drop.layers:
        key = (l.kind, l.label)
        if key not in seen:
            keep.layers.append(l)
            seen.add(key)

    # 坐标：优先取有坐标且 coord_source 更可信的（upstream > amap > none）
    _rank = {"upstream": 2, "amap": 1, "none": 0}
    if drop.lat is not None and (
        keep.lat is None
        or _rank.get(drop.coord_source, 0) > _rank.get(keep.coord_source, 0)
    ):
        keep.lat, keep.lng = drop.lat, drop.lng
        keep.coord_source = drop.coord_source
        keep.precision = drop.precision

    # raw_detail 合并（drop 不覆盖 keep 已有键）
    if drop.raw_detail:
        if keep.raw_detail is None:
            keep.raw_detail = {}
        for k, v in drop.raw_detail.items():
            keep.raw_detail.setdefault(k, v)

    # whitelist_id：优先保留非空
    if not keep.whitelist_id and drop.whitelist_id:
        keep.whitelist_id = drop.whitelist_id
    # buri：优先保留非空
    if not keep.buri and drop.buri:
        keep.buri = drop.buri
    # road_context：优先保留非空
    if not keep.road_context and drop.road_context:
        keep.road_context = drop.road_context

    return keep


def _merge_duplicates(buildings: list[BuildingEvidence]) -> list[BuildingEvidence]:
    """实体合并：同名（规范化后）或坐标近邻(<50m)的候选合并成一个。

    解决"同一建筑被 SLC/amap/landmarks 多源命中，当成多个独立候选"的问题。
    采用贪心 Union-Find：第一个出现的作为 keep，后续匹配的合并进去。
    """
    if len(buildings) < 2:
        return buildings

    merged: list[BuildingEvidence] = []
    # 预计算规范化名
    norms = [_norm_name(b.name) for b in buildings]

    for i, b in enumerate(buildings):
        placed = False
        for j, m in enumerate(merged):
            # 同名判据
            same_name = norms[i] and norms[i] == _norm_name(m.name)
            # 近邻判据
            close = _haversine_m(b, m) <= _GEO_MERGE_THRESHOLD_M
            if same_name or close:
                _merge_pair(m, b)
                placed = True
                break
        if not placed:
            merged.append(b)
    return merged


def join_layers(pack: EvidencePack) -> EvidencePack:
    """实体合并 + 打分排序。

    改动（典籍新生 step②）：
    1. 先做实体合并（同名/坐标<50m → 合并 layers 与坐标），消除多源重复候选；
    2. 再按既有逻辑打分排序（保留原 score>=1 保留策略与排序键）。

    用户硬要求最低 5 站。原阈值 score >= 2 会过滤掉 amap-only 候选
    （无 layer，但有 lat/lng），导致外滩场景下 pack.buildings 从 23
    削到 4——也是最初"只有三个地标"的根因。
    改为：保留所有有坐标的候选（DB landmark 注入 + amap 实时都能进路线），
    layer 数只作排序权重（多 layer 优先），不再硬过滤少 layer 的。
    """
    # === step② 新增：实体合并（在打分前，消除多源重复） ===
    pack.buildings = _merge_duplicates(pack.buildings)

    enriched: list[BuildingEvidence] = []
    for b in pack.buildings:
        kinds = {layer.kind for layer in b.layers}
        score = 0
        if "building" in kinds:
            score += 1
        if "event" in kinds:
            score += 3
        if "person" in kinds:
            score += 2
        # 典籍层加权（classical 是典籍新生的核心信号）
        if "classical" in kinds:
            score += 2
        if b.lat is not None and b.lng is not None:
            score += 1
        # 有 lat/lng 即可入路线（阈值 >=2 放宽到 >=1，让 amap-only 真景点不被削）
        if score >= 1:
            enriched.append(b)
    if not enriched:
        enriched = list(pack.buildings)
    # Sort: more layers first, geo-ready first, classical-attached first
    enriched.sort(
        key=lambda b: (
            -sum(1 for l in b.layers if l.kind == "event"),
            -sum(1 for l in b.layers if l.kind == "person"),
            -sum(1 for l in b.layers if l.kind == "classical"),  # 典籍层优先
            0 if b.lat is not None else 1,
        )
    )
    pack.buildings = enriched
    return pack
