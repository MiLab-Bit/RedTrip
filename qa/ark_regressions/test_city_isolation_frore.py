"""City isolation regression tests, adapted from Ark 37698 / frore 90664.

These tests exercise actual RedTrip evidence functions, unlike the earlier
standalone contract placeholder. Keep failing assertions visible until fixed.
"""
from __future__ import annotations

from types import SimpleNamespace

from redtrip_curator import evidence
from redtrip_curator.models import BuildingEvidence, Intent


def _intent(city="beijing", scene="故宫"):
    return Intent(
        audience="成人", scene=scene, duration_min=120, tone="文艺",
        delivery="导览", companions="朋友", assumptions=[],
        daypart="day", city=city,
    )


class _NoListingClient:
    def building_list(self, _query):
        return SimpleNamespace(ok=False, data=None)


def test_beijing_amap_query_must_use_selected_city(monkeypatch):
    calls = []

    class FakeAmap:
        def place_text(self, keywords, city="021", offset=20, page=1):
            calls.append(city)
            return [
                {"name": f"北京测试景点{i}", "address": "北京市测试地址",
                 "lng": 116.40 + i / 1000, "lat": 39.90 + i / 1000,
                 "type": "风景名胜;公园广场"}
                for i in range(3)
            ]

    monkeypatch.setattr(evidence, "AmapClient", FakeAmap)
    monkeypatch.setattr(evidence, "_scene_landmark_db", lambda intent, limit: ([], [], []))
    monkeypatch.setattr(evidence, "_scene_geonames_places", lambda client, scene: [])

    buildings, _sources, _gaps = evidence._scene_amap(
        _NoListingClient(), _intent(), limit=5
    )
    assert calls and len(buildings) == 3
    assert all(city in {"beijing", "北京", "010"} for city in calls), calls


def test_shanghai_whitelist_cannot_fallback_for_beijing(monkeypatch):
    attempted_batches = []
    monkeypatch.setattr(evidence, "_scene_amap", lambda client, intent, limit: ([], [], []))

    def fake_fetch_batch(client, batch, whitelist, limit):
        attempted_batches.append(list(batch))
        result = []
        for buri, expected_name in batch[:3]:
            point = whitelist.for_buri(buri)
            result.append(BuildingEvidence(
                buri=buri, name=point.name if point else expected_name,
                address="上海测试地址", lat=point.lat if point else 31.2,
                lng=point.lng if point else 121.4,
                whitelist_id=point.id if point else None,
                coord_source="manual", precision="approximate",
            ))
        return result, ["qa fake SLC"], []

    monkeypatch.setattr(evidence, "_fetch_batch", fake_fetch_batch)
    monkeypatch.setattr(evidence, "_scene_rag_corpus", lambda intent, limit: ([], [], []))
    monkeypatch.setattr(evidence, "gather_partner_evidence", lambda city: ([], [], []))

    pack = evidence.fetch_evidence(_NoListingClient(), _intent(), limit=5)
    assert not attempted_batches, (
        f"Beijing request used Shanghai whitelist; leaked buildings: "
        f"{[b.name for b in pack.buildings]}"
    )
