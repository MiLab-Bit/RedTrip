"""G2 / G4 稳定契约：把内容推理的中间产物做成一等公民。

本模块定义 RedTrip 升级后的「内容推理层」四个一等公民中间产物
（Theme / EvidenceGraph / NarrativeArc / ProvenanceReport），以及把它们
从 *同一份取证证据* 派生出来的纯函数 ``build_artifacts``。

设计要点（与现有代码零冲突）：
- ``narrate()`` 的输出（RouteEnvelope dict）保持不变，向后兼容。
- 本模块只「读」``Intent / RoutePlan / EvidencePack``，产出独立的 artifact 字典。
- ``CurationArtifacts.embed(envelope)`` 把产物注入 envelope，使现有
  ``evaluate_envelope`` 闸门能直接校验 G4（细粒度溯源）与 Interest 维度，
  无需新增接口。

字段命名沿用全仓 snake_case（与 TS 契约、Python dict 输出一致）。
"""
from __future__ import annotations

import dataclasses
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

from .models import BuildingEvidence, EvidencePack, IdentityLayer, Intent, RoutePlan
from .proposition import PropositionSet, decompose_intent
from .sentence_provenance import SentenceProvenanceReport
from .storycraft import craft_route_voice

LayerKind = Literal["building", "event", "era", "poem", "person"]
NarrativeRole = Literal["Hook", "Anchor", "Contrast", "Reveal", "Afterimage", "Bridge"]

ARTIFACTS_VERSION = "1.0"


def _d(obj: Any) -> Any:
    """递归转 dict（dataclass → dict）。"""
    return dataclasses.asdict(obj)


# --------------------------------------------------------------------------
# G2-1 Theme（研究命题 / 开放问题入口）
# --------------------------------------------------------------------------
@dataclass
class ResearchAxis:
    """研究轴：命题的单一维度与可证伪假设。"""

    axis: str
    hypothesis: str
    evidence_cluster_ids: list[str] = field(default_factory=list)


@dataclass
class Theme:
    """策展主题：全书级命题容器，是 render_web / render_book 共享的契约入口。"""

    id: str
    title: str
    open_question: str
    research_axes: list[ResearchAxis] = field(default_factory=list)
    why_visit: str = ""
    estimated_duration_min: int = 0
    scope_note: str = ""

    def as_dict(self) -> dict[str, Any]:
        return _d(self)


# --------------------------------------------------------------------------
# G2-2 EvidenceGraph（证据图：聚类 + buri 跨库 join）
# --------------------------------------------------------------------------
@dataclass
class EvidenceFact:
    fact_uri: str
    label: str
    assertion: str
    layer: LayerKind
    source_dataset: str
    confidence: float = 1.0


@dataclass
class EvidenceCluster:
    id: str
    dimension: str  # person / building / event / era / theme
    label: str
    facts: list[EvidenceFact] = field(default_factory=list)


@dataclass
class EvidenceJoin:
    from_uri: str
    to_uri: str
    relation: str


@dataclass
class EvidenceGraph:
    """G2-2 证据图：按维度聚类的事实与跨库 join，书籍化 colophon 的直接来源。"""

    theme_id: str
    clusters: list[EvidenceCluster] = field(default_factory=list)
    joins: list[EvidenceJoin] = field(default_factory=list)
    coverage: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return _d(self)


# --------------------------------------------------------------------------
# G2-3 NarrativeArc（叙事弧：节点叙事角色 + 张力曲线）
# --------------------------------------------------------------------------
@dataclass
class NarrativeNode:
    stop_index: int
    role: NarrativeRole
    beat: str
    facts_referenced: list[str] = field(default_factory=list)


@dataclass
class NarrativeArc:
    theme_id: str
    nodes: list[NarrativeNode] = field(default_factory=list)
    tension_curve: list[float] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return _d(self)


# --------------------------------------------------------------------------
# 故事优先：内容结构（前端 StoryReader / NarrativeArc 直接消费的 CuratedStory）
# --------------------------------------------------------------------------
@dataclass
class StoryEntity:
    id: str
    kind: str  # person | building | event
    name: str
    fact_uri: str | None = None
    note: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return _d(self)


