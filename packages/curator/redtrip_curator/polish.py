"""LLM polish on evidence-bound draft. Never invents facts; Gate re-checks.

B4（章节级流式润色，替代原单次整本大调用）：
  1) 一次元数据调用：theme / logic_line / why_visit / curator_note + 逐站
     meaning / transition_to_next（输出小，先出，作为后续卡片调用的风格上下文）。
  2) 每站 story_card 一次调用：title / body / age_parallel + 该卡逐句溯源
     （彼此独立，在 ThreadPoolExecutor 中并行；max_workers 封顶 4）。
  3) 卡片完成一张即通过 on_chapter 回调推送（供 SSE chapter_ready 做
     「边生成边读」），整本聚合结果仍作为返回值走既有 Gate。

与整本版的约束完全一致：_suspicious_new_years 年份防编造、sources 永不触碰、
单卡失败仅回退该卡为模板、provenance 缺失安全降级。
"""
from __future__ import annotations

import copy
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable

from .hongyuan import VoicePack
from .llm import chat_json, llm_configured
from .models import RoutePlan
from .storyline import detect_arc
from .sentence_provenance import (
    SentenceClaim,
    SentenceProvenanceReport,
    StopSentenceProvenance,
    _fact_catalog,
    _grade_for,
    _heuristic_align,
    _split_sentences,
)

_PROMPT_PATH = (
    Path(__file__).resolve().parents[1] / "prompts" / "polish_narrative.txt"
)
_ESSAY_PROMPT_PATH = (
    Path(__file__).resolve().parents[1] / "prompts" / "essay_narrative.txt"
)

_META_SCHEMA = """JSON schema（本次仅输出元数据与站点衔接，不输出 story_cards）：
{
  "theme": "string",
  "logic_line": "string",
  "why_visit": "string",
  "curator_note": "string",
  "stops": [{"order": 1, "meaning": "string", "transition_to_next": "string|null"}]
}"""

# B1：套话治理统一由 Gate 末端复核（FORBIDDEN_COPY），润色提示不再重复注入，
# 避免模型为躲避长串负向清单而逼出绕弯措辞。

# 去模板化（叙事策略重写）：篇幅听从素材，软上限、宁短勿注水；不再强制三节骨架。
_CARD_TARGET_CHARS = "按素材丰度自然伸缩，通常 700–1200 字，上限约 1500；宁短勿注水，绝不凑字数堆砌空话"
_CARD_BODY_GUIDANCE = (
    "【篇幅与写法】body 写成连贯、有呼吸的散文，像一位懂这地方的作者在对读者说话；"
    f"篇幅听从素材——{_CARD_TARGET_CHARS}。结构服务于内容：历史沿革、人物、怎么逛"
    "可以交织着写，不必切成固定三段、不要使用 markdown 小标题（## 之类）；"
    "某一站没有人物记载就老老实实写空间与年代，不必硬凑一段「人物」。"
)

_CARD_SCHEMA = """JSON schema（本次仅输出该站点的一张 story_card 与逐句溯源）：
{
  "title": "string",
  "body": "string",
  "age_parallel": "string|null",
  "provenance": [{"text": <原句>, "kind": "factual"|"connective",
                  "fact_uris": [<仅取自该站 fact_catalog 的 fact_uri>]}]
}
provenance 的 connective（纯过渡/抒情）句 fact_uris 为空；只能使用给定 fact_uri，
严禁编造；难以判断时可省略 provenance 字段。"""

# 「路线零件」长散文（essay）：独立于卡片的深度批判性长文。
# 软骨架（A–F 作为节奏而非硬配额）、置信度感知、同行者口吻、禁结构标签——
# 全部约束已写进 essay_narrative.txt；此处仅给 JSON schema 与篇幅指引。
# 单站目标约 8000–10000 字：端点默认输出上限（~4096 token）是此前被截短的根本原因，
# 故显式拉高 max_tokens；可用 REDTRIP_ESSAY_MAX_TOKENS 覆盖（按模型实际输出上限调整）。
_ESSAY_TARGET_CHARS = "目标约 8000–10000 字（上限约 10000），素材足够就写得深、写得慢，宁长勿碎但不注水"
_ESSAY_MAX_TOKENS = int(os.getenv("REDTRIP_ESSAY_MAX_TOKENS", "16000"))
_ESSAY_BODY_GUIDANCE = (
    "【篇幅与写法】body 写成连贯、有呼吸的长散文，像一位懂这地方的作者站在现场对同行者说话；"
    f"{_ESSAY_TARGET_CHARS}。A–F 六段是注意力的移动，不是要打的勾——禁止写成 ## 小标题或"
    "A./B./C. 编号或「从现场进入：」这类可见标签，结构必须化进流动的散文里。"
    "允许长段落、允许铺陈现场与层层时间叠层，但每一段都要承载具体材料或命题推进，"
    "绝不为了凑字数堆砌空话。事实按 fact_catalog 里的 grade 措辞：A/B 作确定陈述，C 带轻度归属，"
    "catalog 之外只能以「待核查/地方传闻/研究假设」写成开放问题。"
)

_ESSAY_SCHEMA = """JSON schema（本次仅输出该站点的一篇长散文与逐句溯源）：
{
  "title": "string",
  "body": "string",
  "provenance": [{"text": <原句>, "kind": "factual"|"connective",
                  "fact_uris": [<仅取自该站 fact_catalog 的 fact_uri>],
                  "grades": [<对应 fact_uri 的 A/B/C/D/E>]}]
}
provenance 的 connective（纯过渡/抒情/提问）句 fact_uris 与 grades 为空；
只能使用给定 fact_uri 与 grade，严禁编造；难以判断时可省略 provenance 字段。"""


