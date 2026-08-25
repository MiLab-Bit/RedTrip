"""RAG 数据筛选层单测：检索、场景/时段加权、展览抽取。

用法：.venv/Scripts/python.exe -m pytest tests/test_rag.py -q
"""
import json
from pathlib import Path
from types import SimpleNamespace

from redtrip_curator.models import BuildingEvidence
from redtrip_curator.rag import exhibition_pois, retrieve


def _write_corpus(d: Path, landmarks: list, osm: list) -> None:
    (d / "shanghai-landmarks.json").write_text(
        json.dumps({
            "version": 1, "built_at": "x", "source": "x",
            "categories": [], "landmarks": landmarks,
        }), encoding="utf-8",
    )
    (d / "shanghai-osm.json").write_text(
        json.dumps({
            "version": 1, "built_at": "x", "source": "x", "license": "x",
            "count": len(osm), "pois": osm,
        }), encoding="utf-8",
    )


def _osm(name, cat, val, lat=31.23, lng=121.47, tags=None):
    return {"name": name, "category": cat, "osm_key": "amenity", "osm_value": val,
            "address": name, "lat": lat, "lng": lng, "tags": tags or {}}


def test_retrieve_returns_buildingevidence(tmp_path):
    _write_corpus(tmp_path,
        [{"name": "外滩历史建筑A", "category_id": "historic", "amap_type": "风景名胜",
          "address": "中山东一路", "lat": 31.24, "lng": 121.49}],
        [_osm("外滩观景台", "waterfront", "tower", 31.245, 121.49),
         _osm("浦东美术馆", "culture", "gallery", 31.23, 121.51)],
    )
    intent = SimpleNamespace(scene="外滩", daypart="day")
    out = retrieve(intent, top_k=10, curated_dir=str(tmp_path))
    assert out and all(isinstance(b, BuildingEvidence) for b in out)
    assert len(out) <= 10
    # 外滩相关点应排在前段
    assert any("外滩" in b.name for b in out[:3])


def test_retrieve_empty_corpus_returns_empty(tmp_path):
    _write_corpus(tmp_path, [], [])
    intent = SimpleNamespace(scene="外滩", daypart="day")
    assert retrieve(intent, top_k=10, curated_dir=str(tmp_path)) == []


def test_retrieve_night_prefers_waterfront(tmp_path):
    _write_corpus(tmp_path, [],
        [_osm("外滩夜景", "waterfront", "tower", 31.24, 121.49),
         _osm("某博物馆", "culture", "museum", 31.22, 121.47)],
    )
    intent = SimpleNamespace(scene="外滩", daypart="night")
    out = retrieve(intent, top_k=10, curated_dir=str(tmp_path))
    assert out[0].name == "外滩夜景"


def test_retrieve_no_scene_prioritizes_culture(tmp_path):
    _write_corpus(tmp_path, [],
        [_osm("咖啡店甲", "commercial", "cafe", 31.22, 121.47),
         _osm("历史纪念馆", "historic", "memorial", 31.22, 121.47),
         _osm("街心公园", "nature", "park", 31.22, 121.47)],
    )
    intent = SimpleNamespace(scene="", daypart="day")
    out = retrieve(intent, top_k=10, curated_dir=str(tmp_path))
    # 无场景词时文化/历史/自然优先于纯商业
    assert out[0].name == "历史纪念馆"


def test_exhibition_pois_filters_culture(tmp_path):
    _write_corpus(tmp_path, [],
        [_osm("浦东美术馆", "culture", "gallery"),
         _osm("普通咖啡店", "commercial", "cafe")],
    )
    ex = exhibition_pois(str(tmp_path))
    names = {e["name"] for e in ex}
    assert "浦东美术馆" in names
    assert "普通咖啡店" not in names


