"""RAG 数据筛选层：把「上海该有的 POI」整库预索引，按 intent 做候选预筛。

为什么存在：之前 evidence 取数主链路（SLC building_detail / amap POI）全部依赖
密钥，无 key 时候选为空 → 路线空壳（用户口中的「电子垃圾」）。本层把本地 curated
语料（amap shanghai-landmarks.json + 免 key 的 OSM shanghai-osm.json）合并成统一
索引，让规划器在「不调 LLM / 不调外部 API」的前提下就拿到一批真实、相关、类别
多样的候选 —— 既提速（LLM 不必全城推理），又提精准（按区域/类别/时段预筛）。

仅依赖标准库 + models，可被测试直接 import，无需网络。
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .cities import get_city
from .models import BuildingEvidence, Intent

# packages/curator/redtrip_curator → RedTrip/content/curated
_CURATED = Path(__file__).resolve().parents[3] / "content" / "curated"
_EXHIBITIONS_PATH = _CURATED / "exhibitions.json"
_CACHE: dict[str, list[dict[str, Any]]] = {}
_EXHIBITIONS_CACHE: list[dict[str, Any]] | None = None

# 场景词 -> 核心地标别名（与 evidence._SCENE_ALIASES 同义但自包含，避免反向依赖）
_SCENE_ALIASES: dict[str, tuple[str, ...]] = {
    "外滩": ("外滩", "苏州河", "中山东一路", "外白渡桥"),
    "临港": ("滴水湖", "天文馆", "海昌", "海洋公园"),
    "陆家嘴": ("上海中心", "金茂", "环球金融", "东方明珠", "国金"),
    "豫园": ("豫园", "城隍庙", "九曲桥"),
    "新天地": ("新天地", "一大会址", "太平桥"),
    "北外滩": ("北外滩", "白玉兰", "滨江"),
    "徐汇滨江": ("西岸", "龙美术馆", "油罐"),
    "武康": ("武康", "巴金", "梧桐"),
    "衡山路": ("衡山路", "东平路", "汾阳路"),
    "思南": ("思南公馆", "思南路"),
    "南京路": ("南京东路", "南京路步行街"),
    "静安": ("静安寺", "愚园路"),
    "虹口": ("多伦路", "鲁迅", "1933"),
    "杨浦": ("杨浦滨江", "大学路", "五角场"),
}

_DAYPART_CAT_BONUS = {
    "night": {"waterfront", "nightlife", "commercial"},
    "suburb": {"nature", "suburb"},
    "day": {"culture", "historic", "nature", "waterfront"},
    "full": set(),
}

# ── A1 语料去噪 ────────────────────────────────────────────────────────────────
# e2e 暴露：北外滩「小巨蛋」「标识牌及黄浦江打卡位」「外滩轮渡口」等无叙事价值的
# OSM 原始点被选中，挤掉真正有策展价值的建筑/博物馆/历史点。下面用
# 「类别白名单 + 名称/osm_value 信号」两级过滤掉低叙事价值点。
#
# 1) 名称噪声信号：基础设施/指路/打卡类，无论归类为何都无策展价值。
_NOISE_NAME_RE = re.compile(
    r"(标识牌|指路牌|路牌|导览牌?|门牌|打卡|轮渡|渡口|游艇|公交|停车|充电|报刊|"
    r"自助|取票|售票|寄存|行李|厕所|卫生间|公厕|WC|雕塑(?!院|馆|场|家|园)|"
    r"花坛|岗亭|监控|栏杆|座椅|路灯|绿地|小巨蛋|饮水|月台|站台|出入口|闸机|"
    r"电梯|扶梯|楼梯|天桥|地道|便民|服务点|咨询台)"
)
# 2) OSM 侧类别丢弃：amap 词库已人工筛选，保留；OSM 的纯商业/生活配套/夜场
#    对海派文化漫步叙事价值低（clothes/gift/toys/lottery 等占 OSM 近 1/3）。
_DROP_OSM_CATEGORIES = {"commercial", "suburb", "nightlife"}
# 3) OSM value 级噪声：即使落在被保留类别内（如 leisure=sculpture/fountain
#    被归为 nature/waterfront）也算噪声，精准剔除。
_NOISE_OSM_VALUES = {
    "clothes", "gift", "toys", "lottery", "stationery", "electronics_repair",
    "floorer", "photographer", "amusement_arcade", "bowling_alley",
    "escape_game", "outdoor_seating", "dog_park", "picnic_table",
    "sculpture", "fountain",
}
# 高叙事价值锚点：在 _score 里加分，确保被规划器优先选中。
_HIGH_VALUE_OSM_VALUES = {
    "museum", "gallery", "memorial", "monument", "theatre", "library",
    "arts_centre", "exhibition_centre", "castle", "ruins",
    "archaeological_site", "attraction", "tower", "viewpoint",
    "lighthouse", "marina", "theme_park", "garden", "peak", "tomb",
}
# 名称命中即视为强锚点（建筑/人物/机构类真遗迹）。
_NAME_ANCHOR_RE = re.compile(
    r"(博物馆|美术馆|纪念馆|陈列馆|展览馆|图书馆|大剧院|剧院|故居|旧址|"
    r"遗址|天主|教堂|清真寺|庵|道观|寺|庙|洋行|公馆|大楼|银行|别墅)"
)


def _is_noise_name(name: str) -> bool:
    """仅按名称判断是否为低叙事价值点（供地标库等绕过 rag.retrieve 的路径复用）。"""
    return bool(_NOISE_NAME_RE.search(name or ""))


def _is_noise(poi: dict[str, Any]) -> bool:
    """返回 True 表示该 POI 无策展叙事价值，应从候选中剔除。"""
    if _is_noise_name(poi.get("name") or ""):
        return True
    if poi.get("source") == "osm":
        if poi.get("category") in _DROP_OSM_CATEGORIES:
            return True
        if (poi.get("raw") or {}).get("osm_value") in _NOISE_OSM_VALUES:
            return True
    return False


def _load_landmarks(curated: Path | None = None, city: str = "shanghai") -> list[dict[str, Any]]:
    curated = curated or _CURATED
    cache_key = f"{curated}:{city}"
    if cache_key in _CACHE and "landmarks" in _CACHE[cache_key]:
        return _CACHE[cache_key]["landmarks"]
    p = curated / f"{city}-landmarks.json"
    out: list[dict[str, Any]] = []
    if p.exists():
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            out = [
                {
                    "name": str(l.get("name") or ""),
                    "lat": l.get("lat"),
                    "lng": l.get("lng"),
                    "category": l.get("category_id") or "culture",
                    "source": "amap",
                    "address": l.get("address"),
                    "raw": {"amap_type": l.get("amap_type"), "category": l.get("category")},
                }
                for l in (d.get("landmarks") or [])
                if l.get("name") and l.get("lat") is not None and l.get("lng") is not None
            ]
        except Exception:  # noqa: BLE001
            out = []
    _CACHE.setdefault(cache_key, {})["landmarks"] = out
    return out


def _load_osm(curated: Path | None = None, city: str = "shanghai") -> list[dict[str, Any]]:
    curated = curated or _CURATED
    cache_key = f"{curated}:{city}"
    if cache_key in _CACHE and "osm" in _CACHE[cache_key]:
        return _CACHE[cache_key]["osm"]
    p = curated / f"{city}-osm.json"
    out: list[dict[str, Any]] = []
    if p.exists():
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            out = [
                {
                    "name": str(o.get("name") or ""),
                    "lat": o.get("lat"),
                    "lng": o.get("lng"),
                    "category": o.get("category") or "commercial",
                    "source": "osm",
                    "address": o.get("address"),
                    "raw": {
                        "osm_key": o.get("osm_key"),
                        "osm_value": o.get("osm_value"),
                        "tags": o.get("tags", {}),
                    },
                }
                for o in (d.get("pois") or [])
                if o.get("name") and o.get("lat") is not None and o.get("lng") is not None
            ]
        except Exception:  # noqa: BLE001
            out = []
    _CACHE.setdefault(cache_key, {})["osm"] = out
    return out


def _all_pois(curated: Path | None = None, city: str = "shanghai") -> list[dict[str, Any]]:
    out = _load_landmarks(curated, city) + _load_osm(curated, city)
    seen: set[tuple[str, float, float]] = set()
    dedup: list[dict[str, Any]] = []
    for p in out:
        key = (p["name"], round(p["lat"], 4), round(p["lng"], 4))
        if key in seen:
            continue
        seen.add(key)
        if _is_noise(p):  # A1：剔除低叙事价值 OSM/噪声点
            continue
        dedup.append(p)
    return dedup


def _scene_terms(scene: str, city: str = "shanghai") -> list[str]:
    if not scene:
        return []
    terms = [scene.strip()]
    terms.append(re.sub(r"(新城|地区|周边|一带|附近|区域|街道|镇)$", "", scene).strip() or scene)
    for key, vals in _SCENE_ALIASES.items():
        if key in scene or scene in key:
            terms.extend(vals)
    # 城市专属场景别名（覆盖名字不含场景词的真地标，如「西湖」之于杭州）
    for key, vals in get_city(city).aliases.items():
        if key in scene or scene in key:
            terms.extend(vals)
    return [t for t in dict.fromkeys(terms) if t]


def _score(poi: dict[str, Any], terms: list[str], daypart: str) -> int:
    s = 0
    blob = (poi["name"] + " " + (poi.get("address") or "")).lower()
    for t in terms:
        if t and t.lower() in blob:
            s += 5
    s += 2 if poi["category"] in ("culture", "historic") else 1
    bonus = _DAYPART_CAT_BONUS.get(daypart, set())
    if poi["category"] in bonus:
        s += 3
    # A1：高叙事价值锚点加分（建筑/博物馆/历史点优先于纯自然/滨水休闲）
    ov = (poi.get("raw") or {}).get("osm_value") or ""
    if ov in _HIGH_VALUE_OSM_VALUES:
        s += 2
    if _NAME_ANCHOR_RE.search(poi["name"]):
        s += 2
    return s


def retrieve(intent: Intent, top_k: int = 40, curated_dir: str | None = None) -> list[BuildingEvidence]:
    """按 intent 做数据筛选，返回预筛候选（BuildingEvidence 列表）。

    无 intent.scene 时按类别优先级返回一批代表性候选（仍保证路线非空）。
    纯本地、无网络、无 LLM。curated_dir 可注入（测试用），默认读仓库 content/curated。
    城市由 intent.city 决定（缺省上海），只取该城市的 OSM/地标语料。
    """
    daypart = getattr(intent, "daypart", "day") or "day"
    city = getattr(intent, "city", None) or "shanghai"
    terms = _scene_terms(intent.scene or "", city)
    pois = _all_pois(Path(curated_dir) if curated_dir else None, city)
    if not pois:
        return []

    scored = []
    for p in pois:
        s = _score(p, terms, daypart)
        if not terms and p["category"] not in ("culture", "historic", "nature",
                                                "waterfront"):
            s -= 1  # 无场景词时压低纯商业/生活类，优先文化自然
        scored.append((s, p))
    scored.sort(key=lambda x: -x[0])

    out: list[BuildingEvidence] = []
    for _, p in scored[:top_k]:
        raw = dict(p.get("raw") or {})
        # 顶层 category 必须与下游 _category()/_diversity_select() 读取的键一致
        raw["category"] = p["category"]
        raw["rag_category"] = p["category"]
        raw["rag_source"] = p["source"]
        out.append(
            BuildingEvidence(
                buri=None,
                name=str(p["name"]),
                address=p.get("address"),
                lat=float(p["lat"]),
                lng=float(p["lng"]),
                raw_detail=raw,
                coord_source=p["source"],
                precision="approximate",
            )
        )
    return out


def exhibition_pois(curated_dir: str | None = None, city: str = "shanghai") -> list[dict[str, Any]]:
    """返回语料中被归类为文化场馆 / 纪念馆 / 历史纪念碑的 POI（供 P0-2 回填白名单）。"""
    wanted = {"culture", "historic"}
    out = []
    for p in _load_osm(Path(curated_dir) if curated_dir else None, city) + _load_landmarks(
        Path(curated_dir) if curated_dir else None, city
    ):
        if p["category"] not in wanted:
            continue
        if _is_noise(p):  # A1：展览白名单同样剔除噪声点
            continue
        ov = (p.get("raw") or {}).get("osm_value") or ""
        if p["source"] == "osm" and not any(
            k in ov for k in ("museum", "gallery", "arts_centre", "exhibition",
                              "memorial", "monument", "theatre", "library")
        ):
            # amap 侧已按文化类词条拉取，osm 侧再按 value 收口，避免纯 historic=yes 噪音
            if p["category"] == "historic" and ov not in ("memorial", "monument", "castle", "ruins"):
                continue
        out.append(p)
    return out


def load_exhibitions(curated_dir: str | None = None, city: str = "shanghai") -> list[dict[str, Any]]:
    """读取 content/curated/exhibitions.json 占位展讯（按 city 过滤）。"""
    global _EXHIBITIONS_CACHE
    base = Path(curated_dir) if curated_dir else _CURATED
    path = base / "exhibitions.json"
    if _EXHIBITIONS_CACHE is not None and curated_dir is None:
        items = _EXHIBITIONS_CACHE
    elif not path.is_file():
        return []
    else:
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        items = doc.get("exhibitions") if isinstance(doc, dict) else []
        if not isinstance(items, list):
            items = []
        if curated_dir is None:
            _EXHIBITIONS_CACHE = items
    return [e for e in items if isinstance(e, dict) and (not e.get("city") or e.get("city") == city)]