def _system_prompt() -> str:
    if _PROMPT_PATH.exists():
        return _PROMPT_PATH.read_text(encoding="utf-8")
    return (
        "只润色语气，不新增史实。只输出 JSON。"
        "字段：theme, logic_line, why_visit, curator_note, stops, story_cards。"
    )


def _essay_system_prompt() -> str:
    """长散文「路线零件」系统提示（独立于卡片 prompt，自带 A–F 软骨架与置信度感知）。"""
    if _ESSAY_PROMPT_PATH.exists():
        return _ESSAY_PROMPT_PATH.read_text(encoding="utf-8")
    return (
        "为路线节点写一篇 800–1500 字批判性长散文（路线零件）。只输出 JSON。"
        "字段：title, body, provenance。"
    )


def _collect_claims(envelope: dict[str, Any]) -> list[str]:
    claims: list[str] = []
    for s in envelope.get("route", {}).get("stops") or []:
        if not isinstance(s, dict):
            continue
        for layer in s.get("layers") or []:
            if isinstance(layer, dict) and layer.get("claim"):
                claims.append(str(layer["claim"]))
    # de-dupe keep order
    return list(dict.fromkeys(claims))


def _extract_tokens(claims: list[str]) -> set[str]:
    """Years and CJK name-ish tokens appearing in evidence."""
    toks: set[str] = set()
    for c in claims:
        for y in re.findall(r"\d{3,4}", c):
            toks.add(y)
        for name in re.findall(r"[\u4e00-\u9fff]{2,4}", c):
            toks.add(name)
    return toks


def _suspicious_new_years(text: str, allowed: set[str]) -> list[str]:
    found = []
    for y in re.findall(r"(?<!\d)(?:1[6-9]\d{2}|20[0-2]\d)(?!\d)", text):
        if y not in allowed:
            found.append(y)
    return found


def _fact_catalog_by_stop(plan: RoutePlan) -> dict[int, list[dict[str, Any]]]:
    """按 stop_order 分组事实目录，供润色调用产出句子溯源。

    对 amap-only 站点（无 layers）注入地址/Poi 类型/地名志描述作为事实，
    让 LLM 至少有依据可写，不再因 facts<3 整本回退模板。
    """
    out: dict[int, list[dict[str, Any]]] = {}
    for f in _fact_catalog(plan):
        so = int(f.get("stop_index") or 0)
        out.setdefault(so, []).append(
            {"fact_uri": f["fact_uri"], "label": f["label"], "claim": f["claim"]}
        )

    # B6/B7：补齐 amap-only 站点（无 layers）—— 用地点地址/Poi 类型/地名志描述
    # 充作「事实」，避免 LLM 因完全无依据整本回退模板。
    # 命中 curated landmark-facts 时同时把 年份/风格/建筑设计师/简介 作为事实，
    # 让 polish 写「外滩1号亚细亚大楼 1906 新古典」这种真实叙述。
    for s in plan.stops:
        so = int(getattr(s, "id", None) or s.order)
        be = s.evidence
        rd = be.raw_detail or {}
        # landmark_* 字段即使有 layers 也补充（白名单 + landmark 双数据源叠加）
        existing_facts = out.get(so) or []
        has_landmark_year = any("年" in f.get("label", "") for f in existing_facts)
        synthetic: list[dict[str, Any]] = []
        addr = rd.get("address") or be.address
        if addr:
            synthetic.append(
                {
                    "fact_uri": f"amap:address:{be.name}",
                    "label": "地址",
                    "claim": f"地址：{addr}",
                }
            )
        pt = rd.get("poi_type") or ""
        if pt:
            synthetic.append(
                {
                    "fact_uri": f"amap:type:{be.name}",
                    "label": "场所类型",
                    "claim": f"高德分类：{pt}",
                }
            )
        # 地标库分类（策展语境：历史建筑风貌/博物馆美术馆/滨水地标…）——
        # 给 amap-only 站点一条策展线索，避免 LLM 无类别语境空转
        cat = rd.get("category") or ""
        if cat:
            synthetic.append(
                {
                    "fact_uri": f"amap:category:{be.name}",
                    "label": "场所类别",
                    "claim": f"场所类别：{cat}",
                }
            )
        # landmark 字段注入（含年份/风格/建筑设计师/简介）
        lk_year = rd.get("landmark_year_built")
        if lk_year and not has_landmark_year:
            synthetic.append(
                {
                    "fact_uri": f"curated.year:{be.name}",
                    "label": "建造年份",
                    "claim": f"{be.name} 始建：{lk_year}",
                }
            )
        lk_style = rd.get("landmark_style")
        if lk_style:
            synthetic.append(
                {
                    "fact_uri": f"curated.style:{be.name}",
                    "label": "建筑风格",
                    "claim": f"{be.name} 风格：{lk_style}",
                }
            )
        lk_arch = rd.get("landmark_architect")
        if lk_arch:
            synthetic.append(
                {
                    "fact_uri": f"curated.architect:{be.name}",
                    "label": "建筑师",
                    "claim": f"{be.name} 设计：{lk_arch}",
                }
            )
        lk_desc = rd.get("landmark_description")
        if lk_desc:
            synthetic.append(
                {
                    "fact_uri": f"curated.desc:{be.name}",
                    "label": "建筑沿革",
                    "claim": lk_desc[:240],
                }
            )
        desc = rd.get("description") or ""
        if desc and not lk_desc:  # landmark 描述优先
            synthetic.append(
                {
                    "fact_uri": f"geonames:desc:{be.name}",
                    "label": "沿革记载",
                    "claim": desc[:240],
                }
            )
        if synthetic:
            out.setdefault(so, []).extend(synthetic)

    # 回填置信度分级：真实 layers 已在 _facts_of 带 grade；这里为 amap/curated
    # 合成事实补 grade（按 fact_uri 前缀映射数据源），供 essay/card 按需 hedge。
    for so, lst in out.items():
        for f in lst:
            if "grade" not in f:
                ds = str(f.get("fact_uri", "")).rsplit(":", 1)[0]
                f["dataset"] = ds
                f["grade"] = _grade_for(ds, True)
    return out


