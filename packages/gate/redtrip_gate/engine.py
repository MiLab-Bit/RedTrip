from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .envelope import PLAN_ENVELOPE

HAIPAI = {
    "#33333A",
    "#B9824F",
    "#7C8A8D",
    "#EDE4D3",
    "#A8322A",
    "#F2EBDD",
    # lowercase variants
    "#33333a",
    "#b9824f",
    "#7c8a8d",
    "#ede4d3",
    "#a8322a",
    "#f2ebdd",
}

FORBIDDEN_COPY = (
    "一键",
    "省事",
    "省时",
    "省力",
    "再也不用查攻略",
    "伟大的革命",
    "永垂不朽",
    "集合出发",
    "打卡任务",
    "带队前往",
    # B1 套话治理（吸收 Gemini 文学陈词清单）：叙事中出现的即判 Q8 拦截
    "融汇中西",
    "值得一提的是",
    "仿佛穿越回老上海",
    "穿越回老上海",
    "仿佛穿越",
    "历史与现代在此交融",
    "古今交融",
    "仿佛时光倒流",
    "充满浓厚生活气息",
    # 注意：故事卡（PRD R-06）允许第二人称；导游腔命令式仅在长散文 essay 中拦截
    # （见 _ESSAY_YOU_FAMILY）。勿把「你站在」等放回 FORBIDDEN_COPY，否则红队基线与产品口径冲突。
)

# ── 长散文「路线零件」专属 Gate 规则 ──
# 设计原则（防降智）：长散文允许「同行者口吻」——自然对行走者用「你」（你若在此驻足 /
# 你抬头看），这是把读者当同行伙伴而非指挥游客。因此 essay 只禁导游腔命令式；
# 同时禁把 A–F 软骨架写成可见标签 / markdown 标题。
_ESSAY_YOU_FAMILY = (  # 仅对 essay body/title 生效的导游腔命令式
    "你站在", "你脚下", "你忽然", "你此刻", "你离开",
    "你遇见", "你带走", "你眼前", "你带着", "你会先遇见",
)
_ESSAY_STRUCTURE_BAN = (  # 禁止把六段结构写成可见标签 / 标题 / 编号
    "从现场进入", "地方的时间叠层", "人物进入", "城市机制浮现",
    "给行走者的动作与问题", "路线零件", "时间叠层",
    "下一站是", "接下来我们将前往", "让我们继续探索",
)
# 反怀旧软告警：把贫困 / 衰败 / 旧物浪漫化为「价值」时提醒补具体事实
# （来自「策展委员会」评审 prompt 的反 nostalgia 规则；仅 warn 不 block，避免逼出绕弯写法）
NOSTALGIA_WARN = (
    "烟火气", "老上海的味道", "时光在这里慢下来", "时光仿佛慢下来",
    "慢生活", "旧时光", "市井烟火", "原汁原味", "老底子", "旧时光的味道",
)

REQUIRED_TOP = (
    "intent",
    "theme",
    "logic_line",
    "aesthetic",
    "scenario",
    "why_visit",
    "sources",
    "blocks",
    "curator_note",
    "route",
)


@dataclass
class GateVerdict:
    passed: bool
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "blockers": list(self.blockers),
            "warnings": list(self.warnings),
        }


