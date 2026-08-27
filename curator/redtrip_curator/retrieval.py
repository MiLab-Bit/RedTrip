"""RedTrip · 语料检索层（Wikidata 真实实体 + 高德实时 POI 双源）。

让任意地点都能拉到真实建筑 + 真实坐标 + 史实，取代非梧桐区完全依赖 LLM 现编
的路线生成（治本）。

检索策略（三级，越往后越兜底）：
  1. 高德实时 POI（主，新鲜度最高）：场景中心(地理编码) -> poi_around 取周边
     真实场馆/地标/商业/餐饮，按城市漫步相关类目过滤；并叠加 poi_text(场景)
     关键词定向补充。坐标/类型 100% 真实。
  2. Wikidata 语料（史实最厚）：与 POI 同名实体优先用语料的 claim(史实)，
     补强叙事；地理/关键词检索补足场景周边历史建筑。
  3. LLM 现编（最后兜底，在 pipeline 层，不在本模块）。

依赖：.geocode.geocode_address（高德地理编码，含上海 bbox 回退）
      .amap_client（高德 POI/天气/步行等全接口，env-gated）
"""
from __future__ import annotations

import json
import logging
import math
from pathlib import Path

from .models import BuildingEvidence, IdentityLayer, SourceRef
from . import amap_client

logger = logging.getLogger("redtrip.retrieval")

CORPUS_PATH = Path(__file__).resolve().parent / "poi_corpus" / "cleaned.jsonl"
MAX_RADIUS_M = 30000  # 取中心点 30km 内的语料实体
POI_RADIUS_M = 3000    # 高德周边搜索半径
_CACHE: list[dict] | None = None

# 城市漫步相关的 POI 类目关键词（用于从周边搜索结果里筛出"值得走"的点）
_INTEREST = (
    "风景名胜", "博物馆", "文化", "纪念馆", "故居", "公园", "购物", "餐饮",
    "历史", "广场", "宗教", "寺", "教堂", "学校", "科研", "展览", "美术馆",
    "图书馆", "体育", "地标", "遗址", "古镇", "老街", "主题公园", "植物园",
)

# 繁→简最小映射（仅用于展示/匹配，不改 name）
_TRAD2SIMP = {
    "遺": "遗", "樓": "楼", "機": "机", "鐵": "铁", "車": "车", "園": "园",
    "館": "馆", "產": "产", "設": "设", "備": "备", "區": "区", "線": "线",
    "體": "体", "醫": "医", "療": "疗", "學": "学", "術": "术", "圖": "图",
    "書": "书", "築": "筑", "類": "类", "項": "项", "張": "张", "時": "时",
    "東": "东", "號": "号", "場": "场", "來": "来", "開": "开", "關": "关",
    "會": "会", "後": "后", "處": "处", "點": "点", "階": "阶", "總": "总",
    "員": "员", "賓": "宾",
}


def _simp(s: str) -> str:
    if not s:
        return s
    return "".join(_TRAD2SIMP.get(ch, ch) for ch in s)


def _norm_name(s: str) -> str:
    return _simp(str(s or "")).replace(" ", "").replace("（", "(").replace("）", ")")


def load_corpus(path: Path | None = None) -> list[dict]:
    """加载清洗后的语料（模块级缓存，仅首次读盘）。"""
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    p = path or CORPUS_PATH
    rows: list[dict] = []
    if not p.exists():
        logger.warning("corpus not found: %s", p)
        _CACHE = rows
        return rows
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                o = json.loads(line)
            except json.JSONDecodeError:
                continue
            if o.get("lat") is None or o.get("lng") is None:
                continue
            rows.append(o)
    _CACHE = rows
    logger.info("corpus loaded: %d entities from %s", len(rows), p)
    return rows