def _build_sp_report_from_polish(
    patch: dict[str, Any], plan: RoutePlan, draft: dict[str, Any]
) -> SentenceProvenanceReport | None:
    """从润色调用返回的逐卡 story_provenance 构造句子级溯源报告。

    story_card 走模型标注（与润色同源，结构一致）；route_card 无单 stop 归属，
    回退本地启发式（B2 精神）。任意缺标/异常都安全降级，绝不抛错阻断。
    """
    cat_by_stop = _fact_catalog_by_stop(plan)
    per_stop: list[StopSentenceProvenance] = []
    total = factual = aligned = 0

    for item in patch.get("story_provenance") or []:
        if not isinstance(item, dict):
            continue
        so = int(item.get("stop_order") or 0)
        scoped = cat_by_stop.get(so, [])
        claims: list[SentenceClaim] = []
        for s in item.get("sentences") or []:
            if not isinstance(s, dict):
                continue
            text = str(s.get("text") or "")
            kind = "factual" if s.get("kind") == "factual" else "connective"
            uris = [
                u
                for u in (s.get("fact_uris") or [])
                if isinstance(u, str) and any(u == f["fact_uri"] for f in scoped)
            ]
            labels = [f["label"] for f in scoped if f["fact_uri"] in uris]
            claims.append(
                SentenceClaim(
                    index=len(claims), text=text, kind=kind,
                    fact_uris=uris, fact_labels=labels, aligned=bool(uris),
                )
            )
        per_stop.append(
            StopSentenceProvenance(
                stop_index=so, source_block="story_card", sentences=claims
            )
        )

    # route_card：本地启发式（B2 精神，零网络）
    for b in draft.get("blocks") or []:
        if isinstance(b, dict) and b.get("type") == "card":
            sents = _split_sentences(str(b.get("body") or ""))
            claims = _heuristic_align(sents, _fact_catalog(plan), 0)
            per_stop.append(
                StopSentenceProvenance(
                    stop_index=0, source_block="route_card", sentences=claims
                )
            )

    for sp in per_stop:
        for c in sp.sentences:
            total += 1
            if c.kind == "factual":
                factual += 1
                if c.aligned:
                    aligned += 1
    cov = round(aligned / factual, 4) if factual else 1.0
    return SentenceProvenanceReport(
        total_sentences=total,
        factual_sentences=factual,
        aligned_factual=aligned,
        coverage_ratio=cov,
        per_stop=per_stop,
    )


# ── 元数据润色（theme / logic_line / why_visit / curator_note + 逐站衔接）──
def _draft_meta_payload(envelope: dict[str, Any]) -> dict[str, Any]:
    stops_in = []
    for s in envelope.get("route", {}).get("stops") or []:
        if not isinstance(s, dict):
            continue
        stops_in.append(
            {
                "order": s.get("order"),
                "name": s.get("name"),
                "meaning": s.get("meaning"),
                "transition_to_next": s.get("transition_to_next"),
            }
        )
    return {
        "theme": envelope.get("theme"),
        "logic_line": envelope.get("logic_line"),
        "why_visit": envelope.get("why_visit"),
        "curator_note": envelope.get("curator_note"),
        "aesthetic": envelope.get("aesthetic"),
        "stops": stops_in,
    }


def _chat_meta(
    draft: dict[str, Any],
    voice: VoicePack | None,
    plan: RoutePlan,
    allowed_years: set[str],
) -> tuple[dict[str, Any] | None, list[str]]:
    """元数据 + 逐站衔接，单次调用。失败返回 (None, notes)。"""
    payload: dict[str, Any] = {
        "draft": _draft_meta_payload(draft),
        "fact_catalog_by_stop": _fact_catalog_by_stop(plan),
    }
    voice_block = voice.as_prompt_block() if voice else "（未抽签，保持克制润色）"

    # step④：叙事弧——仅据证据识别贯穿主线，要求 theme/logic_line 写成可贯穿全本的线
    arc = detect_arc(plan)
    arc_block = ""
    main = arc.get("main_thread")
    if main:
        arc_block = (
            "\n\n【叙事弧（典籍新生主线）】本路线的贯穿主线已据证据自动识别为："
            f"类型={main['type']}，人物/朝代={main['label']}，覆盖第 {main['orders']} 站。"
            "请把 theme / logic_line 写成一条可贯穿全本的「线」：开头点出这条主线"
            "（城市记忆被放大、古老足迹被发掘与溯源），中间各章沿主线递进，"
            "结尾收束到「写成书」的策展感。logic_line 必须显式串起主线与每一站的关联，"
            "不要用泛泛的「历史与现代交融」「独树一帜」替代具体事实。"
        )

    user = (
        f"{voice_block}\n\n"
        "以下是已取证事实目录（fact_catalog_by_stop）与模板草稿。"
        "请只润色叙事字段（theme / logic_line / why_visit / curator_note 与各站 "
        "meaning / transition_to_next），返回 JSON。\n"
        + json.dumps(payload, ensure_ascii=False)
        + "\n\n" + _META_SCHEMA
        + arc_block
        + "\n\n【衔接句纪律】transition_to_next 必须仍是史实/人物/记载理由，"
        "禁止「步行可达/顺路」当主理由；套话与禁词由 Gate 在末端统一复核，"
        "本提示不再重复列举，请自然写出即可。"
    )
    temperature = 0.55 if voice else 0.35
    try:
        patch = chat_json(
            system=_system_prompt(), user=user, temperature=temperature,
            backend="auto", role="creative",
            timeout=120,
        )
    except Exception as e:  # noqa: BLE001
        return None, [f"元数据润色失败，回退模板：{e}"]
    if not isinstance(patch, dict):
        return None, ["元数据润色返回非对象，回退模板"]
    return patch, []