# ── A1 语料去噪 ────────────────────────────────────────────────────────────────
def test_a1_noise_names_filtered(tmp_path):
    """名称噪声信号（轮渡/标识牌/小巨蛋/打卡）必须被剔除，不得入线。"""
    _write_corpus(tmp_path, [],
        [_osm("外滩轮渡口", "waterfront", "ferry_terminal", 31.245, 121.49),
         _osm("标识牌及黄浦江打卡位", "waterfront", "information", 31.245, 121.49),
         _osm("小巨蛋", "culture", "arts_centre", 31.24, 121.48),
         _osm("北外滩白玉兰", "culture", "tower", 31.245, 121.50)],
    )
    intent = SimpleNamespace(scene="北外滩", daypart="day")
    out = retrieve(intent, top_k=40, curated_dir=str(tmp_path))
    names = {b.name for b in out}
    assert "外滩轮渡口" not in names
    assert "标识牌及黄浦江打卡位" not in names
    assert "小巨蛋" not in names
    # 真实锚点保留
    assert "北外滩白玉兰" in names


def test_a1_drop_low_value_osm_categories(tmp_path):
    """OSM 纯商业/生活/夜场类别默认丢弃（amap 不受影响）。"""
    _write_corpus(tmp_path,
        [{"name": "外滩历史建筑A", "category_id": "historic", "amap_type": "风景名胜",
          "address": "中山东一路", "lat": 31.24, "lng": 121.49}],
        [_osm("某服装店", "commercial", "clothes", 31.22, 121.47),
         _osm("某夜店", "nightlife", "nightclub", 31.22, 121.47),
         _osm("某纪念馆", "historic", "memorial", 31.22, 121.47)],
    )
    intent = SimpleNamespace(scene="", daypart="day")
    out = retrieve(intent, top_k=40, curated_dir=str(tmp_path))
    names = {b.name for b in out}
    assert "某服装店" not in names
    assert "某夜店" not in names
    # amap 与高价值 OSM 保留
    assert "外滩历史建筑A" in names
    assert "某纪念馆" in names


def test_a1_high_value_anchor_ranked_first(tmp_path):
    """高叙事价值锚点（博物馆/历史点）应排在无价值自然点之前。"""
    _write_corpus(tmp_path, [],
        [_osm("无名绿地广场", "nature", "park", 31.22, 121.47),
         _osm("上海邮政博物馆", "culture", "museum", 31.24, 121.47),
         _osm("外滩历史纪念馆", "historic", "memorial", 31.24, 121.47)],
    )
    intent = SimpleNamespace(scene="", daypart="day")
    out = retrieve(intent, top_k=40, curated_dir=str(tmp_path))
    top3 = {b.name for b in out[:3]}
    assert "上海邮政博物馆" in top3
    assert "外滩历史纪念馆" in top3


def test_a1_is_noise_name_flags_e2e_noise():
    """回归：e2e 暴露的 4 个噪声名必须被名称判定拦截；真地标不得误杀。"""
    from redtrip_curator.rag import _is_noise_name
    for n in ("外滩轮渡口", "北外滩滨江绿地小巨蛋",
              "北外滩滨江绿地-标识牌及黄浦江打卡位", "北外滩国客中心游艇港"):
        assert _is_noise_name(n), n
    for n in ("外滩历史建筑A", "上海邮政博物馆", "外白渡桥", "浦东美术馆",
              "中山东一路18号"):
        assert not _is_noise_name(n), n


def test_a1_landmark_db_excludes_noise():
    """回归：_scene_landmark_db（直接读 shanghai-landmarks.json 的真实路径）
    在「外滩」场景下不得吐出轮渡口/小巨蛋/标识牌/游艇港等噪声点。"""
    from redtrip_curator.evidence import _scene_landmark_db
    from redtrip_curator.models import Intent
    intent = Intent(scene="外滩 南京东路 历史文化漫步", duration_min=240,
                    tone="文艺", audience="深度文化爱好者", delivery="导览",
                    companions="独自", assumptions=[], daypart="day")
    buildings, _, _ = _scene_landmark_db(intent, limit=40)
    names = {b.name for b in buildings}
    noise = {"外滩轮渡口", "北外滩滨江绿地小巨蛋",
             "北外滩滨江绿地-标识牌及黄浦江打卡位", "北外滩国客中心游艇港"}
    assert not (names & noise), f"噪声点漏入候选：{names & noise}"
    # 真实地标仍在
    assert names, "候选不应为空"
