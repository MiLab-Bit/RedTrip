"""evidence.py 中 RAG keyless 兜底的接线测试。

验证：候选不足时 _scene_rag_corpus 会调用 rag.retrieve 并把结果并入 buildings，
且包裹成 (buildings, sources, gaps) 元组、source 标记正确。
"""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "curator"))
from redtrip_curator.models import BuildingEvidence  # noqa: E402


@pytest.fixture
def _patch(monkeypatch):
    from redtrip_curator import evidence  # noqa: E402

    fake = [BuildingEvidence(
        buri=None, name="RAG候选点", address=None, lat=31.2, lng=121.4,
        raw_detail={"rag": 1}, coord_source="osm", precision="approximate",
    )]
    monkeypatch.setattr(evidence, "_rag_retrieve", lambda intent, top_k: fake)
    return evidence


def test_scene_rag_corpus_wires_retrieve(_patch):
    intent = SimpleNamespace(scene="外滩", daypart="day")
    b, src, gap = _patch._scene_rag_corpus(intent, 5)
    assert len(b) == 1 and b[0].name == "RAG候选点"
    assert src == ["RAG 全量 POI 筛选"]
    assert gap == []


def test_scene_rag_corpus_handles_empty(_patch):
    _patch._rag_retrieve = lambda intent, top_k: []  # type: ignore[assignment]
    intent = SimpleNamespace(scene="外滩", daypart="day")
    b, src, gap = _patch._scene_rag_corpus(intent, 5)
    assert b == [] and gap and "空" in gap[0]["note"]