def _apply_meta(
    out: dict[str, Any], meta_patch: dict[str, Any], allowed_years: set[str]
) -> list[str]:
    """merge 元数据字段 + stops。返回 notes。"""
    notes: list[str] = []

    def take_str(key: str) -> None:
        val = meta_patch.get(key)
        if isinstance(val, str) and val.strip():
            bad = _suspicious_new_years(val, allowed_years)
            if bad:
                notes.append(f"拒绝字段 {key}：出现未取证年份 {bad[:3]}")
                return
            out[key] = val.strip()

    for key in ("theme", "logic_line", "why_visit", "curator_note"):
        take_str(key)

    stop_by_order = {
        s.get("order"): s
        for s in (out.get("route") or {}).get("stops") or []
        if isinstance(s, dict)
    }
    for item in meta_patch.get("stops") or []:
        if not isinstance(item, dict):
            continue
        stop = stop_by_order.get(item.get("order"))
        if not stop:
            continue
        for field in ("meaning", "transition_to_next"):
            val = item.get(field)
            if val is None or not isinstance(val, str):
                continue
            bad = _suspicious_new_years(val, allowed_years)
            if bad:
                notes.append(
                    f"拒绝 stop.{item.get('order')}.{field}：未取证年份 {bad[:3]}"
                )
                continue
            stop[field] = val.strip() if val.strip() else stop.get(field)
    return notes