@dataclass
class StoryChapter:
    """故事优先的章节结构：前端 StoryReader / NarrativeArc / 书籍渲染器共享的契约。

    字段在 as_dict() 中转为 camelCase，与 TypeScript CuratedStory 契约对齐。
    """

    id: str
    index: int
    title: str
    hook: str
    narrative_role: NarrativeRole
    stop_id: int
    relation_to_previous: str | None = None
    evidence_ids: list[str] = field(default_factory=list)
    walking_minutes: int = 0
    cast_refs: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        # 故事优先结构被 TS 契约 StoryChapterSchema 与前端（WalkStage /
        # StoryIntro / NarrativeMap）直接消费，字段名须为 camelCase；与 G2/G4
        # 的 snake_case 中间产物（theme / evidence_graph / narrative_arc …）
        # 区分开。内部 dataclass 仍用 snake_case，仅在此序列化层转换。
        return {
            "id": self.id,
            "index": self.index,
            "title": self.title,
            "hook": self.hook,
            "narrativeRole": self.narrative_role,
            "stopId": self.stop_id,
            "relationToPrevious": self.relation_to_previous,
            "evidenceIds": self.evidence_ids,
            "walkingMinutes": self.walking_minutes,
            "castRefs": self.cast_refs,
        }


# --------------------------------------------------------------------------
# G4 ProvenanceReport（细粒度溯源：断言 ↔ 事实）
# --------------------------------------------------------------------------
@dataclass
class AssertionClaim:
    text: str
    fact_uri: str | None
    aligned: bool
    layer: LayerKind | None


@dataclass
class StopProvenance:
    stop_index: int
    assertions: list[AssertionClaim] = field(default_factory=list)


@dataclass
class ProvenanceReport:
    """G4 细粒度溯源：每条断言 ↔ fact_uri 的对齐报告，书籍化 colophon 的校验依据。"""

    total_assertions: int = 0
    aligned_assertions: int = 0
    coverage_ratio: float = 1.0
    per_stop: list[StopProvenance] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return _d(self)


# --------------------------------------------------------------------------
# Bundle
# --------------------------------------------------------------------------
@dataclass
class CurationArtifacts:
    """内容推理层产物容器：渲染器（web / book / 未来形态）唯一依赖的稳定契约。

    版本：1.0。任何渲染器只应读取本容器输出，不应反向依赖内容管线内部实现。
    """

    theme: Theme
    evidence_graph: EvidenceGraph
    narrative_arc: NarrativeArc
    provenance: ProvenanceReport
    sentence_provenance: SentenceProvenanceReport | None = None
    thesis: str = ""
    cast: list[StoryEntity] = field(default_factory=list)
    chapters: list[StoryChapter] = field(default_factory=list)
    artifacts_version: str = ARTIFACTS_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifacts_version": self.artifacts_version,
            "theme": self.theme.as_dict(),
            "evidence_graph": self.evidence_graph.as_dict(),
            "narrative_arc": self.narrative_arc.as_dict(),
            "provenance": self.provenance.as_dict(),
            "sentence_provenance": (
                self.sentence_provenance.as_dict() if self.sentence_provenance else None
            ),
            "thesis": self.thesis,
            "cast": [e.as_dict() for e in self.cast],
            "chapters": [c.as_dict() for c in self.chapters],
        }

    def embed(self, envelope: dict[str, Any]) -> None:
        """把 artifact 注入 envelope，供 Gate 校验与前端消费。

        注入的键均为新增、可选字段，旧 envelope / 旧快照 fixture 不受影响。
        """
        envelope["theme_artifact"] = self.theme.as_dict()
        envelope["evidence_graph"] = self.evidence_graph.as_dict()
        envelope["narrative_arc"] = self.narrative_arc.as_dict()
        envelope["provenance"] = self.provenance.as_dict()
        envelope["sentence_provenance"] = (
            self.sentence_provenance.as_dict() if self.sentence_provenance else None
        )
        envelope["thesis"] = self.thesis
        envelope["cast"] = [e.as_dict() for e in self.cast]
        envelope["chapters"] = [c.as_dict() for c in self.chapters]
        envelope["curation_artifacts"] = self.to_dict()
        # CuratedStory：前端 StoryReader / NarrativeArc 直接消费的内容结构。
        #
        # route 刻意不重复注入：envelope["route"] 是唯一数据源。
        # 早先此处写 "route": envelope.get("route")，注释称"避免重复序列化"——那是错的：
        # Python 侧同一 dict 引用在 json.dumps 时会被完整输出两遍，实测 route 约占
        # envelope 体积的 49%（21.7KB / 44.6KB），等于让每次响应凭空胖一半；
        # 且共享引用一旦被任一侧 mutate 会互相污染。
        # 前端 storyView.buildStoryView() / machine.ts 全部读 env.route，无人读 cs.route，
        # 契约侧 CuratedStorySchema.route 已放宽为可选，故直接省掉。
        envelope["curated_story"] = {
            "id": self.theme.id,
            "theme": self.theme.as_dict(),
            "thesis": self.thesis,
            "cast": [e.as_dict() for e in self.cast],
            "chapters": [c.as_dict() for c in self.chapters],
            "evidenceGraph": self.evidence_graph.as_dict(),
            "quality": {
                "evidence_layers": len(
                    self.evidence_graph.coverage.get("dimensions_covered", []) or []
                ),
                "coverage_ratio": self.evidence_graph.coverage.get("uri_coverage", 1.0),
                "aligned_ratio": self.provenance.coverage_ratio,
            },
        }