def _haversine(lat1, lng1, lat2, lng2) -> float:
    r = 6371000.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def _keyword_score(entity: dict, scene: str) -> int:
    s = scene.strip()
    if not s:
        return 0
    name = _simp(str(entity.get("name") or ""))
    desc = _simp(str(entity.get("desc") or ""))
    cats = [_simp(str(c)) for c in (entity.get("category") or [])]
    score = 0
    if s in name or name in s:
        score += 5
    for c in cats:
        if c and c in s:
            score += 3
    if s in desc:
        score += 2
    return score


def _is_interesting(poi_type: str | None) -> bool:
    if not poi_type:
        return False
    return any(k in poi_type for k in _INTEREST)


# 地标/景点类目（用于语料候选排序时优先，避免路线被大学/车站/街道淹没）
_LANDMARK_CATS = (
    "风景名胜", "博物馆", "纪念馆", "故居", "公园", "遗址", "地标",
    "宗教", "美术馆", "图书馆", "展览", "文化", "海洋公园", "主题公园",
    "古镇", "老街",
)


def _corpus_is_landmark(e: dict) -> bool:
    blob = " ".join(str(c) for c in (e.get("category") or [])) + " " + str(e.get("name") or "")
    return any(k in blob for k in _LANDMARK_CATS)


def retrieve_buildings(scene: str, k: int = 10) -> list[BuildingEvidence]:
    """给定场景名，返回真实候选建筑（corpus + 高德实时 POI 合并）。

    高德 POI 优先保证"真实存在 + 真实坐标 + 类目新鲜"；corpus 同名实体补强史实。
    无结果返回 []。
    """
    from .geocode import geocode_address
    from . import amap_client

    corpus = load_corpus()
    if not scene:
        return []

    # 地理编码：先不带城市解析（保真）；若中心落在上海 bbox 外
    # （如「外滩」被解析到惠州、「临港新城」到四川），用 city=上海 重试纠偏。
    SHANGHAI_BBOX = (30.60, 120.80, 31.95, 122.10)
    center = geocode_address(scene)
    if center is None or not (
        SHANGHAI_BBOX[0] <= center[0] <= SHANGHAI_BBOX[2]
        and SHANGHAI_BBOX[1] <= center[1] <= SHANGHAI_BBOX[3]
    ):
        center = geocode_address(scene, city="上海")

    # ---- 1) 高德实时 POI（主） ----
    live: list[dict] = []
    if center and amap_client._key_ready():
        clat, clng = center
        around = amap_client.poi_around(clng, clat, radius=POI_RADIUS_M, offset=25)
        for p in around:
            if _is_interesting(p.get("type")) and p.get("lat") is not None:
                live.append(p)
        # 关键词定向补充（如"博物馆"场景直接拉相关场馆）
        for p in amap_client.poi_text(scene, city="上海", offset=15):
            if _is_interesting(p.get("type")) and p.get("lat") is not None:
                live.append(p)

    # ---- 2) Wikidata 语料（史实补强 + 周边历史建筑） ----
    # 关键词命中优先（解决地理编码歧义，如「外滩」）
    kw_scored = [( _keyword_score(e, scene), e) for e in corpus]
    kw_scored = [(s, e) for s, e in kw_scored if s > 0]
    kw_scored.sort(key=lambda x: x[0], reverse=True)

    geo_sorted: list[tuple[float, dict]] = []
    if center:
        clat, clng = center
        for e in corpus:
            try:
                d = _haversine(clat, clng, float(e["lat"]), float(e["lng"]))
            except (TypeError, ValueError):
                continue
            geo_sorted.append((d, e))
        geo_sorted.sort(key=lambda x: x[0])

    # ---- 3) 合并：语料(史实)优先，高德实时 POI 补缺，混合去重取 k ----
    seen_norm: set[str] = set()
    corpus_list: list[BuildingEvidence] = []
    live_list: list[BuildingEvidence] = []

    # 3a) 语料候选：关键词命中优先（解决地理编码歧义）；地理候选按
    #     「地标优先 + 距离」排序（30km 内），避免路线被大学/车站/街道淹没。
    for _, e in kw_scored:
        b = _to_building(e, None)
        n = _norm_name(b.name)
        if n not in seen_norm:
            seen_norm.add(n)
            corpus_list.append(b)
    geo_ranked: list[tuple[float, dict]] = []
    for d, e in geo_sorted:
        if d > MAX_RADIUS_M:
            continue
        n = _norm_name(e.get("name"))
        if n in seen_norm:
            continue
        seen_norm.add(n)
        boost = 5000.0 if _corpus_is_landmark(e) else 0.0
        geo_ranked.append((boost - d, e))
    geo_ranked.sort(key=lambda x: x[0], reverse=True)
    for _, e in geo_ranked:
        corpus_list.append(_to_building(e, None))

    # 3b) 高德实时 POI：与语料同名则跳过（语料 claim 更厚），否则作为新鲜候选补缺
    for p in live:
        n = _norm_name(p.get("name"))
        if n in seen_norm:
            continue
        seen_norm.add(n)
        live_list.append(_to_poi_building(p))

    # 3c) 语料优先，但为高德实时 POI 预留名额（让"真实新鲜"的场馆一定能进路线）
    cap_corpus = k if not live_list else max(3, k - 4)
    merged = [*corpus_list[:cap_corpus], *live_list][:k]

    # 行政区标注：仅对最终入选的 ≤k 个建筑做逆地理（控制配额/延迟），best-effort 降级。
    # 注意：绝不能在 _to_building 里做——该函数对全部语料实体调用，会触发数百次逆地理。
    if amap_client._key_ready():
        for b in merged:
            if b.lat is not None and b.lng is not None and not b.district:
                try:
                    b.district = amap_client.district_of(b.lng, b.lat)
                except Exception:  # noqa: BLE001
                    pass
    return merged