# ── 单卡润色（title / body / age_parallel + 该卡逐句溯源）──
def _chat_card(
    stop_order: int,
    card: dict[str, Any],
    facts: list[dict[str, Any]],
    meta_ctx: dict[str, Any],
    voice: VoicePack | None,
    allowed_years: set[str],
) -> tuple[dict[str, Any] | None, list[dict[str, Any]] | None, list[str]]:
    """单卡润色 + 该卡逐句溯源。返回 (card_patch_or_None, provenance_or_None, notes)。"""
    if not llm_configured():
        return None, None, [f"LLM 未配置，第 {stop_order} 站保留模板"]
    payload: dict[str, Any] = {
        "stop_order": stop_order,
        "draft_card": {
            "title": card.get("title"),
            "body": card.get("body"),
            "age_parallel": card.get("age_parallel"),
        },
        "fact_catalog": facts,
        # 整条线的风格上下文（元数据调用已产出），保证单卡读法与全本一致
        "meta": meta_ctx,
    }
    voice_block = voice.as_prompt_block() if voice else "（未抽签，保持克制润色）"
    # B7：向 LLM 暴露该站点的真实元数据（address/POI 类型/简介/landmark），
    # 强制基于这些信息写独特介绍——禁止套话模板（"未收录/借一段旧时光/诚实比完整重要"等）。
    # 元数据从 facts 提取（B6/B7 已把地址/类型/年份/风格/建筑设计师/沿革作为合成事实注入）。
    stop_meta: dict[str, Any] = {}
    for f in facts:
        rid = str(f.get("fact_uri") or "")
        label = str(f.get("label") or "")
        claim = str(f.get("claim") or "")
        if rid.startswith("amap:address:") or label == "地址":
            stop_meta["address"] = claim.removeprefix("地址：")
        elif rid.startswith("amap:type:") or label == "场所类型":
            stop_meta["poi_type"] = claim.removeprefix("高德分类：")
        elif rid.startswith("amap:category:") or label == "场所类别":
            stop_meta["category"] = claim.removeprefix("场所类别：")
        elif rid.startswith("curated.year:") or label == "建造年份":
            stop_meta["landmark_year_built"] = claim.split("始建：")[-1]
        elif rid.startswith("curated.style:") or label == "建筑风格":
            stop_meta["landmark_style"] = claim.split("风格：")[-1]
        elif rid.startswith("curated.architect:") or label == "建筑师":
            stop_meta["landmark_architect"] = claim.split("设计：")[-1]
        elif rid.startswith("curated.desc:") or label == "建筑沿革":
            stop_meta["landmark_description"] = claim
    # facts 里若有「curated.landmark-facts」数据集（人物），注入 stop_meta.characters
    chars = sorted(
        {f.get("label") for f in facts
         if f.get("source", {}).get("dataset") == "curated.landmark-facts"}
    )
    if chars:
        stop_meta["characters"] = [c for c in chars if c]
    # 站点名称（card.title 来自 draft_card）
    stop_meta["name"] = (card.get("title") or "").split("·")[-1].strip() or stop_meta.get("name", "")

    # ── 典籍新生 B：把人物结构化喂给 LLM，叙事主体从「楼」改成「人物/记载」 ──
    # 从 facts 抽出本站所有人物图层（person / classical），按「主角/对照/被遮蔽者」排序：
    # - 主角：名字出现在建筑名里的（如「巴金故居」的「巴金」），或典籍已验证溯源的人物
    # - 被遮蔽者：容易被忽略的人物（如丹麦人史宾伯、外国人毛特宝林海）——正是典籍新生要发掘的
    # - 对照：其他人物
    building_name = stop_meta.get("name", "")
    figures_struct: dict[str, Any] = {"protagonist": [], "contrast": [], "obscured": [], "classical": []}
    seen_names: set[str] = set()
    for f in facts:
        rid = str(f.get("fact_uri") or "")
        label = str(f.get("label") or "")
        claim = str(f.get("claim") or "")
        # 人物图层
        if rid.startswith("person:") or "开放数据将该建筑与人物" in claim:
            # 解析人物名：从「开放数据将该建筑与人物「XXX」建立关联」里抽
            import re as _re
            m = _re.search(r"人物「([^」]+)」", claim)
            name = m.group(1) if m else (label if label and len(label) <= 6 else "")
            if not name or name in seen_names:
                continue
            seen_names.add(name)
            entry = {"name": name, "claim": claim, "fact_uri": rid}
            # 主角：名字在建筑名里
            if name and name in building_name:
                figures_struct["protagonist"].append(entry)
            # 被遮蔽者：外国人名（含外文/译名特征）或非主角的非中文常见名
            elif _re.search(r"[A-Za-z]{4,}|[A-Z][a-z]+", name) or any(
                kw in name for kw in ("史宾伯", "毛特", "宝林", "鲍尔", "外国人", "丹麦", "英国", "俄国")
            ):
                figures_struct["obscured"].append(entry)
            else:
                figures_struct["contrast"].append(entry)
        # 典籍图层（CBDB 已验证）
        elif "classical" in rid or "cbdb" in rid.lower() or f.get("layer") == "classical":
            m = _re.search(r"典籍 · ([^：\s]+)", label) or _re.search(r"人物「?([^」]+)」?", label)
            name = m.group(1) if m else label
            if name and name not in seen_names:
                seen_names.add(name)
                figures_struct["classical"].append({
                    "name": name, "claim": claim, "fact_uri": rid, "verified": True,
                })
    stop_meta["figures"] = figures_struct

    # step④：本章在整本中的位置（卷→章→节递进），让单卡承接上一章、引出下一章
    arc = meta_ctx.get("narrative_arc") or {}
    arc_hint = ""
    main = arc.get("main_thread")
    total = int(arc.get("total_stops", 1) or 1)
    if main:
        pos = "开篇" if stop_order == 1 else ("收束" if stop_order == total else f"第 {stop_order}/{total} 章")
        arc_hint = (
            f"\n【本章位置】本文是整本的第 {stop_order}/{total} 章（{pos}）。"
            f"全本主线：{main['label']}（{main['type']}）。"
            "请让本卡的 title / body 承接上一章、引出下一章，使全本像一册被翻开的典籍："
            "人物与记载沿主线递进，避免各章各自为战；不要写「下一站是」式转场。"
        )

    user = (
        f"{voice_block}\n\n"
        "【典籍新生叙事指令】请基于下面 stop_metadata（含 figures 人物结构）与 "
        "fact_catalog，写该站点一张独特的叙事卡（title / body / age_parallel）。\n"
        "核心原则——叙事主体是人，不是楼：\n"
        "0) 这张卡的主角是「人」，不是「建筑」。建筑是人留下的舞台痕迹。"
        "开篇第一句必须落在一个具体的人名或一个具体年份的记载上，不要以建筑名开头，"
        "不要以「这里」「这栋」「走进」开头。\n"
        "1) 人物结构（stop_metadata.figures）已为你分好类：\n"
        "   - protagonist：名字写进建筑名里的主人公（如「巴金故居」的巴金）\n"
        "   - obscured：容易被忽略的人——外国人、照看房产的中间人、被遮蔽的关联者"
        "（如丹麦人史宾伯照看毛特宝林海的房产，再租给上海作协）。典籍新生要发掘的"
        "正是这类被遗忘者，请给他们至少一句具体记载。\n"
        "   - classical：从典籍（CBDB）中考据出的历史人物，已验证溯源，请点明其典籍出处。\n"
        "   - contrast：同时代/同事件里的对照人物，用于呈现张力。\n"
        "2) body 写成「一段人物在地点上的情节」：时间 + 人物 + 发生在此的事 + 出处。"
        "可以穿插多位人物（主角—被遮蔽者—对照），让一栋楼成为几代人命运的容器。"
        "禁止把建筑沿革/地址/场所类型堆成清单——这些信息只能化进人物的情节里。\n"
        "3) 禁止导游腔：绝对禁止出现以下字串（评审会逐字匹配并整篇判废）：\n"
        "   「你站在 / 你脚下 / 你忽然 / 你此刻 / 你离开 / 你遇见 / 你会先遇见 / "
        "你带走 / 你眼前 / 你带着」。\n"
        "   可用自然的「你」（如「你若在此驻足」「你抬头看」）。\n"
        "4) 禁止套话：绝对禁止出现以下字串：\n"
        "   「一键 / 省事 / 省时 / 省力 / 再也不用查攻略 / 伟大的革命 / 永垂不朽 / "
        "集合出发 / 打卡任务 / 带队前往 / 融汇中西 / 值得一提的是 / 仿佛穿越回老上海 / "
        "穿越回老上海 / 仿佛穿越 / 历史与现代在此交融 / 古今交融 / 仿佛时光倒流」。\n"
        "   每一句都必须落到本站某个可核实细节上。不得编造。\n"
        "5) 标题用「人物与『地名』」「人名：命题」等结构，禁止以纯地名或「在『地名』停一下」开头。\n"
        "6) age_parallel 仅在确实有跨时代对照时填写，否则置空。\n"
        "7) 同一 JSON 内逐句溯源（provenance 数组，每句一条，fact_uri 仅取自 fact_catalog）。"
        "只输出该站内容。\n"
        "8) 【风格范例】这是理想的开篇写法（仅供参考，勿照抄人名地名）：\n"
        "   「1955 年 9 月，巴金一家搬进武康路 113 号时，那扇门后还留着丹麦人史宾伯的钥匙。"
        "他曾在 1948 年接下这栋房子的照看之责，那时原房主英国人毛特宝林海已远走。」\n"
        "   注意：开篇是具体年份 + 具体人物 + 一个可核实的细节（钥匙），不是形容词堆砌。\n"
        + arc_hint
        + f"\nstop_metadata: {json.dumps(stop_meta, ensure_ascii=False)}\n"
        + json.dumps(payload, ensure_ascii=False)
        + "\n\n" + _CARD_SCHEMA
        + "\n\n" + _CARD_BODY_GUIDANCE
    )
    temperature = 0.55 if voice else 0.35
    try:
        patch = chat_json(
            system=_system_prompt(), user=user, temperature=temperature,
            backend="auto", role="creative",
            # 单卡篇幅上调到接近 1500 字（B8），放宽超时到 420s 以容纳更长生成；
            # 网关非流式、按总时长计时，需高于实际出字耗时。
            timeout=420,
        )
    except Exception as e:  # noqa: BLE001
        return None, None, [f"第 {stop_order} 站润色失败，保留模板：{e}"]
    if not isinstance(patch, dict):
        return None, None, [f"第 {stop_order} 站润色返回非对象，保留模板"]
    provenance = (
        patch.get("provenance")
        if isinstance(patch.get("provenance"), list)
        else None
    )
    card_patch = {k: patch.get(k) for k in ("title", "body", "age_parallel")}
    return card_patch, provenance, []