# --------------------------------------------------------------------------
# 派生逻辑（纯函数：intent / plan / pack -> artifacts）
# --------------------------------------------------------------------------
_DIM_LABEL = {
    "person": "人物",
    "building": "建筑",
    "event": "事件",
    "era": "年代",
    "poem": "诗词",
}

# 数据源优先级（越小越靠前）—— 多源交叉验证时优先 SLC 馆藏与 curated
# landmark-facts（权威性高），次 amap 通用 POI。展示时同 cluster 内事实按
# 此序排序，截屏「数据来源」字段也会带出最权威出处。
_SOURCE_PRIORITY: dict[str, int] = {
    "geonames_corpus": 0,        # SLC 地名志
    "building_detail": 0,       # SLC 馆藏建筑详情
    "road_corpus": 0,           # SLC 路名志
    "literary_corpus": 0,       # SLC 文学交集
    "curated.landmark-facts": 1,# 本地 curated 历史风貌区词库
    "amap": 2,                  # 高德通用 POI（兜底）
}


def _layer_to_fact(layer: IdentityLayer, *, fallback_uri: str) -> EvidenceFact:
    rid = (layer.source.record_id or "").strip()
    if rid == "?":
        rid = ""
    return EvidenceFact(
        fact_uri=rid or fallback_uri,
        label=layer.label,
        assertion=layer.claim,
        layer=layer.kind,
        source_dataset=layer.source.dataset,
        confidence=1.0 if rid else 0.0,
    )


def _fact_dedup_key(fact: EvidenceFact) -> tuple[str, str, str]:
    """去重 key：(kind, label, dataset) —— fact_uri 为空时仍能跨 stop 去重

    同一人物/事件在多个 stop 的 layers 里被引用时，只入一次 evidence_graph。
    """
    return (fact.layer, fact.label, fact.source_dataset)


def _evidence_clusters(plan: RoutePlan, theme_id: str) -> tuple[list[EvidenceCluster], list[EvidenceFact]]:
    """按维度聚类事实；扁平聚合 + 跨 stop 去重 + 多源按权威优先级排序。

    去重策略：fact_uri 优先（精准）；fallback 到 (kind, label, dataset) 元组
    ——amap-only 站点无 record_id 时仍能去掉「马勒船王」跨 5 个章节的重复。
    多源时，SLC > curated.landmark-facts > amap（_SOURCE_PRIORITY）。
    """
    by_dim: dict[str, EvidenceCluster] = {}
    flat: list[EvidenceFact] = []
    seen_uris: set[str] = set()
    seen_keys: set[tuple[str, str, str]] = set()
    for s in plan.stops:
        be: BuildingEvidence = s.evidence
        for layer in be.layers:
            if layer.kind not in by_dim:
                by_dim[layer.kind] = EvidenceCluster(
                    id=f"cl-{layer.kind}",
                    dimension=layer.kind,
                    label=_DIM_LABEL.get(layer.kind, layer.kind),
                )
            fact = _layer_to_fact(layer, fallback_uri=be.buri or "")
            dkey = _fact_dedup_key(fact)
            if dkey in seen_keys:
                # 同一事实已被更靠前的 stop 收录；不再重复入栈。
                continue
            if fact.fact_uri and fact.fact_uri in seen_uris:
                continue
            if fact.fact_uri:
                seen_uris.add(fact.fact_uri)
            seen_keys.add(dkey)
            by_dim[layer.kind].facts.append(fact)
            flat.append(fact)
    # 多源时按权威优先级排序——SLC 馆藏 / curated 优先展示在前
    for cl in by_dim.values():
        cl.facts.sort(
            key=lambda f: (_SOURCE_PRIORITY.get(f.source_dataset, 9), -f.confidence)
        )
    clusters = list(by_dim.values())

    # 主题聚类：整条线一句话总结（来自 route-level theme）
    theme_cl = EvidenceCluster(id="cl-theme", dimension="theme", label="主题线索")
    clusters.append(theme_cl)
    return clusters, flat


