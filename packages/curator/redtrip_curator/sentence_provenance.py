"""句子级 G4 的共享数据结构与小工具。

句子级溯源（事实句 ↔ fact_uri）的计算逻辑已合并进 ``polish._build_sp_report_from_polish``
（与润色同一次 LLM 调用，避免独立的「溯源大调用」）。本模块只保留：
- ``SentenceProvenanceReport`` 等数据结构（被 artifacts / pipeline / polish 引用）；
- ``_split_sentences`` / ``_fact_catalog`` / ``_heuristic_align`` 等被 polish 复用的纯函数。

事实目录只取自 RoutePlan 中已取证的 IdentityLayer（其 source.record_id 即 fact_uri），
LLM 只能在目录内选择，严禁编造——与「事实只能源于取证证据」的硬约束一致。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .models import RoutePlan

# 占位符：缺失真实标识的 record_id（既不是 None/空，也不是合法 URI）。
_PLACEHOLDER_IDS = {"", "?", None}

# ── 证据置信度分级（A–E，吸收「策展委员会」评审 prompt 的事实核查框架）──
# A：一手档案 / 可验证现场物（SLC 馆藏、地名志、建筑详情，且带真实 record_id）
# B：可靠策展词库 / 权威机构资料（curated.landmark-facts、外部 source）
# C：可靠二手但非一手（高德通用 POI、未带 record_id 的权威库条目）
# D：地方传闻 / 未核实网页 / 记忆性材料（当前管线不 ingest，预留）
# E：推测，不可当作事实讲述（当前管线不 ingest，预留）
#
# 设计原则（防降智）：分级是「告知模型如何措辞」而非「禁止」。A/B 可作事实陈述；
# C 须带轻度归属（「据地图标注」「高德分类为」）；D/E 须用 待核查/地方传闻/研究假设
# 标签且仅作开放问题，绝不作确定陈述。Gate 对 C 级平铺事实仅告警不拦截。
def _grade_for(dataset: str, has_rid: bool) -> str:
    d = dataset or ""
    if d in ("geonames_corpus", "building_detail", "road_corpus", "literary_corpus",
             "geonames") or d.startswith("slc_") or d.startswith("geonames:"):
        return "A" if has_rid else "C"
    if d == "curated.landmark-facts" or d.startswith("curated."):
        return "B" if has_rid else "C"
    if d in ("amap", "amap_poi") or d.startswith("amap:"):
        return "C"  # 通用 POI，可靠但非一手档案
    if d in ("geoname", "literary", "source"):
        return "B" if has_rid else "C"
    return "C"


def _grade_label(grade: str) -> str:
    return {
        "A": "一手档案/可验证现场物",
        "B": "可靠策展词库/权威资料",
        "C": "可靠二手（通用POI/未带出处ID）",
        "D": "地方传闻/未核实材料",
        "E": "推测（不可作事实）",
    }.get(grade, "未分级")


@dataclass
class SentenceClaim:
    index: int
    text: str
    kind: str  # factual | connective
    fact_uris: list[str] = field(default_factory=list)
    fact_labels: list[str] = field(default_factory=list)
    aligned: bool = False
    grades: list[str] = field(default_factory=list)  # 对应 fact_uris 的置信度 A–E

    def as_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "text": self.text,
            "kind": self.kind,
            "fact_uris": self.fact_uris,
            "fact_labels": self.fact_labels,
            "aligned": self.aligned,
            "grades": self.grades,
        }


@dataclass
class StopSentenceProvenance:
    stop_index: int
    source_block: str  # story_card | route_card
    sentences: list[SentenceClaim] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "stop_index": self.stop_index,
            "source_block": self.source_block,
            "sentences": [s.as_dict() for s in self.sentences],
        }


@dataclass
class SentenceProvenanceReport:
    total_sentences: int = 0
    factual_sentences: int = 0
    aligned_factual: int = 0
    coverage_ratio: float = 0.0
    per_stop: list[StopSentenceProvenance] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "total_sentences": self.total_sentences,
            "factual_sentences": self.factual_sentences,
            "aligned_factual": self.aligned_factual,
            "coverage_ratio": self.coverage_ratio,
            "per_stop": [s.as_dict() for s in self.per_stop],
        }


def _split_sentences(text: str) -> list[str]:
    """中文友好分句：以 。！？；或换行 切，保留标点的完整句。"""
    if not text:
        return []
    parts = re.split(r"(?<=[。！？；\n])", text)
    return [p.strip() for p in parts if p and p.strip()]


def _facts_of(plan: RoutePlan) -> list[dict[str, Any]]:
    """事实目录：每个已取证的 IdentityLayer → 一条可溯源事实（跳过占位 record_id）。"""
    cat: list[dict[str, Any]] = []
    for s in plan.stops:
        be = s.evidence
        for l in be.layers:
            rid = (l.source.record_id or "").strip()
            if rid in _PLACEHOLDER_IDS:
                continue
            cat.append(
                {
                    "fact_uri": rid,
                    "stop_index": s.order,
                    "label": l.label,
                    "layer": l.kind,
                    "claim": (l.claim or "")[:120],
                    "dataset": l.source.dataset,
                    "grade": _grade_for(l.source.dataset, rid not in _PLACEHOLDER_IDS),
                }
            )
    return cat


# 兼容别名：polish 中沿用 ``_fact_catalog`` 名称。
def _fact_catalog(plan: RoutePlan) -> list[dict[str, Any]]:
    return _facts_of(plan)


def _heuristic_align(
    sentences: list[str], cat: list[dict[str, Any]], stop_index: int
) -> list[SentenceClaim]:
    """回退：句子若命中该站点事实的人名/年份 token 则视为 factual 并归入该事实。"""
    stop_facts = [f for f in cat if f.get("stop_index") == stop_index]
    claims: list[SentenceClaim] = []
    for i, sent in enumerate(sentences):
        hits: list[str] = []
        labels: list[str] = []
        grades: list[str] = []
        for f in stop_facts:
            toks = set(re.findall(r"[\u4e00-\u9fff]{2,4}", f.get("label", "")))
            years = set(re.findall(r"\d{3,4}", f.get("claim", "")))
            if any(t in sent for t in toks) or any(y in sent for y in years):
                hits.append(f["fact_uri"])
                labels.append(f["label"])
                grades.append(f.get("grade", ""))
        kind = "factual" if hits else "connective"
        claims.append(
            SentenceClaim(
                index=i,
                text=sent,
                kind=kind,
                fact_uris=hits,
                fact_labels=labels,
                aligned=bool(hits),
                grades=grades,
            )
        )
    return claims
