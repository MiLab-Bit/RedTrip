"""P0-2 验收：R-20 白名单 points.json 必须含文化场馆/纪念馆锚点、元数据非 null。

未运行 build_exhibition_whitelist.py 前 points.json 仅 30 条梧桐区/一大周边点，
本测试会 skip；生成后必须全部通过。
"""
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PTS = ROOT / "content" / "whitelist" / "points.json"


def _load():
    return json.loads(PTS.read_text(encoding="utf-8"))


def test_points_has_exhibitions():
    doc = _load()
    pts = doc.get("points", [])
    if len(pts) <= 30:
        pytest.skip("P0-2 尚未生成（points.json 仍仅 30 条）")

    # 1) 元数据三字段非 null
    for p in pts:
        assert p.get("open_hours") is not None
        assert p.get("enterable") is not None
        assert p.get("need_reservation") is not None
        assert p.get("district_tag")  # 粗标行政区非空

    # 2) 确为扩张：>30 条
    assert len(pts) > 30

    # 3) 存在展览/文化类锚点（新增 OSM 点 source=osm）
    osm_added = [p for p in pts if p.get("coord_source") == "osm"]
    assert osm_added, "未发现 OSM 并入的文化场馆锚点"
    # 4) 诚实约定：未做上图映射的 OSM 点 buri 必须为空；
    #    已通过 SLC 真实映射的点允许保留 http://data.library.sh.cn/… URI。
    for p in osm_added:
        buri = p.get("buri")
        if buri is None:
            continue
        assert str(buri).startswith("http://data.library.sh.cn/"), (
            f"OSM 点 {p.get('name')!r} 的 buri 不是上图 URI: {buri!r}"
        )