def _evidence_joins(plan: RoutePlan, flat: list[EvidenceFact]) -> list[EvidenceJoin]:
    """buri 跨库 join：建筑 ↔ 其人物/事件；跨站点同人物 join。"""
    joins: list[EvidenceJoin] = []
    seen_person: dict[str, str] = {}
    for s in plan.stops:
        be: BuildingEvidence = s.evidence
        for layer in be.layers:
            if layer.kind in ("person", "event"):
                joins.append(
                    EvidenceJoin(
                        from_uri=be.buri or "",
                        to_uri=(layer.source.record_id or be.buri or ""),
                        relation="馆藏关联" + _DIM_LABEL.get(layer.kind, layer.kind),
                    )
                )
                if layer.kind == "person":
                    prev = seen_person.get(layer.label)
                    if prev:
                        joins.append(
                            EvidenceJoin(
                                from_uri=prev,
                                to_uri=layer.source.record_id or be.buri or "",
                                relation="同人物跨站点",
                            )
                        )
                    seen_person[layer.label] = layer.source.record_id or be.buri or ""
    return joins


def _coverage(
    clusters: list[EvidenceCluster],
    flat: list[EvidenceFact],
    pack: EvidencePack,
) -> dict[str, Any]:
    total = len(flat)
    with_uri = sum(1 for f in flat if f.fact_uri)
    dims = sorted({c.dimension for c in clusters if c.dimension != "theme"})
    return {
        "facts_total": total,
        "facts_with_uri": with_uri,
        "uri_coverage": round(with_uri / total, 4) if total else 1.0,
        "dimensions_covered": dims,
        "gaps": pack.gaps,
        "buildings_fetched": len(pack.buildings),
    }


def _research_axes(plan: RoutePlan, theme_id: str) -> list[ResearchAxis]:
    has_person = any(
        any(l.kind == "person" for l in s.evidence.layers) for s in plan.stops
    )
    has_event = any(
        any(l.kind == "event" for l in s.evidence.layers) for s in plan.stops
    )
    axes: list[ResearchAxis] = []
    if has_person:
        axes.append(
            ResearchAxis(
                axis="人物关系",
                hypothesis="这些名字先后被钉进同一坐标，构成可对照的群像。",
                evidence_cluster_ids=["cl-person"],
            )
        )
    if has_event:
        axes.append(
            ResearchAxis(
                axis="用途更替",
                hypothesis="事件记载显示同一栋楼的用途随年代被改写。",
                evidence_cluster_ids=["cl-event"],
            )
        )
    if not axes:
        axes.append(
            ResearchAxis(
                axis="建筑事实",
                hypothesis="以可核对的建筑事实为唯一叙事支点。",
                evidence_cluster_ids=["cl-building"],
            )
        )
    return axes


def _narrative_arc(plan: RoutePlan, theme_id: str) -> tuple[list[NarrativeNode], list[float]]:
    nodes: list[NarrativeNode] = []
    tension: list[float] = []
    n = len(plan.stops)
    for i, s in enumerate(plan.stops):
        be: BuildingEvidence = s.evidence
        kinds = {l.kind for l in be.layers}
        persons = [l for l in be.layers if l.kind == "person"]
        events = [l for l in be.layers if l.kind == "event"]

        # 节点叙事角色（G3）：首=Hook，尾=Afterimage，含事件变化=Contrast/Reveal
        if i == 0:
            role: NarrativeRole = "Hook"
        elif i == n - 1:
            role = "Afterimage"
        elif len(events) >= 1 and len(kinds) >= 2:
            role = "Contrast"
        elif len(persons) >= 1:
            role = "Reveal"
        else:
            role = "Anchor"

        beat = s.meaning or be.name
        refs = [l.source.record_id for l in be.layers if l.source.record_id]
        nodes.append(NarrativeNode(stop_index=s.order, role=role, beat=beat, facts_referenced=refs))

        # 张力曲线：基础 0.3，有人物/事件叠加，首尾略收
        t = 0.3 + (0.25 if persons else 0) + (0.25 if events else 0)
        if role in ("Hook", "Afterimage"):
            t = max(0.2, t - 0.1)
        tension.append(round(min(1.0, t), 2))
    return nodes, tension