def _chat_weave(
    cards_snapshot: list[dict[str, Any]],
    meta_ctx: dict[str, Any],
    voice: VoicePack | None,
    allowed_years: set[str],
) -> tuple[dict[str, Any] | None, list[str]]:
    """全书编织（典籍新生 step③）：所有卡生成后，看全本回头给每张卡加呼应句。

    6 张卡是并行独立生成的，彼此不知道对方写了什么。本书要求「卷→章→节」的
    贯穿感：意象呼应、人物跨站回响、收束感。本函数把全本卡的 title + 开篇 +
    结尾摘要喂给 LLM，让它为每张卡产出「呼应句」（承接上一章或收束全书），
    追加到该卡 body 末尾。只加呼应不删改原文，不触碰 sources，不臆造事实。

    返回 (weave_patch_or_None, notes)。weave_patch 形如：
    {"stops": [{"order": 2, "echo_line": "一句承接/呼应的话"}]}
    """
    if not llm_configured():
        return None, ["全书编织跳过：LLM 未配置"]
    if len(cards_snapshot) < 2:
        return None, ["全书编织跳过：站点不足 2"]
    digest = []
    for c in sorted(cards_snapshot, key=lambda x: x.get("stop_order", 0)):
        body = str(c.get("body") or "")
        digest.append(
            {
                "order": c.get("stop_order"),
                "title": c.get("title"),
                "opening": body[:80],
                "ending": body[-60:] if body else "",
            }
        )
    payload = {
        "all_cards_digest": digest,
        "theme": meta_ctx.get("theme"),
        "logic_line": meta_ctx.get("logic_line"),
    }
    voice_block = voice.as_prompt_block() if voice else "（未抽签，保持克制润色）"
    schema = """JSON schema：
{
  "stops": [{"order": 2, "echo_line": "一句话，承接上一章或呼应全本主线的意象"}]
}
要求：
- 只为「确实能形成呼应」的站输出 echo_line（通常 2-4 站），不要每站都硬写。
- echo_line 必须基于 digest 里已有的内容（人物/事件/意象），不得引入新事实。
- echo_line 追加到该卡 body 末尾，作为自然收束句，不得出现「上一章」「下一站」字样。"""
    user = (
        f"{voice_block}\n\n"
        "以下是全本各章叙事卡的摘要（title / 开篇 / 结尾）。这是一本关于城市记忆的"
        "「典籍」：人物与记载沿一条线递进。请找出能形成跨章呼应的意象或人物"
        "（如一把钥匙的传递、一个被遗忘者的名字重现），为少数几站各写一句呼应句，"
        "让全本有「书」的贯穿感。\n"
        + json.dumps(payload, ensure_ascii=False)
        + "\n\n" + schema
    )
    try:
        patch = chat_json(
            system="你是一位懂文学的策展编辑，只输出 JSON。",
            user=user, temperature=0.5,
            backend="auto", role="creative",
            timeout=120,
        )
    except Exception as e:  # noqa: BLE001
        return None, [f"全书编织失败，跳过：{e}"]
    if not isinstance(patch, dict):
        return None, ["全书编织返回非对象，跳过"]
    # 校验年份（呼应句不得引入新年份）
    stops = patch.get("stops")
    if not isinstance(stops, list):
        return None, ["全书编织缺少 stops，跳过"]
    clean: list[dict[str, Any]] = []
    notes: list[str] = []
    for item in stops:
        if not isinstance(item, dict):
            continue
        line = str(item.get("echo_line") or "").strip()
        if not line:
            continue
        bad = _suspicious_new_years(line, allowed_years)
        if bad:
            notes.append(f"全书编织拒绝 stop{item.get('order')}：未取证年份 {bad[:3]}")
            continue
        clean.append({"order": item.get("order"), "echo_line": line})
    if not clean:
        return None, ["全书编织无有效呼应句"]
    return {"stops": clean}, notes