def evaluate_envelope(envelope: dict[str, Any] | None) -> GateVerdict:
    blockers: list[str] = []
    warnings: list[str] = []

    if not isinstance(envelope, dict):
        return GateVerdict(False, ["GATE: envelope 为空或非对象"], [])

    # A1 / A5 contract
    for key in REQUIRED_TOP:
        val = envelope.get(key)
        if val in (None, "", [], {}):
            blockers.append(f"A1: 缺少字段 {key}")

    route = envelope.get("route") or {}
    stops = route.get("stops") or []
    if not isinstance(stops, list):
        blockers.append("A1: route.stops 非法")
        stops = []

    n = len(stops)
    if n < PLAN_ENVELOPE.min_stops:
        blockers.append(f"Q4: 点位过少 ({n})")
    elif n > PLAN_ENVELOPE.max_stops:
        blockers.append(f"Q4: 点位过多 ({n})")
    elif n > PLAN_ENVELOPE.warn_max_stops:
        warnings.append(f"Q4[warn]: 建议 ≤{PLAN_ENVELOPE.warn_max_stops} 点，当前 {n}")

    duration = route.get("duration_min")
    if isinstance(duration, (int, float)) and duration > PLAN_ENVELOPE.max_duration_min:
        blockers.append(f"Q4: 总时长超 {PLAN_ENVELOPE.max_duration_min}min ({duration})")

    # Collect narrative text for Q8（卡片 / 元数据走常规 FORBIDDEN_COPY；
    # 长散文 essay 单独收集，走专属规则，允许「同行者口吻」）
    texts: list[str] = [
        str(envelope.get("curator_note") or ""),
        str(envelope.get("why_visit") or ""),
        str(envelope.get("theme") or ""),
        str(envelope.get("logic_line") or ""),
    ]
    essay_texts: list[tuple[int, str]] = []  # (stop_order, text)
    for b in envelope.get("blocks") or []:
        if isinstance(b, dict):
            if b.get("type") == "essay":
                so = b.get("stop_order")
                essay_texts.append((so, str(b.get("body") or "")))
                essay_texts.append((so, str(b.get("title") or "")))
            else:
                texts.extend(
                    [
                        str(b.get("body") or ""),
                        str(b.get("title") or ""),
                        str(b.get("lead") or ""),
                        str(b.get("coda") or ""),
                    ]
                )

    for s in stops:
        if not isinstance(s, dict):
            blockers.append("A1: stop 非对象")
            continue
        texts.append(str(s.get("meaning") or ""))
        texts.append(str(s.get("transition_to_next") or ""))

        # Q2 layers + sources
        layers = s.get("layers") or []
        rd = s.get("raw_detail") or {}
        if not layers:
            # 地标库/高德 POI 通道的点：无 layers 但有地址/类别上下文也能策展
            # （素材在 raw_detail，polish 已注入 stop_metadata）。有上下文 → warning，
            # 完全空白才 blocker——否则 amap-only 场景整本被 Gate 打回模板。
            if rd.get("address") or rd.get("category") or rd.get("poi_type"):
                warnings.append(
                    f"Q2[warn]: 点位无 layers（有地址/类别上下文）— {s.get('name')}"
                )
            else:
                blockers.append(f"Q2: 点位无 layers — {s.get('name')}")
        for layer in layers:
            if not isinstance(layer, dict):
                blockers.append(f"Q2: layer 非对象 — {s.get('name')}")
                continue
            claim = layer.get("claim")
            src = layer.get("source")
            if claim and not isinstance(src, dict):
                blockers.append(f"Q2: claim 无 source 对象 — {s.get('name')}")
                continue
            if isinstance(src, dict):
                rid = src.get("record_id")
                # "?" 是缺失标识的占位符，必须视为缺 record_id
                if not src.get("dataset") or str(rid).strip() in ("", "?", "None"):
                    blockers.append(
                        f"Q2: source 缺 dataset/record_id — {s.get('name')}/{layer.get('label')}"
                    )

        # Q7 pitfalls
        pitfalls = s.get("pitfalls") or {}
        for fld in ("open_hours", "enterable", "need_reservation"):
            val = pitfalls.get(fld) if isinstance(pitfalls, dict) else None
            if val in (None, ""):
                blockers.append(f"Q7: {fld} 空 — {s.get('name')}")

        # Q6 / NG-10 precision honesty
        geo = s.get("geo") or {}
        if isinstance(geo, dict):
            precision = geo.get("precision")
            coord_source = geo.get("coord_source")
            if precision == "exact" and coord_source in ("none", None, ""):
                blockers.append(
                    f"Q6: precision=exact 但 coord_source 无效 — {s.get('name')}"
                )
            if precision not in ("exact", "approximate", "schematic"):
                blockers.append(f"Q6: precision 非法 — {s.get('name')}")

        # R19 transitions
        transition = s.get("transition_to_next")
        if transition:
            t = str(transition)
            physical = ("步行" in t or "距离" in t or "分钟可达" in t) and (
                "记载" not in t and "馆藏" not in t and "事件" not in t and "人物" not in t
            )
            if physical:
                blockers.append(f"R19: 衔接疑似纯物理理由 — {s.get('name')}")

        minutes = s.get("minutes")
        if isinstance(minutes, (int, float)) and not (3 <= minutes <= 30):
            warnings.append(f"Q4[warn]: 单点时长异常 {minutes} @ {s.get('name')}")

    # Story cards density (Q1 warn)
    story_cards = [
        b
        for b in (envelope.get("blocks") or [])
        if isinstance(b, dict) and b.get("type") == "story_card"
    ]
    if len(story_cards) < 3:
        warnings.append(f"Q1[warn]: story_card < 3（当前 {len(story_cards)}）")
    for card in story_cards:
        for src in card.get("sources") or []:
            if not isinstance(src, dict):
                blockers.append(
                    f"Q2: story_card 出处非对象 — {card.get('title') or card.get('stop_order')}"
                )
                continue
            rid = src.get("record_id")
            if not src.get("dataset") or str(rid).strip() in ("", "?", "None"):
                blockers.append(
                    f"Q2: story_card 缺出处 — {card.get('title') or card.get('stop_order')}"
                )

    blob = "\n".join(texts)
    for bad in FORBIDDEN_COPY:
        if bad in blob:
            blockers.append(f"Q8: 文案含禁用词「{bad}」")

    # ── 长散文「路线零件」专属规则 ──
    # 1) 允许同行者口吻（自然「你」），但禁导游腔命令式 + 禁把 A–F 结构写成可见标签。
    _essay_forbidden = set(FORBIDDEN_COPY) | set(_ESSAY_STRUCTURE_BAN) | {"##"}
    for so, et in essay_texts:
        for bad in _essay_forbidden:
            if bad in et:
                blockers.append(
                    f"Q8[essay#{so}]: 长散文含禁用结构/措辞「{bad}」"
                )
        for bad in _ESSAY_YOU_FAMILY:
            if bad in et:
                blockers.append(
                    f"Q8[essay#{so}]: 长散文含导游腔命令式「{bad}」"
                )
        # 反怀旧软告警（仅 warn）：浪漫化贫困/衰败而未补具体事实时提醒
        for w in NOSTALGIA_WARN:
            if w in et:
                warnings.append(
                    f"反怀旧[essay#{so}]: 出现「{w}」，建议补具体现场/史实以免浪漫化"
                )
    # 2) 置信度 hedge 软告警：essay provenance 中标记 C 级的 factual 句，
    #    若文本无任何归属词（据/记载/标注/显示/称/高德分类），提示补归属。
    _HEDGE_MARKERS = ("据", "记载", "标注", "显示", "称", "高德分类", "地图", "研究假设", "待核查", "地方传闻")
    for b in envelope.get("blocks") or []:
        if not isinstance(b, dict) or b.get("type") != "essay":
            continue
        so = b.get("stop_order")
        prov = b.get("provenance")
        if not isinstance(prov, list):
            continue
        for s in prov:
            if not isinstance(s, dict) or s.get("kind") != "factual":
                continue
            grades = s.get("grades") or []
            if "C" not in grades:
                continue
            txt = str(s.get("text") or "")
            if txt and not any(m in txt for m in _HEDGE_MARKERS):
                warnings.append(
                    f"置信度[essay#{so}]: C级事实句未带归属词——「{txt[:24]}…」"
                )

    # Palette scan (optional color fields)
    def walk(obj: Any, path: str = "$") -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k.lower() == "color" and isinstance(v, str):
                    if v not in HAIPAI and v.upper() not in {c.upper() for c in HAIPAI}:
                        blockers.append(f"Q6: 越界色 {path}.{k}={v}")
                walk(v, f"{path}.{k}")
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                walk(v, f"{path}[{i}]")

    walk(envelope)

    # Multi-layer presence warning
    multi = 0
    for s in stops:
        kinds = {l.get("kind") for l in (s.get("layers") or []) if isinstance(l, dict)}
        if len(kinds) >= 2:
            multi += 1
    if multi < 1:
        warnings.append("路线缺少多重身份点（building+event/person）")

    # ---- G4: 细粒度溯源（断言 ↔ 事实，核心承诺）----
    # 任何一条事实断言缺少 fact_uri 即拦截；覆盖率必须 = 1.0。
    prov = envelope.get("provenance")
    if isinstance(prov, dict):
        total = int(prov.get("total_assertions") or 0)
        aligned = int(prov.get("aligned_assertions") or 0)
        ratio = prov.get("coverage_ratio")
        for sp in prov.get("per_stop") or []:
            if not isinstance(sp, dict):
                continue
            for a in sp.get("assertions") or []:
                if isinstance(a, dict) and not a.get("aligned"):
                    blockers.append(
                        f"G4: 存在未对齐事实断言 — stop {sp.get('stop_index')}"
                    )
        if total and aligned < total:
            blockers.append(f"G4: 溯源覆盖率不足（{aligned}/{total}）")
        elif isinstance(ratio, (int, float)) and ratio < 1.0:
            blockers.append(f"G4: 溯源覆盖率 {ratio}")

    # ---- G4-sentence: 句子级细粒度溯源（事实句必须可溯源；warn 级，保守不阻断）----
    # 与上面的 layer 级 G4（硬约束）互补：本检查针对 *渲染后* 叙事文本，
    # 标注每个事实句是否落到 fact_uri。事实句未溯源仅告警，避免误伤润色表达。
    sp = envelope.get("sentence_provenance")
    if isinstance(sp, dict):
        factual = int(sp.get("factual_sentences") or 0)
        aligned = int(sp.get("aligned_factual") or 0)
        if factual and aligned < factual:
            warnings.append(
                f"G4-sentence[warn]: {factual - aligned} 个事实句未溯源"
            )

    # ---- Interest (I1): 事实对但「无聊」拦截（warn 级，保守不阻断）----
    eg = envelope.get("evidence_graph")
    na = envelope.get("narrative_arc")
    if isinstance(eg, dict) or isinstance(na, dict):
        tension_stops = 0
        for s in stops:
            if not isinstance(s, dict):
                continue
            layers = [l for l in (s.get("layers") or []) if isinstance(l, dict)]
            has_person = any(l.get("kind") == "person" for l in layers)
            has_event = any(l.get("kind") == "event" for l in layers)
            if has_person or has_event:
                tension_stops += 1
        if tension_stops < 2:
            warnings.append(
                "I1[warn]: 路线叙事张力偏弱（含人物/事件对照的站点 < 2）"
            )
        if isinstance(na, dict):
            roles = {
                nd.get("role")
                for nd in (na.get("nodes") or [])
                if isinstance(nd, dict)
            }
            if len(roles) < 2:
                warnings.append(
                    "I1[warn]: 叙事节点角色单一，缺乏节奏变化"
                    "（Hook/Contrast/Reveal/Afterimage）"
                )

    # de-dupe
    blockers = list(dict.fromkeys(blockers))
    warnings = list(dict.fromkeys(warnings))
    return GateVerdict(passed=len(blockers) == 0, blockers=blockers, warnings=warnings)