def _provenance(plan: RoutePlan) -> ProvenanceReport:
    """G4：把每个 stop 的事实原子（IdentityLayer）逐一对齐到 fact_uri。

    规则：每条断言 = 一个 IdentityLayer 的 claim；其 fact_uri = 该层 source.record_id。
    因为叙事严格只由这些层构建（storycraft 约束），所以这是真实可校验的溯源。
    """
    per_stop: list[StopProvenance] = []
    total = 0
    aligned = 0
    for s in plan.stops:
        be: BuildingEvidence = s.evidence
        claims: list[AssertionClaim] = []
        for layer in be.layers:
            rid = (layer.source.record_id or "").strip()
            # "?" 是缺失标识的占位符，必须视为「未对齐」，否则 G4 安全网形同虚设
            ok = rid not in ("", "?", None)
            claims.append(
                AssertionClaim(
                    text=layer.claim,
                    fact_uri=rid or None,
                    aligned=ok,
                    layer=layer.kind,
                )
            )
            total += 1
            if ok:
                aligned += 1
        per_stop.append(StopProvenance(stop_index=s.order, assertions=claims))
    ratio = round(aligned / total, 4) if total else 1.0
    return ProvenanceReport(
        total_assertions=total,
        aligned_assertions=aligned,
        coverage_ratio=ratio,
        per_stop=per_stop,
    )


def _build_theme(
    intent: Intent,
    plan: RoutePlan,
    prop_set: PropositionSet | None,
    theme_id: str,
    route_theme: str,
    why: str,
    curator_note: str,
) -> Theme:
    """构造 G2-1 Theme：优先用 G1 LLM 命题集合，失败则回退规则。"""
    if prop_set:
        axes = []
        for p in prop_set.propositions:
            if getattr(p, "status", "allowed") == "dropped":
                continue
            cid = "cl-theme" if p.dimension == "theme" else f"cl-{p.dimension}"
            axes.append(
                ResearchAxis(
                    axis=p.axis,
                    hypothesis=p.hypothesis,
                    evidence_cluster_ids=[cid],
                )
            )
        return Theme(
            id=theme_id,
            title=prop_set.title or route_theme,
            open_question=prop_set.open_question or (intent.message or route_theme),
            research_axes=axes,
            why_visit=why,
            estimated_duration_min=plan.duration_min,
            scope_note=prop_set.scope_note or curator_note,
        )

    # 回退：规则式 research_axes（依据可用维度）
    open_question = (
        intent.message
        or f"在「{intent.scene}」一带，谁能让一栋楼装下不止一种人生？"
    )
    return Theme(
        id=theme_id,
        title=route_theme,
        open_question=open_question,
        research_axes=_research_axes(plan, theme_id),
        why_visit=why,
        estimated_duration_min=plan.duration_min,
        scope_note=curator_note,
    )


_ROLE_CHAPTER_LABEL: dict[str, str] = {
    "Hook": "引子",
    "Anchor": "锚点",
    "Contrast": "对照",
    "Reveal": "揭示",
    "Afterimage": "留白",
    "Bridge": "过渡",
}


def _build_cast(pack: EvidencePack) -> list[StoryEntity]:
    """从取证包抽取人物 / 建筑 / 事件三类「角色」，供前端 cast 与章节 castRefs 使用。

    按 (kind, name) 去重；建筑以 whitelist/buri 为锚，人物/事件以 layer.label 为锚。
    """
    seen: dict[tuple[str, str], StoryEntity] = {}
    for be in pack.buildings:
        bkey = ("building", be.name or be.buri or "")
        if bkey not in seen:
            seen[bkey] = StoryEntity(
                id=f"ent-building-{be.buri or be.name}",
                kind="building",
                name=be.name or "未命名建筑",
                fact_uri=(be.buri or None),
                note=(be.whitelist_id or None),
            )
        for layer in be.layers:
            if layer.kind in ("person", "event"):
                k = (layer.kind, layer.label)
                if k in seen:
                    continue
                seen[k] = StoryEntity(
                    id=f"ent-{layer.kind}-{layer.label}",
                    kind=layer.kind,
                    name=layer.label,
                    fact_uri=(layer.source.record_id or None),
                    note=(layer.claim or None),
                )
    return list(seen.values())


