"""典籍数据源：把 CBDB 中国历代人物传记接进 evidence 流。

设计原则（与《书籍化架构》红线一致）：
- 事实只能源于取证证据：只从已落地的 cbdb.json 取数据，绝不臆造。
- 零 token：纯本地查表，不调 LLM。
- 证据可溯源：每个 classical 图层带 record_id（cbdb:<personid>），可回查典籍出处。

接入点：在 evidence._attach_corpus_layers 之后调用 attach_classical_layers(be, city)。
匹配逻辑：对建筑已有的 person 图层人名，在 CBDB 里按「同名同城市」查典籍传记。
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from .models import BuildingEvidence, IdentityLayer, SourceRef

logger = logging.getLogger(__name__)

# content/partner/cbdb.json 由 extract_cbdb.py 生成（35496 位典籍人物）
# 路径相对项目根（packages/curator/redtrip_curator/classics.py → 向上三级到项目根）
_PARTNER_DIR = (
    Path(__file__).resolve().parents[3] / "content" / "partner"
)
_CBDB_PATH = _PARTNER_DIR / "cbdb.json"

# 模块级缓存：避免每次策展都重新读 7MB JSON
_CBDB_BY_CITY: dict[str, dict[str, dict[str, Any]]] | None = None
_CBDB_ALL_NAMES: dict[str, dict[str, Any]] | None = None  # 全名索引（跨城）


def _load_cbdb() -> tuple[dict[str, dict[str, dict[str, Any]]], dict[str, dict[str, Any]]]:
    """加载 CBDB 并建城市→{人名→人物记录}索引 + 全名索引。懒加载、模块级缓存。"""
    global _CBDB_BY_CITY, _CBDB_ALL_NAMES
    if _CBDB_BY_CITY is not None and _CBDB_ALL_NAMES is not None:
        return _CBDB_BY_CITY, _CBDB_ALL_NAMES

    if not _CBDB_PATH.exists():
        logger.warning("CBDB index not found at %s — classical layers disabled", _CBDB_PATH)
        _CBDB_BY_CITY, _CBDB_ALL_NAMES = {}, {}
        return _CBDB_BY_CITY, _CBDB_ALL_NAMES

    try:
        data = json.loads(_CBDB_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("CBDB load failed (%s) — classical layers disabled", e)
        _CBDB_BY_CITY, _CBDB_ALL_NAMES = {}, {}
        return _CBDB_BY_CITY, _CBDB_ALL_NAMES

    by_city: dict[str, dict[str, dict[str, Any]]] = {}
    all_names: dict[str, dict[str, Any]] = {}
    persons = data.get("persons", []) if isinstance(data, dict) else []
    for p in persons:
        if not isinstance(p, dict):
            continue
        name = p.get("name")
        if not name:
            continue
        city = p.get("city", "")
        # 优先保留信息更全的记录（有生卒年或官职的）
        prev = by_city.get(city, {}).get(name)
        if prev is None or _richness(p) > _richness(prev):
            by_city.setdefault(city, {})[name] = p
        prev_all = all_names.get(name)
        if prev_all is None or _richness(p) > _richness(prev_all):
            all_names[name] = p

    _CBDB_BY_CITY = by_city
    _CBDB_ALL_NAMES = all_names
    logger.info(
        "CBDB loaded: %d cities, %d unique names", len(by_city), len(all_names)
    )
    return _CBDB_BY_CITY, _CBDB_ALL_NAMES


def _richness(p: dict[str, Any]) -> int:
    """记录信息丰富度评分：有生卒>有官职>有朝代>基础。用于同名去重留最全的。"""
    score = 0
    if p.get("birth_year") or p.get("death_year"):
        score += 3
    if p.get("offices"):
        score += 2
    if p.get("dynasty"):
        score += 1
    if p.get("entry"):
        score += 1
    return score


def _normalize_name(name: str) -> str:
    """规范化人名用于匹配：去空格/标点，繁→简（轻量）。"""
    import re
    n = re.sub(r"[\s\u3000《》「」『』（）()·]", "", name)
    # 轻量繁简转换（只覆盖人名常见字）
    _F2S = {
        "蘇": "苏", "吳": "吴", "張": "张", "劉": "刘", "陳": "陈", "趙": "赵",
        "錢": "钱", "孫": "孙", "楊": "杨", "黃": "黄", "鄭": "郑", "謝": "谢",
        "葉": "叶", "萬": "万", "範": "范", "華": "华", "趙": "赵", "龔": "龚",
        "應": "应", "蔣": "蒋", "蔡": "蔡", "餘": "余", "鍾": "钟", "徐": "徐",
        "鄒": "邹", "蘇": "苏", "婁": "娄", "譚": "谭", "閔": "闵", "顧": "顾",
        "費": "费", "賀": "贺", "潘": "潘", "戴": "戴", "魏": "魏", "薛": "薛",
        "葉": "叶", "閻": "阎", "餘": "余", "餘": "余", "龐": "庞", "董": "董",
        "賈": "贾", "鄒": "邹", "婁": "娄", "諸": "诸", "葛": "葛", "章": "章",
        "魯": "鲁", "許": "许", "蔣": "蒋", "鮑": "鲍", "鄧": "邓", "洪": "洪",
        "顏": "颜", "倪": "倪", "婁": "娄", "盧": "卢", "姚": "姚", "石": "石",
        "麥": "麦", "龐": "庞", "鍾": "钟", "汪": "汪", "毛": "毛", "余": "余",
        "丁": "丁", "秦": "秦", "蔣": "蒋", "江": "江", "史": "史", "羅": "罗",
        "范": "范", "桂": "桂", "簡": "简", "邢": "邢", "裴": "裴", "童": "童",
        "湛": "湛", "於": "于", "施": "施", "洪": "洪", "姜": "姜", "滕": "滕",
        "殷": "殷", "溫": "温", "祁": "祁", "翁": "翁", "卓": "卓", "嚴": "严",
        "祝": "祝", "焦": "焦", "屈": "屈", "阮": "阮", "藍": "蓝", "管": "管",
        "盧": "卢", "岳": "岳", "駱": "骆", "歐": "欧", "向": "向", "梅": "梅",
        "盛": "盛", "鄺": "邝", "樊": "樊", "胡": "胡", "凌": "凌", "浦": "浦",
    }
    return "".join(_F2S.get(c, c) for c in n)


def _was_attached(be: BuildingEvidence, kind: str, label_prefix: str = "") -> bool:
    """检查是否已挂同类型 classical 图层（按 label 前缀去重，避免同人多次挂）。"""
    for l in be.layers:
        if l.kind == kind and (not label_prefix or l.label.startswith(label_prefix)):
            return True
    return False


def attach_classical_layers(be: BuildingEvidence, city: str | None = None) -> None:
    """对建筑已有的 person 图层人名，在 CBDB 查典籍传记，附加 classical 图层。

    匹配策略（按优先级）：
    1. 同名 + 同城市（最精确）
    2. 同名（跨城市兜底，标记「异籍同名」）

    每个 classical 图层承载：朝代·生卒·官职·入仕·籍贯出处，
    source.dataset="cbdb_classical", record_id=人物 id（可回查哈佛 CBDB 原库）。
    """
    by_city, all_names = _load_cbdb()
    if not by_city and not all_names:
        return

    persons = [l.label for l in be.layers if l.kind == "person"]
    if not persons:
        return

    for person_name in persons:
        norm = _normalize_name(person_name)
        if not norm:
            continue

        # 去重：同一建筑的同一人物只挂一次
        label_prefix = f"典籍 · {person_name}"
        if _was_attached(be, "classical", label_prefix):
            continue

        # 优先同名同城市
        match = None
        city_pool = by_city.get(city or "", {})
        for cname, rec in city_pool.items():
            if _normalize_name(cname) == norm:
                match = rec
                break
        # 兜底：同名跨城市
        if match is None:
            for cname, rec in all_names.items():
                if _normalize_name(cname) == norm:
                    match = rec
                    break

        if match is None:
            continue

        claim = _build_classical_claim(match)
        if not claim:
            continue

        be.layers.append(
            IdentityLayer(
                kind="classical",
                label=label_prefix,
                claim=claim,
                source=SourceRef(
                    dataset="cbdb_classical",
                    record_id=match.get("id", ""),
                    excerpt=_build_excerpt(match),
                ),
            )
        )


def _build_classical_claim(p: dict[str, Any]) -> str:
    """把典籍人物记录组装成一段可溯源的 claim。"""
    parts = []
    dynasty = p.get("dynasty")
    if dynasty and dynasty != "未詳":
        parts.append(f"{dynasty}")
    by = p.get("birth_year")
    dy = p.get("death_year")
    if by and dy and by > 0 and dy > 0:
        parts.append(f"{by}–{dy}年")
    elif by and by > 0:
        parts.append(f"生于{by}年")
    jg = p.get("jiguang")
    if jg:
        parts.append(f"籍{p.get('jiguang')}")
    entry = p.get("entry")
    if entry:
        parts.append(f"入仕：{entry}")
    offices = p.get("offices") or []
    if offices:
        parts.append("历" + "、".join(offices[:3]))
    if not parts:
        return ""
    # 头部标注典籍出处
    head = f"据《CBDB 中国历代人物传记》载："
    return head + "，".join(parts) + "。"


def _build_excerpt(p: dict[str, Any]) -> str | None:
    """给 Gate G4 留的简短出处摘要。"""
    jg = p.get("jiguang") or ""
    off = "、".join((p.get("offices") or [])[:2])
    dyn = p.get("dynasty") or ""
    bits = [b for b in [dyn, f"籍{jg}" if jg else "", off] if b]
    return ("；".join(bits) + "；") if bits else None


def classical_stats() -> dict[str, Any]:
    """供 /v1/health 报告 classics 源状态。"""
    by_city, all_names = _load_cbdb()
    return {
        "loaded": bool(by_city or all_names),
        "cities": len(by_city),
        "unique_names": len(all_names),
        "source": "CBDB 中国历代人物传记 (cbdb-project, 20260822)",
    }
