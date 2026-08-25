"""artifacts.py 单测：跨 stop 去重 + 多源权威度排序（SLC>curated>amap）。

运行：.venv/Scripts/python.exe -m pytest tests/test_artifacts.py -q
"""
from redtrip_curator.artifacts import EvidenceFact, _evidence_clusters, _fact_dedup_key
from redtrip_curator.models import (
    BuildingEvidence,
    IdentityLayer,
    PlannedStop,
    RoutePlan,
    SourceRef,
)


def _layer(kind, label, dataset, rid):
    return IdentityLayer(
        kind=kind, label=label, claim=f"{label} claim",
        source=SourceRef(dataset=dataset, record_id=rid),
    )


def _stop(be, order):
    return PlannedStop(order=order, evidence=be, minutes=10, meaning="m", transition_to_next=None)


def _be_with_layers(layers):
    return BuildingEvidence(
        buri="u", name="n", address=None, lat=31.2, lng=121.4, layers=layers,
        raw_detail={"category": "historic"}, coord_source="amap", precision="approximate",
    )


def test_dedup_key_stable():
    """同一 (kind,label,dataset) 应映射到同一去重 key；fact_uri 为空也能跨 stop 去重。"""
    a = _fact_dedup_key(EvidenceFact(
        fact_uri="", label="马勒", assertion="马勒 claim",
        layer="person", source_dataset="amap", confidence=0.0,
    ))
    b = _fact_dedup_key(EvidenceFact(
        fact_uri="r1", label="马勒", assertion="different claim",
        layer="person", source_dataset="amap", confidence=1.0,
    ))
    assert a == b  # 去重只看 (layer,label,source_dataset)，忽略 fact_uri/assertion


def test_authority_order():
    """同维度事实按 SLC(0) > curated(1) > amap(2) 排序。"""
    be = _be_with_layers([
        _layer("person", "甲", "amap", "a1"),
        _layer("person", "乙", "building_detail", "b1"),
    ])
    plan = RoutePlan(stops=[_stop(be, 1)], duration_min=60, walk_meters_est=100)
    clusters, _ = _evidence_clusters(plan, "theme-x")
    pcl = next(c for c in clusters if c.dimension == "person")
    assert pcl.facts[0].source_dataset == "building_detail"
    assert pcl.facts[-1].source_dataset == "amap"


def test_cross_stop_dedup():
    """同一人物跨两个 stop 只入一次 evidence_graph。"""
    shared = _layer("person", "马勒", "amap", "r-maller")
    be1 = _be_with_layers([shared, _layer("event", "e1", "building_detail", "e1")])
    be2 = _be_with_layers([shared, _layer("event", "e2", "building_detail", "e2")])
    plan = RoutePlan(
        stops=[_stop(be1, 1), _stop(be2, 2)], duration_min=60, walk_meters_est=200
    )
    clusters, flat = _evidence_clusters(plan, "theme-x")
    pcl = next(c for c in clusters if c.dimension == "person")
    # 「马勒」只应出现一次
    maller = [f for f in pcl.facts if f.label == "马勒"]
    assert len(maller) == 1, [f.label for f in pcl.facts]
