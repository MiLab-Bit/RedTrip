from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

from redtrip_library import SlcClient
from redtrip_library.amap import AmapClient
from redtrip_library.providers import gather_partner_evidence

from .models import BuildingEvidence, EvidencePack, IdentityLayer, Intent, SourceRef
from .rag import _is_noise_name
from .rag import retrieve as _rag_retrieve
from .whitelist import Whitelist, WhitelistPoint, load_whitelist
from .classics import attach_classical_layers  # 典籍源（CBDB）

# ---------------------------------------------------------------------------
# 本地策展语料：地名志 / 文学交集（静态兜底）
# SLC geonames 端点在带 key 后可返回（实测「外滩」命中外滩街道/外滩）；
# 本地 JSON 语料仅作为其失败/空结果时的静态兜底。匹配优先级：
# 先按建筑名（places），再按路名（roads，由 _road_of 抽取）。
# ---------------------------------------------------------------------------
_CORPUS_DIR = Path(__file__).resolve().parent / "corpus"
_CURATED_DIR = Path(__file__).resolve().parent.parent.parent.parent / "content" / "curated"


@lru_cache(maxsize=4)
def _load_landmark_facts() -> list[dict[str, Any]]:
    """加载本地 curated 词库（外滩万国建筑等历史风貌区核心建筑+人物+简介）。

    命中 amap POI 时把 description / characters / year_built / style 注入
    BuildingEvidence.raw_detail，并把 characters 转 IdentityLayer（kind=person），
    让 polish 拆卡拿到真素材（地址/类型/简介/人物）而非凭空套话。
    """
    out: list[dict[str, Any]] = []
    if not _CURATED_DIR.exists():
        return out
    for f in sorted(_CURATED_DIR.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if isinstance(data, list):
                out.extend([x for x in data if isinstance(x, dict)])
            elif isinstance(data, dict):
                for v in data.values():
                    if isinstance(v, list):
                        out.extend([x for x in v if isinstance(x, dict)])
        except Exception:  # noqa: BLE001 —— 词库错就当空
            continue
    return out


def _match_landmark(
    name: str, facts: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """按 name 或 alias 模糊匹配 landmark；返回第一条命中的词条。"""
    if not name:
        return None
    n = name.strip()
    for entry in facts:
        keys = [entry.get("name"), *(entry.get("alias") or [])]
        for k in keys:
            if not k:
                continue
            if n == k or n in k or k in n:
                return entry
    return None


# 历史风貌区场景识别：副搜时附「万国建筑/历史建筑」等词命中真正的景点
# （外滩1-18 号等历史建筑），而不是购物中心/SOHO/广场等商业 POI。
HERITAGE_SCENE_KEYWORDS = (
    "外滩", "陆家嘴", "南京西路", "思南", "茂名", "巨鹿", "陕西南", "武康",
    "新华", "愚园", "衡山", "湖南", "汾阳", "复兴", "思北路", "北外滩",
)
_GENERIC_AUX = ("景区", "景点")
_HERITAGE_AUX = (
    "万国建筑", "历史建筑", "老建筑", "博物馆", "建筑博览群", "名宅", "公馆",
)

# 场景词 → 核心地标检索词（覆盖名字不含场景词的真地标，如「临港新城」的
# 滴水湖/天文馆/海昌，「陆家嘴」的上海中心/金茂/环球金融/东方明珠）。
# RAG 分级词库的检索扩展：先按别名词在已分级词条里命中，命中 >=3 即用。
_SCENE_ALIASES: dict[str, tuple[str, ...]] = {
    "外滩": ("外滩", "苏州河外滩", "中山东一路", "外白渡桥"),
    "临港": ("滴水湖", "临港", "天文馆", "海昌", "海洋公园"),
    "陆家嘴": ("上海中心", "金茂", "环球金融", "东方明珠", "陆家嘴", "国金"),
    "豫园": ("豫园", "城隍庙", "九曲桥", "沉香阁"),
    "新天地": ("新天地", "一大会址", "太平桥"),
    "北外滩": ("北外滩", "白玉兰广场", "北外滩滨江"),
    "徐汇滨江": ("西岸", "徐汇滨江", "龙美术馆"),
    "武康": ("武康", "巴金", "梧桐"),
    "衡山路": ("衡山路", "东平路", "汾阳路"),
    "思南": ("思南公馆", "思南路"),
    "南京路": ("南京东路", "南京路步行街", "大丸百货"),
    "静安": ("静安寺", "愚园路", "静安嘉里"),
    "虹口": ("多伦路", "鲁迅", "1933", "北外滩"),
    "杨浦": ("杨浦滨江", "大学路", "五角场"),
    "世纪公园": ("世纪公园", "世纪大道"),
}


def _aux_keywords(scene: str) -> tuple[str, ...]:
    if any(kw in scene for kw in HERITAGE_SCENE_KEYWORDS):
        # 历史风貌区：加「万国建筑/历史建筑/博物馆」副词命中核心建筑
        return _GENERIC_AUX + _HERITAGE_AUX
    return _GENERIC_AUX


@lru_cache(maxsize=8)
def _load_landmark_db(city: str = "shanghai") -> dict[str, Any]:
    """加载城市地标分类词库（packages/tools/build_landmarks.py 批量预拉取）。

    结构：{version, built_at, categories:[{id,label,dayparts}],
    landmarks:[{id,name,category_id,category,amap_type,address,lat,lng}]}
    —— 分类词条分级入库，检索时按场景词命中即用，不再依赖实时高德。
    按城市加载 <city>-landmarks.json（默认上海）。
    """
    p = _CURATED_DIR / f"{city}-landmarks.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 —— 词库损坏当空
        return {}


def _scene_landmark_db(
    intent: Intent, limit: int
) -> tuple[list[BuildingEvidence], list[str], list[dict[str, str]]]:
    """在地标库按场景词检索（RAG 词条分级预拉取）。

    命中 >=3 直接返回（点位真实、带分类号与 curated 简介）；不足 3 时返回
    已命中的点，由调用方叠加实时 amap 结果兜底。daypart 过滤：点所在分类
    的 dayparts 必须覆盖当前时段（night 只留夜景/滨水/商业等可夜游类目）。
    """
    city = getattr(intent, "city", None) or "shanghai"
    db = _load_landmark_db(city)
    landmarks = db.get("landmarks") or []
    if not landmarks:
        return [], [], [{"subject": "地标库", "note": f"{city}-landmarks.json 未生成或为空"}]
    cats = {c["id"]: c for c in db.get("categories") or []}
    scene = (intent.scene or "").strip()
    daypart = getattr(intent, "daypart", "day") or "day"
    if not scene:
        return [], [], []
    slim = re.sub(r"(新城|地区|周边|一带|附近|区域|街道|镇)$", "", scene).strip() or scene

    # 别名扩展：场景词命中别名表 → 用核心地标词检索（滴水湖/三件套等名字
    # 不含场景词的真地标），否则退回 name 包含场景词。
    terms: list[str] = [scene, slim]
    for key, vals in _SCENE_ALIASES.items():
        if key in scene or scene in key:
            terms.extend(vals)

    matched: list[dict[str, Any]] = []
    for lm in landmarks:
        name = lm.get("name") or ""
        cid = lm.get("category_id") or ""
        cdp = (cats.get(cid) or {}).get("dayparts") or ["day", "full"]
        if daypart != "full" and daypart not in cdp:
            continue
        if any(t and t in name for t in terms):
            # A1 语料去噪：地标库同样剔除无叙事价值的噪声点
            # （轮渡口/标识牌/小巨蛋/游艇港等），与 rag.retrieve 共用同一判定。
            if _is_noise_name(name):
                continue
            matched.append(lm)

    if not matched:
        return (
            [],
            [],
            [{"subject": "地标库", "note": f"「{scene}」未命中已分级词条"}],
        )

    landmark_facts = _load_landmark_facts()
    buildings: list[BuildingEvidence] = []
    for lm in matched[:limit]:
        name = str(lm.get("name") or "")
        lk = _match_landmark(name, landmark_facts)
        raw: dict[str, Any] = {
            "poi_type": lm.get("amap_type") or "",
            "address": lm.get("address"),
            "category": lm.get("category"),
            "category_id": lm.get("category_id"),
            "amap_location": f"{lm.get('lng')},{lm.get('lat')}",
        }
        if lk:
            for k in ("description", "year_built", "style", "architect"):
                if lk.get(k):
                    raw[f"landmark_{k}"] = lk[k]
        be = BuildingEvidence(
            buri=None,
            name=name,
            address=lm.get("address"),
            lat=lm.get("lat"),
            lng=lm.get("lng"),
            raw_detail=raw,
            coord_source="amap",
            precision="approximate",
        )
        if lk and lk.get("characters"):
            for ch in lk["characters"]:
                be.layers.append(
                    IdentityLayer(
                        kind="person",
                        label=str(ch),
                        claim=f"{name}相关人物",
                        source=SourceRef(
                            dataset="curated.landmark-facts",
                            record_id=str(ch),
                        ),
                    )
                )
        buildings.append(be)
    return buildings, ["地标库分类词条"], []


@lru_cache(maxsize=2)
def _load_corpus(name: str) -> dict[str, Any]:
    p = _CORPUS_DIR / name
    if not p.exists():
        return {}
    try:
        with p.open(encoding="utf-8") as f:
            return json.load(f)
    except Exception:  # noqa: BLE001
        return {}


def _corpus_lookup(corpus: dict[str, Any], name: str | None, road: str | None):
    """返回 (entry_or_list, key_used)；places 优先于 roads。

    匹配优先级：① 直接键名 → ② 别名/包含（建筑可能以别名、路名另一写法、
    或「路名+门牌」出现；地名志 alias 字段常存外文名/旧名/门牌号）。
    仅当无直接命中时才走别名，避免误伤精确键。
    """
    places = corpus.get("places") or {}
    roads = corpus.get("roads") or {}

    # ① 直接键名
    if name and name in places:
        return places[name], name
    if road and road in roads:
        return roads[road], road

    # ② 别名 / 包含匹配（only when no exact hit）
    if name:
        for k, v in places.items():
            alias = (v.get("alias") or "") if isinstance(v, dict) else ""
            if alias and (name == alias or name in alias or alias in name):
                return v, k
        for k, v in roads.items():
            alias = (v.get("alias") or "") if isinstance(v, dict) else ""
            if alias and (name == alias or name in alias or alias in name):
                return v, k
    if road:
        for k, v in roads.items():
            if k != road and (road in k or k in road):
                return v, k
    return None, None


def _was_attached(be: "BuildingEvidence", kind: str) -> bool:
    return any(l.kind == kind for l in be.layers)


def _attach_corpus_layers(be: "BuildingEvidence") -> None:
    """把地名志 / 文学交集 作为一等公民图层挂到建筑证据上。"""
    road = _road_of(be)
    name = be.name

    # 地名志
    if not _was_attached(be, "geoname"):
        entry, key = _corpus_lookup(_load_corpus("geonames.json"), name, road)
        if isinstance(entry, dict) and entry.get("note"):
            be.layers.append(
                IdentityLayer(
                    kind="geoname",
                    label=f"地名 · {key}",
                    claim=entry["note"],
                    source=SourceRef(
                        dataset="geonames_corpus",
                        # 缺失真实标识时置 None（而非占位 "?"），让 Gate G4 能真正校验
                        record_id=key or name or None,
                        excerpt=(entry.get("alias") or "")[:120] or None,
                    ),
                )
            )

    # 文学交集（事实性引用，不引受版权保护原文）
    if not _was_attached(be, "literary"):
        entry, key = _corpus_lookup(_load_corpus("literary.json"), name, road)
        if isinstance(entry, list):
            for item in entry[:2]:
                if isinstance(item, dict) and item.get("relation"):
                    author = item.get("author", "")
                    work = item.get("work", "")
                    # 语料 work 字段可能已含《》：如「《家》《春》《秋》」
                    # 已含书名号则原样使用，避免《《...》》嵌套
                    w = work if "《" in work else (f"《{work}》" if work else "")
                    be.layers.append(
                        IdentityLayer(
                            kind="literary",
                            label=f"文学 · {author}" if author else "文学交集",
                            claim=f"{author}{w}：{item['relation']}",
                            source=SourceRef(
                                dataset="literary_corpus",
                                record_id=key or name or None,
                                excerpt=item.get("source", "")[:120] or None,
                            ),
                        )
                    )


def _as_list(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    for key in ("data", "result", "list", "buildings", "items"):
        val = payload.get(key)
        if isinstance(val, list):
            return [x for x in val if isinstance(x, dict)]
        if isinstance(val, dict):
            for k2 in ("list", "items", "data", "result"):
                if isinstance(val.get(k2), list):
                    return [x for x in val[k2] if isinstance(x, dict)]
    return []


def _uri_of(item: dict[str, Any]) -> str | None:
    for k in ("uri", "buri", "id", "buildingUri", "building_uri"):
        v = item.get(k)
        if isinstance(v, str) and len(v) > 8:
            return v
    return None


def _name_of(item: dict[str, Any]) -> str:
    for k in ("name", "title", "buildingName", "label"):
        v = item.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return "未命名建筑"


def _coords(detail: dict[str, Any]) -> tuple[float | None, float | None]:
    loc = detail.get("location")
    if isinstance(loc, list) and loc:
        first = loc[0]
        if isinstance(first, dict):
            try:
                lat = float(first.get("lat"))
                lng = float(first.get("long") or first.get("lng") or first.get("lon"))
                return lat, lng
            except (TypeError, ValueError):
                return None, None
    return None, None


def _apply_whitelist_geo(be: BuildingEvidence, wp: WhitelistPoint | None) -> None:
    """Prefer R-20 geo/pitfalls; keep upstream only when whitelist missing."""
    if wp is None:
        return
    be.whitelist_id = wp.id
    be.pitfalls = wp.pitfalls()
    be.photo_spot = wp.photo_spot
    # NG-10: use whitelist lat/lng as authoritative for v1
    be.lat = wp.lat
    be.lng = wp.lng
    be.coord_source = wp.coord_source
    be.precision = wp.precision
    if wp.name:
        be.name = wp.name


def _build_from_detail(
    *,
    uri: str,
    detail: dict[str, Any],
    item_name: str,
    event_rows: list[dict[str, Any]],
    event_dataset: str,
    wp: WhitelistPoint | None,
) -> BuildingEvidence:
    lat, lng = _coords(detail)
    name = str(detail.get("name") or item_name)
    address = detail.get("address") if isinstance(detail.get("address"), str) else None

    be = BuildingEvidence(
        buri=uri,
        name=name,
        address=address,
        lat=lat,
        lng=lng,
        raw_detail=detail,
        coord_source="upstream" if lat is not None else "none",
        precision="approximate" if lat is not None else "schematic",
    )

    building_bits = [name]
    if address:
        building_bits.append(f"地址：{address}")
    if detail.get("created"):
        building_bits.append(f"始建/创建相关记载：{detail.get('created')}")
    if detail.get("architecturalStyle"):
        building_bits.append(f"风格记载：{detail.get('architecturalStyle')}")
    struct = str(detail.get("architectureStructure") or "").strip()
    building_excerpt = struct[:180] if struct else "；".join(building_bits)[:180]
    be.layers.append(
        IdentityLayer(
            kind="building",
            label="建筑",
            claim="；".join(building_bits),
            source=SourceRef(
                dataset="building_detail",
                record_id=uri,
                excerpt=building_excerpt or None,
            ),
        )
    )

    relations = detail.get("relation")
    if isinstance(relations, list):
        for rel in relations[:4]:
            if not isinstance(rel, dict):
                continue
            pname = rel.get("name")
            puri = rel.get("uri")
            if not isinstance(pname, str) or not pname.strip():
                continue
            be.layers.append(
                IdentityLayer(
                    kind="person",
                    label=pname.strip(),
                    claim=f"开放数据将该建筑与人物「{pname.strip()}」建立关联。",
                    source=SourceRef(
                        dataset="building_detail.relation",
                        record_id=str(puri or uri),
                        excerpt=pname.strip(),
                    ),
                )
            )

    for row in event_rows:
        if not isinstance(row, dict):
            continue
        desc = row.get("description") or row.get("title") or row.get("name")
        if not isinstance(desc, str) or not desc.strip():
            continue
        when = row.get("startedAtTime") or row.get("eventdate") or ""
        label = f"{when}事件" if when else "事件"
        claim = desc.strip()
        if when and when not in claim:
            claim = f"{when}：{claim}"
        rid = str(row.get("event") or row.get("uri") or uri)
        be.layers.append(
            IdentityLayer(
                kind="event",
                label=label,
                claim=claim,
                source=SourceRef(
                    dataset=event_dataset,
                    record_id=rid,
                    excerpt=desc.strip()[:180],
                ),
            )
        )

    # era 层：从建造年 + 内嵌事件时间轴抽取"纪年线"（零新 API）
    era_claim = _build_era_claim(detail)
    if era_claim:
        be.layers.append(
            IdentityLayer(
                kind="era",
                label="纪年",
                claim=era_claim,
                source=SourceRef(
                    dataset="building_detail.timeline",
                    record_id=uri,
                    excerpt=era_claim[:180],
                ),
            )
        )

    _apply_whitelist_geo(be, wp)
    return be


def _build_era_claim(detail: dict[str, Any]) -> str | None:
    """从建造年 + 内嵌事件时间轴抽取『纪年线』（零新 API）。"""
    nodes: list[tuple[str, str]] = []
    created = detail.get("created")
    if isinstance(created, str) and created.strip():
        nodes.append((created.strip(), "始建"))
    events = detail.get("event")
    if isinstance(events, list):
        for row in events:
            if not isinstance(row, dict):
                continue
            y = row.get("startedAtTime") or row.get("eventdate") or ""
            desc = row.get("description") or row.get("title") or ""
            if not isinstance(desc, str) or not desc.strip():
                continue
            short = desc.strip()
            if y and short.startswith(str(y)):
                short = short[len(str(y)):].lstrip("年，、。 ").strip()
            if y:
                nodes.append((str(y), short))
    if not nodes:
        return None

    def _ykey(n: tuple[str, str]) -> int:
        m = re.match(r"(\d{3,4})", n[0])
        return int(m.group(1)) if m else 9999

    nodes.sort(key=_ykey)
    seen_y: set[str] = set()
    picked: list[str] = []
    for y, d in nodes:
        if y in seen_y:
            continue
        seen_y.add(y)
        snippet = d[:22]
        picked.append(f"{y} {snippet}".strip() if snippet else y)
        if len(picked) >= 6:
            break
    if not picked:
        return None
    return "时间轴上的几个节点：" + "；".join(picked) + "。"


def _build_poem_layer(resp: Any, name: str, uri: str):
    """从搜韵(sou-yun)响应构造 poem IdentityLayer；无诗则返回 None。"""
    if not resp or not getattr(resp, "ok", False):
        return None
    data = getattr(resp, "data", None)
    if not isinstance(data, dict):
        return None
    shi = data.get("ShiData")
    if not isinstance(shi, list) or not shi:
        return None
    lines: list[str] = []
    for poem in shi[:2]:
        if not isinstance(poem, dict):
            continue
        title_obj = poem.get("Title")
        title = title_obj.get("Content") if isinstance(title_obj, dict) else title_obj
        if not title:
            continue
        author = poem.get("Author")
        dynasty = poem.get("Dynasty")
        clauses = poem.get("Clauses") or []
        first = ""
        if isinstance(clauses, list) and clauses:
            c0 = clauses[0]
            first = c0.get("Content") if isinstance(c0, dict) else str(c0)
        head = f"{dynasty or ''} {author or ''}《{title}》" if (author or dynasty) else f"《{title}》"
        line = head + (f"：『{first}』" if first else "")
        lines.append(line.strip())
    if not lines:
        return None
    claim = "历代文人以此地为题留下诗作，如 " + "；".join(lines) + "。"
    return IdentityLayer(
        kind="poem",
        label="诗词",
        claim=claim,
        source=SourceRef(
            dataset="souyun_poem",
            record_id=name or uri,
            excerpt=claim[:180],
        ),
    )


# 路段脉络（road）：同一条马路上的建筑共享一次查询，模块级缓存去重
_ROAD_CACHE: dict[str, str | None] = {}


def _road_name_of(detail: dict[str, Any], address: str | None) -> str | None:
    """从地址/详情里抽取路名（武康路、淮海中路…），用于查 road_list。"""
    candidates: list[str] = []
    for v in (address, detail.get("road"), detail.get("street"), detail.get("address")):
        if isinstance(v, str) and v.strip():
            candidates.append(v.strip())
    for c in candidates:
        m = re.search(r"([\u4e00-\u9fa5]{1,8}(?:路|道路|大道|大街|街|弄|巷))", c)
        if m:
            return m.group(1)
    return None


def _road_of(be: "BuildingEvidence") -> str | None:
    """从建筑 raw_detail 抽取路名，供路线级「同一条马路」聚类使用。"""
    if not be.raw_detail:
        return None
    addr = be.raw_detail.get("address")
    return _road_name_of(be.raw_detail, addr if isinstance(addr, str) else None)


def _road_claim(resp: Any) -> str | None:
    if not resp or not getattr(resp, "ok", False):
        return None
    data = getattr(resp, "data", None)
    rows = _as_list(data) if isinstance(data, dict) else (data if isinstance(data, list) else [])
    if not rows:
        return None
    row = rows[0]
    if not isinstance(row, dict):
        return None
    bits: list[str] = []
    for k in ("name", "alias", "anotherName", "description", "history", "built", "builtYear", "built_year", "note"):
        v = row.get(k)
        if isinstance(v, str) and v.strip():
            bits.append(v.strip())
    if not bits:
        for v in row.values():
            if isinstance(v, str) and len(v) > 4:
                bits.append(v)
                break
    if not bits:
        return None
    return "；".join(bits)[:160]


def _road_cache_get(client: SlcClient, name: str) -> str | None:
    if name in _ROAD_CACHE:
        return _ROAD_CACHE[name]
    try:
        claim = _road_claim(client.road(name))
    except Exception:  # noqa: BLE001
        claim = None
    _ROAD_CACHE[name] = claim
    return claim


def _fetch_one(
    client: SlcClient,
    uri: str,
    *,
    item_name: str,
    wl: Whitelist,
    sources_used: list[str],
    gaps: list[dict[str, str]],
) -> BuildingEvidence | None:
    detail_resp = client.building_detail(uri)
    sources_used.append("building_detail")
    if not detail_resp.ok or not isinstance(detail_resp.data, dict):
        gaps.append({"subject": uri, "note": "暂无数据支撑"})
        return None

    detail_wrap = detail_resp.data
    detail = detail_wrap.get("data") if isinstance(detail_wrap.get("data"), dict) else detail_wrap
    if not isinstance(detail, dict):
        gaps.append({"subject": uri, "note": "暂无数据支撑"})
        return None

    ev_resp = client.event_list(uri)
    sources_used.append("event_list")
    event_rows = _as_list(ev_resp.data) if ev_resp.ok else []
    embedded = detail.get("event")
    if isinstance(embedded, list):
        for row in embedded:
            if isinstance(row, dict):
                event_rows.append(row)

    wp = wl.for_buri(uri)
    be = _build_from_detail(
        uri=uri,
        detail=detail,
        item_name=item_name,
        event_rows=event_rows,
        event_dataset="event_list" if ev_resp.ok else "building_detail.event",
        wp=wp,
    )

    # poem 层（搜韵诗词关联 —— 沪小游 6.2 万 POI 不具备的跨库差异化维度）
    try:
        poem_resp = client.poem(item_name)
        sources_used.append("souyun_poem")
        poem_layer = _build_poem_layer(poem_resp, item_name, uri)
        if poem_layer is not None:
            be.layers.append(poem_layer)
    except Exception:  # noqa: BLE001 — 诗词缺失/超时不影响主流程
        pass

    # road 层（路段脉络 —— 漫步的容器；SLC road_list 已有但此前未接入）
    try:
        road_name = _road_name_of(detail, detail.get("address") if isinstance(detail.get("address"), str) else None)
        if road_name:
            claim = _road_cache_get(client, road_name)
            if claim:
                be.road_context = claim
    except Exception:  # noqa: BLE001
        pass

    # 地名志 / 文学交集（本地策展语料，SLC 端点返回空时的承接层）
    try:
        _attach_corpus_layers(be)
    except Exception:  # noqa: BLE001
        pass

    has_event = any(l.kind == "event" for l in be.layers)
    if be.lat is None or be.lng is None:
        if not has_event:
            return None
    return be


def _fetch_batch(
    client: SlcClient,
    items: list[tuple[str, str]],
    wl: Whitelist,
    limit: int,
) -> tuple[list[BuildingEvidence], list[str], list[dict[str, str]]]:
    """Concurrently fetch a batch of buildings (方案C).

    Each worker returns its own (be, sources, gaps) so there is no shared-list
    contention. Pool size is capped well below SLC's headroom.
    """
    buildings: list[BuildingEvidence] = []
    sources_used: list[str] = []
    gaps: list[dict[str, str]] = []
    if not items:
        return buildings, sources_used, gaps
    capped = items[:limit]
    workers = min(12, len(capped))

    def _worker(arg: tuple[str, str]) -> tuple[
        BuildingEvidence | None, list[str], list[dict[str, str]]
    ]:
        uri, name = arg
        local_sources: list[str] = []
        local_gaps: list[dict[str, str]] = []
        be = _fetch_one(
            client,
            uri,
            item_name=name,
            wl=wl,
            sources_used=local_sources,
            gaps=local_gaps,
        )
        return be, local_sources, local_gaps

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for be, s, g in pool.map(_worker, capped):
            if be is not None:
                buildings.append(be)
            sources_used.extend(s)
            gaps.extend(g)
            if len(buildings) >= limit:
                break
    return buildings, sources_used, gaps


def _scene_whitelist(intent: Intent, wl: Whitelist) -> tuple[list[WhitelistPoint], bool]:
    """按场景词匹配白名单；返回 (points, matched)。

    matched=False 表示场景词未命中白名单任何关键词/名称（如「外滩」「临港」），
    调用方应改用通用场景通道（高德 POI + SLC 地名志），而非直接吃全量白名单。
    """
    scene = intent.scene or ""
    if any(k in scene for k in ("一大", "兴业", "黄陂", "石库门")):
        tagged = wl.filter_by_district("一大周边")
        if tagged:
            return tagged, True
    if any(
        k in scene
        for k in (
            "武康",
            "梧桐",
            "华山",
            "衡山",
            "安福",
            "湖南",
            "思南",
            "巴金",
            "宋庆龄",
            "Wukang",
            "wukang",
        )
    ):
        tagged = wl.filter_by_district("梧桐区")
        if tagged:
            return tagged, True
    # Name / corridor substring against whitelist labels
    name_hits = [
        p
        for p in wl.points
        if p.name and (p.name in scene or scene.replace("一带", "").replace("周边", "") in p.name)
    ]
    if name_hits:
        return name_hits, True
    # default: prefer mapped buris (多重人生), then all —— 未命中，标记 false
    mapped = [p for p in wl.points if p.buri]
    return (mapped or list(wl.points)), False


def _scene_geonames_places(client: SlcClient, scene: str) -> list[dict[str, str]]:
    """SLC 地名志检索：场景词 → [{name, uri, description}]（权威沿革锚点）。

    地名志是「全上海」的主题库（区别于武康路建筑库），覆盖外滩/豫园等；
    描述（description）是策展可引用的权威沿革文本。
    """
    if not scene:
        return []
    try:
        r = client.call("geonames_list", {"freetext": scene})
    except Exception:  # noqa: BLE001 —— 取证层统一降级
        return []
    if not r.ok:
        return []
    items = _as_list(r.data)
    out: list[dict[str, str]] = []
    for it in items[:6]:
        uri = _uri_of(it)
        if not uri:
            continue
        desc = ""
        try:
            d = client.call("geonames_detail", {"uri": uri})
            if d.ok and isinstance(d.data, dict):
                data = d.data.get("data") if isinstance(d.data.get("data"), dict) else d.data
                desc = str(data.get("description") or "").strip()
        except Exception:  # noqa: BLE001
            desc = ""
        out.append(
            {
                "name": str(it.get("name") or it.get("title") or "").strip(),
                "uri": uri,
                "description": desc,
            }
        )
    return out


def _scene_amap(
    client: SlcClient,
    intent: Intent,
    limit: int,
) -> tuple[list[BuildingEvidence], list[str], list[dict[str, str]]]:
    """场景词通用通道：高德 POI 给真实点位+坐标，SLC 地名志给权威沿革。

    仅在场景词未命中白名单时调用（如外滩/临港/陆家嘴）。高德 POI 保证
    点位真实且带坐标（GCJ-02，与白名单坐标口径一致），地名志沿革
    注入 raw_detail["description"] 供策展引用。

    关键：POI 强过滤（type 白名单 + name 黑名单）—— 否则「临港新城」会拿到
    派出所/通信中心/酒店等行政/商业 POI，根本没有景点；再用场景副搜（"景区/景点"）
    + 剥离地域后缀，命中真实地标（滴水湖/上海天文馆/海昌海洋公园）。
    """
    scene = (intent.scene or "").strip()
    daypart = getattr(intent, "daypart", "day") or "day"
    sources: list[str] = []
    gaps: list[dict[str, str]] = []
    if not scene:
        return [], sources, gaps

    # 0) 先查本地地标库（RAG 分类词条预拉取，带分类号）——命中 >=3 直接用，
    #    不再依赖实时高德检索（实时检索会返回 SOHO/广场等通用商业 POI）。
    db_b, db_s, db_g = _scene_landmark_db(intent, limit)
    if len(db_b) >= 3:
        return db_b, db_s, db_g
    if db_b:
        sources.extend(db_s)
        gaps.extend(db_g)
    # 不足 3 → 继续实时高德兜底（原逻辑）

    amap = AmapClient()

    # 拉够多候选再过滤；type 白名单 + name 黑名单把派出所/酒店/加油站等
    # 行政区划/商业 POI 全部丢掉，只保留真景点类（daypart 时段过滤见 _filter_pois）。
    candidates: list[dict[str, Any]] = []
    seen_names: set[str] = set()

    def _consume(d: list[dict[str, Any]]) -> None:
        for p in d:
            n = str(p.get("name") or "").strip()
            if not n or n in seen_names:
                continue
            seen_names.add(n)
            candidates.append(p)

    _consume(
        _filter_pois(
            amap.place_text(scene, offset=min(25, max(20, limit * 2))), daypart
        )
    )

    # 辅助搜索：场景副词（历史风貌区加「万国建筑/历史建筑/博物馆」命中核心建筑）——
    # 让"外滩"拿到 1-18 号万国建筑，而不是 SOHO/广场等商业 POI。
    if len(candidates) < 3:
        for aux in _aux_keywords(scene):
            _consume(
                _filter_pois(
                    amap.place_text(
                        f"{scene}{aux}", offset=min(25, max(20, limit * 2))
                    ),
                    daypart,
                )
            )
            if len(candidates) >= 3:
                break

    # 末次尝试：剥离地域后缀（如"临港新城"→"临港"），让大区域查询也能拆出
    # 范围内的真景点（"滴水湖/上海天文馆/海昌海洋公园"在"临港"里而不在"临港新城"里）。
    if len(candidates) < 3:
        slim = re.sub(r"(新城|地区|周边|一带|附近|区域)$", "", scene).strip()
        if slim and slim != scene:
            _consume(
                _filter_pois(
                    amap.place_text(slim, offset=min(25, max(20, limit * 2))),
                    daypart,
                )
            )

    # 历史风貌区兜底：直接用词库中所有 landmark 名字作为搜索词（amap 支持
    # 多关键词），保证「外滩」能命中 1-18 号万国建筑等真景点，而不是 SOHO/广场。
    # 多关键词可能被截断/部分命中，逐个补搜每个名字，提高覆盖。
    landmark_facts = _load_landmark_facts()
    if len(candidates) < 6 and any(
        kw in scene for kw in HERITAGE_SCENE_KEYWORDS
    ):
        lm_names = [e["name"] for e in landmark_facts if e.get("name")][:8]
        if lm_names:
            _consume(
                _filter_pois(
                    amap.place_text(
                        ",".join(lm_names),
                        offset=min(25, max(20, limit * 2)),
                    ),
                    daypart,
                )
            )
            # 补搜：逐个 landmark 名字单独搜（每个取前 3 条），保证漏网也回来
            for n in lm_names:
                if any(c.get("name") == n for c in candidates):
                    continue
                _consume(
                    _filter_pois(
                        amap.place_text(n, offset=10), daypart
                    )
                )

    if not candidates:
        gaps.append(
            {"subject": "场景检索", "note": f"高德未检索到「{scene}」景点类 POI"}
        )
        return [], ["高德 POI"], gaps
    sources.append("高德 POI")

    buildings: list[BuildingEvidence] = []
    geo = _scene_geonames_places(client, scene)
    geo_by_name = {g["name"]: g for g in geo if g["name"]}
    if geo:
        sources.append("SLC 地名志")

    for poi in candidates:
        name = str(poi.get("name") or "").strip()
        if not name:
            continue
        g = geo_by_name.get(name)
        lk = _match_landmark(name, landmark_facts)
        raw: dict[str, Any] = {
            "poi_type": poi.get("type") or "",
            "address": poi.get("address"),
            "amap_location": f"{poi['lng']},{poi['lat']}",
        }
        if g and g.get("description"):
            raw["description"] = g["description"]
        # landmark 词库命中：把简介/年代/风格/人物补进 raw_detail + layers
        layers: list[IdentityLayer] = []
        if lk:
            lk_desc = lk.get("description")
            if lk_desc:
                raw["landmark_description"] = lk_desc
            for k in ("year_built", "style", "architect"):
                if lk.get(k):
                    raw[f"landmark_{k}"] = lk[k]
            for ch in lk.get("characters") or []:
                if not ch or not isinstance(ch, str):
                    continue
                layers.append(
                    IdentityLayer(
                        kind="person",
                        label=ch,
                        claim=f"「{name}」相关人物（本地策展词库）",
                        source=SourceRef(
                            dataset="curated.landmark-facts",
                            record_id=lk.get("name") or name,
                            excerpt=lk_desc[:120] if lk_desc else None,
                        ),
                    )
                )
        buildings.append(
            BuildingEvidence(
                buri=g["uri"] if g else None,
                name=name,
                address=poi.get("address"),
                lat=poi.get("lat"),
                lng=poi.get("lng"),
                raw_detail=raw,
                coord_source="amap",
                precision="approximate",
                layers=layers,
            )
        )
        if len(buildings) >= limit:
            break
    if not buildings:
        gaps.append({"subject": "场景检索", "note": f"「{scene}」无可用点位"})
    return buildings, sources, gaps


# ---- 高德 POI 过滤（黑名单式）：只丢「无 citywalk 价值」的，保留有氛围/审美的 ----
# 保留：风景名胜/博物馆/天文馆/公园广场/历史古迹/宗教设施；
#       五星级酒店（type 含「五星级宾馆」或豪华品牌名）、部分获奖四星；
#       商场/购物中心、咖啡/奶茶/酒吧/网红餐厅（citywalk 休息与氛围节点）；
#       名校（高等院校名单内）。
# 过滤：派出所/政务/通信/邮政/加油站/停车场/汽修/银行/医院/药店/快递/物流/
#       驾校/殡葬/普通写字楼/普通学校（非名校）/经济连锁酒店（如家汉庭亚朵普通店）。

_FAMOUS_UNIVERSITIES = (
    "上海交通大学", "复旦大学", "同济大学", "华东师范大学", "上海财经大学",
    "华东理工大学", "东华大学", "上海外国语大学", "上海大学", "上海科技大学",
    "上海纽约大学", "上海音乐学院", "上海戏剧学院", "华东政法大学",
    "上海中医药大学", "上海对外经贸大学", "上海海事大学", "上海理工大学",
    "上海师范大学", "上海体育大学",
)
_LUXURY_HOTEL_BRANDS = (
    "和平饭店", "半岛酒店", "华尔道夫", "瑞吉酒店", "柏悦", "君悦", "丽思卡尔顿",
    "宝格丽", "悦榕庄", "安缦", "瑰丽", "文华东方", "四季酒店", "洲际酒店",
    "万豪", "威斯汀", "香格里拉", "凯悦", "W酒店", "璞丽", "外滩茂悦",
    "波特曼丽思", "宝丽嘉", "苏宁宝丽嘉", "养云安缦",
)
_DROP_NAME_KEYWORDS = (
    "派出所", "公安", "政务", "政府", "党群", "市民中心", "办事",
    "通信中心", "通讯", "邮政", "营业厅",
    "加油站", "充电站", "停车场", "汽修", "修理", "洗车", "4S店",
    "银行", "证券", "保险", "ATM", "公积金", "社保",
    "医院", "诊所", "药店", "体检",
    "快递", "物流", "货运", "仓库",
    "驾校", "殡仪", "墓园", "灵堂",
    "写字楼", "办公楼", "产业园", "工业园", "科技园", "商务楼",
    "幼儿园", "小学", "中学", "职校", "中专", "技师学院", "附中", "附小",
    "如家", "汉庭", "7天", "七天", "锦江之星", "格林豪泰", "速8", "速八",
    "城市便捷", "维也纳", "宜必思", "全季", "桔子", "轻居", "智选假日",
    "加油站便利店",
    # 普通快餐/小吃（非网红特征），citywalk 休息节点应是咖啡/奶茶/酒吧/有辨识度餐饮
    "馄饨", "米线", "面馆", "麻辣烫", "快餐", "食堂", "盖浇饭", "黄焖鸡",
    "沙县", "兰州拉面", "烧烤", "炸鸡", "汉堡", "炸串", "煎饼",
)
_DROP_TYPE_PREFIXES = (
    "政府机构", "公司企业", "金融保险服务", "医疗服务", "物流仓储服务",
    "交通设施服务;停车场", "交通设施服务;加油站", "商务住宅;楼宇",
    "地名地址信息;交通地名;道路名", "地名地址信息;交通地名;路口名",
    "地名地址信息;门牌信息", "地名地址信息;地名地址信息",
)
_KEEP_TYPE_PREFIXES = (
    "风景名胜", "科教文化服务", "公园广场", "旅游景点", "博物馆",
    "历史古迹", "宗教", "教堂", "餐饮服务", "购物服务", "休闲娱乐服务",
    "住宿服务;宾馆酒店;五星级宾馆", "住宿服务;度假村",
)


# 夜间：21 点前关门的（博物馆/纪念馆/故居/遗址类）排除，保留夜景地标与夜生活
_NIGHT_CLOSE_EARLY_KEYWORDS = (
    "纪念馆", "故居", "遗址", "博物馆", "美术馆", "科技馆", "天文馆",
    "规划馆", "展示馆", "陈列馆", "艺术馆", "图书馆", "档案馆",
)
_NIGHT_KEEP_KEYWORDS = (
    "外滩", "滨江", "江畔", "码头", "塔", "桥", "广场", "夜市", "灯光",
    "酒吧", "清吧", "Livehouse", "livehouse", "夜",
)


def _filter_pois(
    pois: list[dict[str, Any]], daypart: str = "day"
) -> list[dict[str, Any]]:
    """黑名单式过滤：只丢无 citywalk 价值的；保留景点/文教/五星酒店/商场/
    咖啡餐饮酒吧/名校等有氛围或休息价值的 POI。

    daypart 额外维度：
      night  排除 21 点前关门的（博物馆/纪念馆/故居/遗址…），只留夜景地标
             （外滩/滨江/塔/桥/广场/夜市）+ 夜生活（酒吧/KTV/深夜餐饮/影院）；
      suburb 偏向自然景点（公园/湖泊/湿地/山/森林/农庄/田园…），排除市中心商业；
      day/full 走常规逻辑。
    """
    out: list[dict[str, Any]] = []
    for p in pois:
        if not isinstance(p, dict):
            continue
        t = str(p.get("type") or "").strip()
        name = str(p.get("name") or "").strip()
        if not name:
            continue
        # 1) 名字命中硬黑名单（派出所/政务/加油站/经济酒店/普通学校…）→ 丢
        if any(kw in name for kw in _DROP_NAME_KEYWORDS):
            continue
        # 2) type 命中硬黑名单前缀 → 丢
        if t and any(t.startswith(prefix) for prefix in _DROP_TYPE_PREFIXES):
            continue
        # 3) 名校（高等院校且名单内）→ 保
        if "高等院校" in t and any(u in name for u in _FAMOUS_UNIVERSITIES):
            out.append(p)
            continue
        # 3.5) 非名校学校/大学城/附中附小 → 丢（不能落进"科教文化服务"白名单）
        if any(k in t for k in ("学校", "高等院校", "中学", "小学", "大学")) or any(
            k in name for k in ("大学城", "校区", "学院", "附中", "附小")
        ):
            continue
        # 4) 五星级宾馆 / 豪华品牌 → 保（不受经济连锁黑名单影响——第1步已处理连锁）
        if "五星级宾馆" in t or any(b in name for b in _LUXURY_HOTEL_BRANDS):
            out.append(p)
            continue
        # 5) 常规酒店（非五星非豪华）→ 丢（避免普通酒店刷屏，citywalk 不必要）
        if "住宿服务" in t:
            continue
        # 5.5) 时段分支
        if daypart == "night":
            if _night_keep(p, t, name):
                out.append(p)
            continue
        if daypart == "suburb":
            if _suburb_keep(t, name):
                out.append(p)
            continue
        # 6) 其余按 type 白名单前缀保留（风景/文教/餐饮/购物/休闲…）
        if t and any(t.startswith(prefix) for prefix in _KEEP_TYPE_PREFIXES):
            out.append(p)
            continue
        # 7) type 为空：只保留名字含地标词（湖/馆/山/寺/塔/古镇/老街/园/故居/遗址…）
        if not t and any(
            kw in name
            for kw in ("湖", "馆", "山", "寺", "塔", "古镇", "老街", "故居",
                       "遗址", "公园", "广场", "码头", "城堡", "庄园")
        ):
            out.append(p)
            continue
    return out


def _night_keep(
    p: dict[str, Any], t: str, name: str
) -> bool:
    """夜晚模式：保留 21 点后仍在营业/可看的场所。"""
    # 夜生活/夜间餐饮/影院/休闲娱乐：酒吧/KTV/夜店/影院/深夜餐饮
    if t.startswith(("休闲娱乐服务", "餐饮服务", "购物服务", "住宿服务")):
        return True
    # 景点类：只有夜景特征（外滩/滨江/塔/桥/广场/夜市/灯光/码头）才保留，
    # 否则 21 点前关门的博物馆/纪念馆/故居/遗址排除
    if t.startswith(("风景名胜", "公园广场", "旅游景点", "历史古迹", "科教文化服务")):
        if any(k in name for k in _NIGHT_KEEP_KEYWORDS):
            return True
        if any(k in name for k in _NIGHT_CLOSE_EARLY_KEYWORDS):
            return False
        return True  # 无明确关门特征的景点按开放处理（如外滩公共空间）
    return False


def _suburb_keep(t: str, name: str) -> bool:
    """郊区模式：只保留自然景点（公园/湖泊/湿地/山/森林/农庄/田园…）。"""
    if any(
        k in t
        for k in ("湖泊", "湿地", "山岳", "森林", "自然保护区", "植物园", "动物园")
    ):
        return True
    if any(
        k in name
        for k in ("公园", "湖", "湿地", "山", "森林", "农庄", "田园", "郊野",
                  "花海", "植物园", "动物园", "野生动物园", "果园", "营地")
    ):
        return True
    return False


def _scene_rag_corpus(
    intent: Intent, limit: int
) -> tuple[list[BuildingEvidence], list[str], list[dict[str, str]]]:
    """Keyless RAG 数据筛选兜底：无 SLC/amap key 或白名单未命中时，用本地全量
    POI 语料（amap <city>-landmarks + 免 key 的 OSM <city>-osm）按 intent
    预筛候选，保证路线非空（避免空壳 / 电子垃圾）。纯本地、无网络、无 LLM。"""
    city = getattr(intent, "city", None) or "shanghai"
    try:
        buildings = _rag_retrieve(intent, top_k=limit)
    except Exception:  # noqa: BLE001
        return [], [], [{"subject": "RAG 语料", "note": "检索失败"}]
    if not buildings:
        return [], [], [{"subject": "RAG 语料", "note": f"{city}-landmarks/osm 语料为空"}]
    return buildings, ["RAG 全量 POI 筛选"], []


def _attach_partner_layers(
    buildings: list[BuildingEvidence],
    partner_layers: list[dict[str, Any]],
) -> None:
    """把 partner 归一化 layer（裸结构）按名近似挂到已命中建筑。

    匹配规则：layer.label（人名/地名）与建筑名互相包含（≥2 字）即视为同一主体，
    避免跨库 join 错位。未匹配到的 layer 暂不丢弃——挂到同名度最高的建筑若都无则跳过
    （partner 数据稀疏时不强行污染无关建筑）。
    """
    for bl in buildings:
        name = (bl.name or "").strip()
        if len(name) < 2:
            continue
        for layer in partner_layers:
            label = (layer.get("label") or "").strip()
            if len(label) < 2:
                continue
            if label in name or name in label:
                src = layer.get("source") or {}
                bl.layers.append(
                    IdentityLayer(
                        kind=str(layer.get("kind") or "person"),
                        label=label,
                        claim=str(layer.get("claim") or ""),
                        source=SourceRef(
                            dataset=str(src.get("dataset") or "partner"),
                            record_id=str(src.get("record_id") or label),
                        ),
                    )
                )


def fetch_evidence(client: SlcClient, intent: Intent, *, limit: int = 10) -> EvidencePack:
    sources_used: list[str] = ["R-20 whitelist"]
    gaps: list[dict[str, str]] = []
    buildings: list[BuildingEvidence] = []
    wl = load_whitelist()

    if wl.count == 0:
        gaps.append({"subject": "R-20 whitelist", "note": "暂无数据支撑"})
    else:
        # 0) 场景词未命中白名单（如外滩/临港/陆家嘴）→ 通用通道：
        #    高德 POI 给真实点位+坐标，SLC 地名志给权威沿革。避免「搜外滩给巴金故居」。
        #    通用通道命中 >=3 即视为场景已覆盖，跳过白名单抓取（防串味）。
        _, matched = _scene_whitelist(intent, wl)
        if not matched:
            gb, gs, gg = _scene_amap(client, intent, limit)
            buildings.extend(gb)
            sources_used.extend(gs)
            gaps.extend(gg)

        # 1) Prefer whitelist buris (R-20 ∩ SLC), fetched concurrently (方案C)
        #    仅在场景已命中白名单、或通用通道不足 3 站时执行（白名单作兜底）。
        if matched or len(buildings) < 3:
            preferred = [p for p in _scene_whitelist(intent, wl)[0] if p.buri]
            seen: set[str] = set()
            batch: list[tuple[str, str]] = []
            for wp in preferred:
                if not wp.buri:  # 控制流判断，避免 -O 模式下 assert 被剥离导致 AttributeError
                    continue
                if wp.buri in seen:
                    continue
                seen.add(wp.buri)
                batch.append((wp.buri, wp.name))
            b1, s1, g1 = _fetch_batch(client, batch, wl, limit)
            buildings.extend(b1)
            sources_used.extend(s1)
            gaps.extend(g1)

            # 2) If still thin, intersect building_list with remaining whitelist buris
            if len(buildings) < 3:
                listing = client.building_list("")
                sources_used.append("building_list")
                if listing.ok and listing.data is not None:
                    items = _as_list(listing.data)
                    batch2: list[tuple[str, str]] = []
                    for item in items:
                        uri = _uri_of(item)
                        if not uri or uri in seen:
                            continue
                        if uri not in wl.by_buri:
                            continue
                        seen.add(uri)
                        batch2.append((uri, _name_of(item)))
                    b2, s2, g2 = _fetch_batch(client, batch2, wl, limit)
                    buildings.extend(b2)
                    sources_used.extend(s2)
                    gaps.extend(g2)
                else:
                    gaps.append({"subject": "building_list", "note": "暂无数据支撑"})

        # Keyless RAG 兜底：候选不足时（无 key / 白名单未命中 / SLC 取数失败）
        # 用本地全量 POI 语料（amap + OSM）按 intent 预筛，保证路线非空。
        if len(buildings) < limit:
            rb, rs, rg = _scene_rag_corpus(intent, limit - len(buildings))
            if rb:
                buildings.extend(rb)
                sources_used.extend(rs)
                gaps.extend(rg)

        # 多数据源接入（方案 §3）：按城市收集已落盘 partner 的归一化 layer；
        # 未落盘/待定源进 gaps（诚实标注），不编造。layer 按名近似挂到已命中建筑。
        try:
            _pl, _ps, _pg = gather_partner_evidence(
                getattr(intent, "city", None) or "shanghai"
            )
            if _pl:
                _attach_partner_layers(buildings, _pl)
                sources_used.extend(_ps)
            gaps.extend(_pg)
        except Exception:  # noqa: BLE001
            gaps.append(
                {"subject": "partner 数据源", "note": "接入异常（已跳过，不影响主链路）"}
            )

    # 典籍源（CBDB 中国历代人物传记）：对每栋建筑已挂的 person 图层，
    # 按「同名同城市」查典籍传记，附加 classical 图层。零 token、纯本地查表。
    try:
        _city = getattr(intent, "city", None) or "shanghai"
        for _be in buildings:
            attach_classical_layers(_be, city=_city)
        if any(any(l.kind == "classical" for l in b.layers) for b in buildings):
            sources_used.append("cbdb_classical")
    except Exception:  # noqa: BLE001
        gaps.append({"subject": "cbdb_classical", "note": "典籍层挂载异常（已跳过）"})

    if len(buildings) < 3:
        gaps.append({"subject": "候选建筑不足", "note": "暂无数据支撑"})

    sources_used = list(dict.fromkeys(sources_used))
    return EvidencePack(
        buildings=buildings,
        gaps=gaps,
        fetched_at=datetime.now(timezone.utc).isoformat(),
        mode="indexed",
        sources_used=sources_used,
    )
