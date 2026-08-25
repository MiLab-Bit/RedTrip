"""plan.py 单测：评分 + 类别多样性（每类最多 N 站）+ 最低 5 站兜底。

运行：.venv/Scripts/python.exe -m pytest tests/test_plan.py -q
"""
from collections import Counter

from redtrip_curator.models import BuildingEvidence
from redtrip_curator.plan import _assign_acts, _category, _diversity_select, _score


def _be(name: str, *, category=None, poi_type=None, lat=31.23, lng=121.47) -> BuildingEvidence:
    rd = {}
    if category:
        rd["category"] = category
    if poi_type:
        rd["poi_type"] = poi_type
    return BuildingEvidence(
        buri=f"u-{name}", name=name, address=None, lat=lat, lng=lng,
        layers=[], raw_detail=rd or None, coord_source="amap", precision="approximate",
    )


def test_category_from_raw():
    assert _category(_be("a", category="historic")) == "historic"
    assert _category(_be("b", poi_type="风景名胜")) == "nature"
    assert _category(_be("c", poi_type="科教文化服务")) == "culture"
    assert _category(_be("d")) == "uncategorized"


def test_score_weights():
    base = _be("base", category="historic")
    with_event = _be("ev", category="historic")
    with_event.layers = [type(base).layers.__class__()] if False else []
    # _score 只看 layers 的 event/person 计数；无 layers 时权重=坐标加分(1.0)
    assert _score(base) == 1.0
    rich = _be("rich", category="historic")
    from redtrip_curator.models import IdentityLayer, SourceRef
    rich.layers = [
        IdentityLayer(kind="event", label="e", claim="c", source=SourceRef(dataset="x", record_id="r1")),
        IdentityLayer(kind="person", label="p", claim="c", source=SourceRef(dataset="x", record_id="r2")),
    ]
    assert _score(rich) == 3.0 + 1.5 + 1.0


def test_diversity_cap():
    """陆家嘴「东方明珠系」塔群同属 commercial，配额 2 → 最多 2 个，逼出其它类别。

    用 4 个类别各 6 候选，使「严格配额」即可凑满 ≥5 站，从而干净地验证
    每类都不超配额（不触发「兜底补齐到 5」那条放宽分支）。
    """
    cands = (
        [_be(f"c{i}", category="commercial") for i in range(6)]
        + [_be(f"h{i}", category="historic") for i in range(6)]
        + [_be(f"n{i}", category="nature") for i in range(6)]
        + [_be(f"u{i}", category="culture") for i in range(6)]
    )
    sel = _diversity_select(cands, target_n=10, max_per_cat=2)
    cnt = Counter(_category(b) for b in sel)
    assert cnt["commercial"] <= 2, cnt
    assert cnt["historic"] <= 2, cnt
    assert cnt["nature"] <= 2, cnt
    assert cnt["culture"] <= 2, cnt
    assert len(sel) == 8, cnt  # 4 类 × 配额 2 = 8，严格配额已凑满，不触发兜底


def test_diversity_floor_fills_to_five():
    """候选充裕但只有 1~2 类时，兜底补齐到 5（类别多样性不牺牲最低 5 站硬要求）。

    严格配额只能给 commercial=2 + historic=2 = 4，不足 5，故兜底再补 1 站 → 5。
    此测试显式锁定该行为：允许某一类在兜底时突破配额，但总数必达 5。
    """
    cands = [_be(f"c{i}", category="commercial") for i in range(6)] + \
            [_be(f"h{i}", category="historic") for i in range(6)]
    sel = _diversity_select(cands, target_n=10, max_per_cat=2)
    cnt = Counter(_category(b) for b in sel)
    assert len(sel) == 5, cnt
    # 兜底只补到 5，不会把两类的配额都拉满成 4+4
    assert cnt["commercial"] <= 3 and cnt["historic"] <= 3, cnt


def test_diversity_relax_min5():
    """候选不足 5 时放宽配额补齐（保证最低 5 站）。"""
    cands = [_be(f"c{i}", category="commercial") for i in range(3)]
    sel = _diversity_select(cands, target_n=10, max_per_cat=2)
    assert len(sel) == 3  # 全部候选都用上（仍 <5，但只有 3 个）


def test_assign_acts_sequence():
    assert _assign_acts(6) == [
        "prologue",
        "focus",
        "transit",
        "focus",
        "transit",
        "epilogue",
    ]
    assert _assign_acts(1) == ["prologue"]