def _to_building(e: dict, dist_m: float | None) -> BuildingEvidence:
    qid = str(e.get("id") or "")
    name = str(e.get("name") or "")
    desc = _simp(str(e.get("desc") or name))
    cats = [_simp(str(c)) for c in (e.get("category") or [])]
    cat_claim = "；".join(cats) if cats else ""
    claim = desc if desc else cat_claim
    layers = [
        IdentityLayer(
            kind="building",
            label=name,
            claim=claim,
            source=SourceRef(dataset="wikidata", record_id=qid, excerpt=claim[:180] or None),
        )
    ]
    if cat_claim:
        layers.append(
            IdentityLayer(
                kind="building",
                label="类别",
                claim=f"类别：{cat_claim}",
                source=SourceRef(dataset="wikidata", record_id=qid),
            )
        )
    if dist_m is not None:
        layers.append(
            IdentityLayer(
                kind="building",
                label="距场景中心",
                claim=f"距「场景中心」约 {int(dist_m)} 米",
                source=SourceRef(dataset="wikidata_geo", record_id=qid),
            )
        )
    return BuildingEvidence(
        buri=f"wikidata://{qid}",
        name=name,
        address=None,
        lat=float(e["lat"]),
        lng=float(e["lng"]),
        layers=layers,
        coord_source="upstream",
        precision="exact",
    )


def _to_poi_building(p: dict) -> BuildingEvidence:
    name = str(p.get("name") or "")
    poi_id = str(p.get("poi_id") or _norm_name(name))
    ptype = str(p.get("type") or "")
    addr = str(p.get("address") or "")
    claim = f"类别：{ptype}" + (f"；地址：{addr}" if addr else "")
    layers = [
        IdentityLayer(
            kind="building",
            label=name,
            claim=claim,
            source=SourceRef(dataset="amap_poi", record_id=poi_id, excerpt=claim[:180] or None),
        )
    ]
    return BuildingEvidence(
        buri=f"amap://{poi_id}",
        name=name,
        address=addr or None,
        lat=p["lat"],
        lng=p["lng"],
        layers=layers,
        coord_source="upstream",
        precision="exact",
    )
