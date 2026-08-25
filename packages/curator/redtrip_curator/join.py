from __future__ import annotations

from .models import BuildingEvidence, EvidencePack


def join_layers(pack: EvidencePack) -> EvidencePack:
    """Score / sort buildings for multi-layer identity.

    用户硬要求最低 5 站。原阈值 score >= 2 会过滤掉 amap-only 候选
    （无 layer，但有 lat/lng），导致外滩场景下 pack.buildings 从 23
    削到 4——也是最初"只有三个地标"的根因。
    改为：保留所有有坐标的候选（DB landmark 注入 + amap 实时都能进路线），
    layer 数只作排序权重（多 layer 优先），不再硬过滤少 layer 的。
    """
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
        if b.lat is not None and b.lng is not None:
            score += 1
        # 有 lat/lng 即可入路线（阈值 >=2 放宽到 >=1，让 amap-only 真景点不被削）
        if score >= 1:
            enriched.append(b)
    if not enriched:
        enriched = list(pack.buildings)
    # Sort: more layers first, geo-ready first
    enriched.sort(
        key=lambda b: (
            -sum(1 for l in b.layers if l.kind == "event"),
            -sum(1 for l in b.layers if l.kind == "person"),
            0 if b.lat is not None else 1,
        )
    )
    pack.buildings = enriched
    return pack