def _build_chapters(
    plan: RoutePlan,
    narrative_arc: NarrativeArc,
    cast: list[StoryEntity],
) -> list[StoryChapter]:
    """把叙事弧节点富化为前端可直接渲染的章节。

    每个章节带：标题（角色标签 + 站点名）、一句话悬念（node.beat）、
    与上一章的关系（meaning 串联）、证据 id、步行时长、关联角色引用。
    """
    cast_by_name = {e.name: e.id for e in cast}
    chapters: list[StoryChapter] = []
    prev_meaning: str | None = None
    for i, (node, stop) in enumerate(zip(narrative_arc.nodes, plan.stops)):
        be = stop.evidence
        role_label = _ROLE_CHAPTER_LABEL.get(node.role, "章节")
        title = f"{role_label}：{be.name or '站点'}"
        hook = node.beat or f"第 {i + 1} 站，{be.name}"
        relation: str | None = None
        if i > 0:
            cur = stop.meaning or be.name or "下一处"
            prev = prev_meaning or (plan.stops[i - 1].evidence.name or "上一站")
            relation = f"从「{prev}」走向「{cur}」"
        refs: list[str] = []
        if be.name and be.name in cast_by_name:
            refs.append(cast_by_name[be.name])
        for layer in be.layers:
            cid = cast_by_name.get(layer.label)
            if cid and cid not in refs:
                refs.append(cid)
        chapters.append(
            StoryChapter(
                id=f"ch-{i + 1}",
                index=i + 1,
                title=title,
                hook=hook,
                narrative_role=node.role,
                stop_id=node.stop_index,
                relation_to_previous=relation,
                evidence_ids=list(node.facts_referenced),
                walking_minutes=int(stop.minutes or 0),
                cast_refs=refs,
            )
        )
        prev_meaning = stop.meaning or be.name
    return chapters


def build_artifacts(
    intent: Intent,
    plan: RoutePlan,
    pack: EvidencePack,
) -> CurationArtifacts:
    """从 (intent, plan, pack) 派生四个一等公民中间产物 + 句子级 G4 容器。

    顺序：先建证据图（cluster id 决定了 G1 命题的维度映射），再做 G1 命题分解，
    再合成 Theme；句子级 G4 在 pipeline 中对 *最终* 叙事（post-polish）单独计算。
    """
    theme_id = f"theme-{uuid.uuid4().hex[:8]}"
    route_theme, route_logic, curator_note, why = craft_route_voice(plan, intent)

    # G2-2 证据图（先建，cluster id 供 G1 维度映射）
    clusters, flat = _evidence_clusters(plan, theme_id)
    joins = _evidence_joins(plan, flat)
    coverage = _coverage(clusters, flat, pack)
    evidence_graph = EvidenceGraph(
        theme_id=theme_id, clusters=clusters, joins=joins, coverage=coverage
    )

    # G1：LLM 命题分解（不可用时回退规则）
    available_dims = sorted({c.dimension for c in clusters if c.dimension != "theme"})
    prop_set = decompose_intent(intent, plan, pack, available_dims)
    theme_obj = _build_theme(intent, plan, prop_set, theme_id, route_theme, why, curator_note)

    # G2-3 叙事弧
    nodes, tension = _narrative_arc(plan, theme_id)
    narrative_arc = NarrativeArc(theme_id=theme_id, nodes=nodes, tension_curve=tension)

    # G4（layer 级）：每条 IdentityLayer 断言对齐 fact_uri
    provenance = _provenance(plan)

    # 故事优先：从取证包抽取角色，并把叙事弧富化为章节
    cast = _build_cast(pack)
    chapters = _build_chapters(plan, narrative_arc, cast)
    thesis = theme_obj.open_question

    return CurationArtifacts(
        theme=theme_obj,
        evidence_graph=evidence_graph,
        narrative_arc=narrative_arc,
        provenance=provenance,
        thesis=thesis,
        cast=cast,
        chapters=chapters,
    )