def _apply_weave(out: dict[str, Any], weave_patch: dict[str, Any]) -> list[str]:
    """把呼应句追加到对应卡 body 末尾。返回 notes。"""
    notes: list[str] = []
    stop_lines = {
        int(item.get("order") or 0): str(item.get("echo_line") or "").strip()
        for item in (weave_patch.get("stops") or [])
        if isinstance(item, dict)
    }
    for b in out.get("blocks") or []:
        if not isinstance(b, dict) or b.get("type") != "story_card":
            continue
        so = int(b.get("stop_order") or 0)
        line = stop_lines.get(so)
        if not line:
            continue
        body = str(b.get("body") or "")
        if not body:
            continue
        b["body"] = body.rstrip() + "\n" + line
        notes.append(f"全书编织: stop{so} 追加呼应句")
    return notes


def _chat_essay(
    stop_order: int,
    facts: list[dict[str, Any]],
    meta_ctx: dict[str, Any],
    voice: VoicePack | None,
    allowed_years: set[str],
) -> tuple[dict[str, Any] | None, list[dict[str, Any]] | None, list[str]]:
    """单站长散文（路线零件）生成 + 逐句溯源。返回 (essay_patch_or_None, provenance_or_None, notes)。"""
    if not llm_configured():
        return None, None, [f"LLM 未配置，第 {stop_order} 站长散文保留空"]
    payload: dict[str, Any] = {
        "stop_order": stop_order,
        "fact_catalog": facts,  # 每条带 grade 字段（A/B/C/D/E）
        "meta": meta_ctx,
    }
    voice_block = voice.as_prompt_block() if voice else "（未抽签，保持克制润色）"
    user = (
        f"{voice_block}\n\n"
        "请基于下面 fact_catalog（每条含 grade 置信度）写该站点一篇「路线零件」长散文"
        "（title / body / provenance）。\n"
        "硬性规则：\n"
        "0) 从现场具体细节进入，不写百科开头；A–F 六段是节奏不是表单，禁止写成 ## 标题或"
        "A./B./C. 编号或「从现场进入：」这类可见标签；全文同一种连续声音。\n"
        "1) 事实按 grade 措辞：A/B 级作确定陈述；C 级带轻度归属（「据地图标注」「高德分类为」）；"
        "fact_catalog 之外只能以「待核查 / 地方传闻 / 研究假设」写成开放问题，严禁当确定事实。\n"
        "2) 同行者口吻：可用自然「你」（你若在此驻足 / 你抬头看），但严禁导游腔命令式"
        "（你站在 / 你脚下 / 你忽然 / 你此刻 / 你离开）。\n"
        "3) 人物以关系而非传奇进入；保留被遮蔽者、不确定与争议；最后自然转场（禁「下一站是」）。\n"
        "4) 同一 JSON 内逐句溯源（provenance 数组，每句一条，带 grades）。只输出该站内容。\n"
        + json.dumps(payload, ensure_ascii=False)
        + "\n\n" + _ESSAY_SCHEMA
        + "\n\n" + _ESSAY_BODY_GUIDANCE
    )
    temperature = 0.6 if voice else 0.4
    try:
        patch = chat_json(
            system=_essay_system_prompt(), user=user, temperature=temperature,
            backend="auto", role="creative",
            # 长散文目标 ~10000 字：端点默认输出上限（~4096 token）会被拦腰截断，
            # 故显式拉高 max_tokens 到 _ESSAY_MAX_TOKENS（默认 16000，可经 env 覆盖）。
            max_tokens=_ESSAY_MAX_TOKENS,
            timeout=900,
        )
    except Exception as e:  # noqa: BLE001
        return None, None, [f"第 {stop_order} 站长散文生成失败，保留空：{e}"]
    if not isinstance(patch, dict):
        return None, None, [f"第 {stop_order} 站长散文返回非对象，保留空"]
    provenance = (
        patch.get("provenance")
        if isinstance(patch.get("provenance"), list)
        else None
    )
    essay_patch = {
        k: patch.get(k)
        for k in ("title", "body")
        if isinstance(patch.get(k), str) and patch.get(k).strip()
    }
    return essay_patch, provenance, []


def _apply_card(
    out: dict[str, Any], stop_order: int, card_patch: dict[str, Any],
    allowed_years: set[str],
) -> list[str]:
    """merge 单卡字段进 blocks 的对应 story_card（sources 永不触碰）。"""
    notes: list[str] = []
    for b in out.get("blocks") or []:
        if (
            not isinstance(b, dict)
            or b.get("type") != "story_card"
            or b.get("stop_order") != stop_order
        ):
            continue
        for field in ("title", "body", "age_parallel"):
            val = card_patch.get(field)
            if val is None:
                continue
            if field == "age_parallel" and val == "":
                continue
            if not isinstance(val, str):
                continue
            bad = _suspicious_new_years(val, allowed_years)
            if bad:
                notes.append(f"拒绝 story.{stop_order}.{field}：未取证年份 {bad[:3]}")
                continue
            if val.strip():
                b[field] = val.strip()
        break
    return notes


def polish_envelope(
    draft: dict[str, Any],
    voice: VoicePack | None = None,
    plan: RoutePlan | None = None,
    on_chapter: Callable[[dict[str, Any]], None] | None = None,
) -> tuple[dict[str, Any] | None, list[str], SentenceProvenanceReport | None]:
    """
    Returns (polished_envelope_or_None, notes, sentence_provenance_or_None).
    None means caller should keep draft.

    B4：拆为「元数据 + 逐卡并行」；每卡完成若 on_chapter 提供则立即回调
    {"stop_order": int, "card": {title, body, age_parallel}, "provenance": [...]}，
    供 SSE chapter_ready 做边生成边读。整本聚合结果仍作为返回值（Gate 在 pipeline 内跑）。
    """
    if not llm_configured():
        return None, ["LLM 未配置，使用模板叙事"], None
    if plan is None:
        return None, ["未提供 plan，跳过润色"], None
    facts = _fact_catalog(plan)
    # B6 移除 facts<3 硬阻断——amap-only 站点（无 layers）会因空目录
    # 整本回退模板。改用 _fact_catalog_by_stop 为 amap 点补地址/类型/沿革
    # 作合成事实（见该函数），LLM 至少有依据可写。
    _ = facts  # 保留总览统计，但不再据此早退

    allowed_years = {
        y for y in _extract_tokens([f.get("claim") or "" for f in facts]) if y.isdigit()
    }
    # 补充 landmark 词库建造年份（raw_detail.landmark_year_built）——
    # 否则 LLM 引用真实年份（1906/1923…）会被 _apply_card 误拒为「未取证年份」。
    for s in plan.stops:
        rd = s.evidence.raw_detail or {}
        y = str(rd.get("landmark_year_built") or "")
        for token in re.findall(r"\d{4}", y):
            allowed_years.add(token)
    out = copy.deepcopy(draft)
    notes: list[str] = []

    # 1) 元数据（含逐站衔接）先出，作为卡片调用的风格上下文
    meta_patch, meta_notes = _chat_meta(draft, voice, plan, allowed_years)
    notes.extend(meta_notes)
    meta_ctx: dict[str, Any] = {}
    if meta_patch:
        notes.extend(_apply_meta(out, meta_patch, allowed_years))
        meta_ctx = {
            "theme": out.get("theme"),
            "logic_line": out.get("logic_line"),
            "why_visit": out.get("why_visit"),
            "curator_note": out.get("curator_note"),
        }
        # step④：把贯穿主线随风格上下文一起传给逐卡，使单卡知道自己在整本中的章位置
        meta_ctx["narrative_arc"] = detect_arc(plan)

    # 2) 逐卡并行 + 完成即回调
    facts_by_stop = _fact_catalog_by_stop(plan)
    cards = [
        (b.get("stop_order"), b)
        for b in out.get("blocks") or []
        if isinstance(b, dict) and b.get("type") == "story_card"
    ]
    if not cards:
        return out, notes, None

    prov_parts: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=min(4, len(cards))) as pool:
        futs = {
            pool.submit(
                _chat_card, so, card, facts_by_stop.get(so, []),
                meta_ctx, voice, allowed_years,
            ): so
            for so, card in cards
        }
        for fut in as_completed(futs):
            so = futs[fut]
            card_patch, provenance, card_notes = fut.result()
            notes.extend(card_notes)
            if card_patch is not None:
                notes.extend(_apply_card(out, so, card_patch, allowed_years))
                if provenance is not None:
                    prov_parts.append({"stop_order": so, "sentences": provenance})
            if on_chapter is not None and card_patch is not None:
                on_chapter(
                    {
                        "stop_order": so,
                        "card": {
                            k: card_patch.get(k)
                            for k in ("title", "body", "age_parallel")
                        },
                        "provenance": provenance,
                    }
                )

    # 3) 溯源汇总（复用整本版构建器；聚合 patch 仅含逐卡 story_provenance）
    sp: SentenceProvenanceReport | None = None
    if prov_parts:
        try:
            sp = _build_sp_report_from_polish(
                {"story_provenance": prov_parts}, plan, draft
            )
        except Exception:  # noqa: BLE001
            sp = None

    # 3.5) 全书编织（典籍新生 step③）：所有卡生成后看全本回头加呼应句
    # 让「卷→章→节」有贯穿感：意象呼应、人物跨站回响。失败仅跳过，不阻断。
    if os.getenv("REDTRIP_WEAVE", "1") != "0":
        cards_snapshot = [
            {"stop_order": b.get("stop_order"), "title": b.get("title"), "body": b.get("body")}
            for b in out.get("blocks") or []
            if isinstance(b, dict) and b.get("type") == "story_card"
            and b.get("body")
        ]
        weave_patch, weave_notes = _chat_weave(
            cards_snapshot, meta_ctx, voice, allowed_years,
        )
        notes.extend(weave_notes)
        if weave_patch:
            notes.extend(_apply_weave(out, weave_patch))

    # 4) 逐站长散文「路线零件」并行生成（与卡片同 fact_catalog，独立成 block）
    # 典籍新生优化：essay 长散文前端不消费、只进导出的书（book.py 渲染），
    # 却占一次策展 ~60-90s 与 81% 的 token。默认关闭（REDTRIP_ESSAY=0），
    # 阅读场景只生成 card（时间减半）；导出「书」要长文时再开 REDTRIP_ESSAY=1。
    essay_blocks: list[dict[str, Any]] = []
    if os.getenv("REDTRIP_ESSAY", "0") != "0":
        essay_futs = {}
        with ThreadPoolExecutor(max_workers=min(4, len(cards))) as pool:
            for so, _card in cards:
                essay_futs[pool.submit(
                    _chat_essay, so, facts_by_stop.get(so, []),
                    meta_ctx, voice, allowed_years,
                )] = so
            for fut in as_completed(essay_futs):
                so = essay_futs[fut]
                essay_patch, essay_prov, essay_notes = fut.result()
                notes.extend(essay_notes)
                if essay_patch:
                    essay_blocks.append(
                        {
                            "type": "essay",
                            "stop_order": so,
                            "title": essay_patch.get("title", ""),
                            "body": essay_patch.get("body", ""),
                            "provenance": essay_prov,
                        }
                    )
    if essay_blocks:
        out.setdefault("blocks", []).extend(essay_blocks)
        notes.append(f"已生成 {len(essay_blocks)} 篇路线零件长散文（待 Gate）")

    prefix = "红鸢润色已应用（待 Gate）" if voice else "LLM 润色已应用（待 Gate）"
    notes = [prefix, *notes]
    return out, notes, sp
