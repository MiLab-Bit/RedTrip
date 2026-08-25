from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Literal

from redtrip_library import SlcClient

from .artifacts import CurationArtifacts, build_artifacts
from .evidence import fetch_evidence
from .hongyuan import VoicePack, attach_layer3, draw_voice_pack
from .intent import parse_intent
from .join import join_layers
from .llm import llm_configured
from .narrative import narrate
from .plan import RoutePlan, plan_route
from .polish import polish_envelope
from .review import review_envelope
from .sentence_provenance import SentenceProvenanceReport

# Ensure gate package importable when running from API / scripts
_GATE = Path(__file__).resolve().parents[2] / "gate"
if str(_GATE) not in sys.path:
    sys.path.insert(0, str(_GATE))

from redtrip_gate import evaluate_envelope  # noqa: E402
from redtrip_gate.engine import (  # noqa: E402
    FORBIDDEN_COPY,
    _ESSAY_YOU_FAMILY,
    _ESSAY_STRUCTURE_BAN,
)


def _scrub_forbidden(envelope: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """局部清洗：把含禁用词的句子从润色后的卡片/长散文里删掉，而不是整本回退。

    典籍新生修复：Gate 规则合理（禁导游腔、禁套话），但「一两个禁用词判废整本」
    太严苛——会让一次成功的润色（6 卡 + 6 essay，几十秒 LLM 调用）全部白费。
    本函数在 Gate 判废后跑：逐句扫描 story_card.body / essay.body，
    删掉含禁用词的句子（保留其他干净的），让大部分润色成果得以保留。

    返回 (清洗后的 envelope, 清洗记录)。清洗记录形如：
      "Q8-局部清洗: story_card#2 删 N 句含「你站在」"
    """
    import re as _re

    notes: list[str] = []

    def _split_sentences(text: str) -> list[str]:
        # 简单句切：按中文句号/问号/感叹号 + 换行
        parts = _re.split(r"(?<=[。！？\n])", text)
        return [p for p in parts if p.strip()]

    def _join_sentences(sents: list[str]) -> str:
        return "".join(sents)

    # story_card：禁 FORBIDDEN_COPY 全集
    for b in envelope.get("blocks") or []:
        if not isinstance(b, dict):
            continue
        if b.get("type") == "story_card":
            body = str(b.get("body") or "")
            if not body:
                continue
            sents = _split_sentences(body)
            kept: list[str] = []
            removed: list[str] = []
            for s in sents:
                if any(bad in s for bad in FORBIDDEN_COPY):
                    removed.append(s)
                else:
                    kept.append(s)
            if removed:
                so = b.get("stop_order")
                bads = sorted({_b for s in removed for _b in FORBIDDEN_COPY if _b in s})
                notes.append(
                    f"Q8-局部清洗: story_card#{so} 删除 {len(removed)} 句含「{'、'.join(bads[:3])}」"
                )
                # 同步清洗 provenance 里对应的句子（若有）
                prov = b.get("provenance")
                if isinstance(prov, list):
                    removed_texts = {s.strip() for s in removed}
                    b["provenance"] = [
                        p for p in prov
                        if not (isinstance(p, dict) and str(p.get("text", "")).strip() in removed_texts)
                    ]
                b["body"] = _join_sentences(kept) if kept else body  # 兜底：全删则保留原

        elif b.get("type") == "essay":
            body = str(b.get("body") or "")
            if not body:
                continue
            sents = _split_sentences(body)
            kept = []
            removed = []
            # essay 禁用集：FORBIDDEN_COPY 去掉 you-family（允许同行者口吻）
            # + structure ban（禁结构标签）
            essay_forbidden = (
                set(FORBIDDEN_COPY) - set(_ESSAY_YOU_FAMILY)
            ) | set(_ESSAY_STRUCTURE_BAN) | set(_ESSAY_YOU_FAMILY)
            for s in sents:
                if any(bad in s for bad in essay_forbidden):
                    removed.append(s)
                else:
                    kept.append(s)
            if removed:
                so = b.get("stop_order")
                bads = sorted({_b for s in removed for _b in essay_forbidden if _b in s})
                notes.append(
                    f"Q8-局部清洗: essay#{so} 删除 {len(removed)} 句含「{'、'.join(bads[:3])}」"
                )
                prov = b.get("provenance")
                if isinstance(prov, list):
                    removed_texts = {s.strip() for s in removed}
                    b["provenance"] = [
                        p for p in prov
                        if not (isinstance(p, dict) and str(p.get("text", "")).strip() in removed_texts)
                    ]
                b["body"] = _join_sentences(kept) if kept else body

    # 元数据字段（theme/logic_line/why_visit/curator_note/meaning/transition）也清洗
    def _scrub_str(s: str) -> str:
        if not isinstance(s, str):
            return s
        for bad in FORBIDDEN_COPY:
            if bad in s:
                s = s.replace(bad, "")
        return s

    for k in ("theme", "logic_line", "why_visit", "curator_note"):
        if k in envelope:
            old = envelope[k]
            new = _scrub_str(old)
            if new != old:
                envelope[k] = new
                notes.append(f"Q8-局部清洗: 字段 {k} 清洗禁用词")
    for stop in (envelope.get("route") or {}).get("stops") or []:
        if not isinstance(stop, dict):
            continue
        for f in ("meaning", "transition_to_next"):
            old = stop.get(f)
            new = _scrub_str(old) if old else old
            if new and new != old:
                stop[f] = new
                notes.append(f"Q8-局部清洗: stop.{stop.get('order')}.{f} 清洗禁用词")

    return envelope, notes


@dataclass
class CurateResult:
    ok: bool
    envelope: dict[str, Any] | None
    assumptions: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    mode: str = "indexed"
    evidence_count: int = 0
    narrative: Literal["template", "llm_polish"] = "template"
    hongyuan: dict[str, Any] | None = None
    artifacts: CurationArtifacts | None = None


def _finalize_narrative(
    draft: dict[str, Any],
    voice: VoicePack | None,
    plan: RoutePlan | None = None,
    on_chapter: Callable[[dict[str, Any]], None] | None = None,
) -> tuple[dict[str, Any], list[str], Literal["template", "llm_polish"], SentenceProvenanceReport | None]:
    """Polish on evidence-bound draft; Gate must pass or fall back.
    句子级溯源与润色合并为同一次 LLM 调用（B3），随叙事结果一并返回。
    B4：内部按「元数据 + 逐卡并行」拆章，每卡完成经 on_chapter 回调（流式交付）。
    """
    notes: list[str] = []
    if not llm_configured():
        return draft, ["叙事：模板（未配置 LLM）"], "template", None

    polished, polish_notes, sp = polish_envelope(
        draft, voice=voice, plan=plan, on_chapter=on_chapter
    )
    notes.extend(polish_notes)
    if not polished:
        return draft, notes, "template", None

    verdict = evaluate_envelope(polished)
    if verdict.passed:
        notes.append("叙事：红鸢润色已过 Gate" if voice else "叙事：LLM 润色已过 Gate")
        notes.extend(verdict.warnings)
        # 反方策展人：单视角对抗性评审（非阻断，仅告警）。
        # 默认开启；可用 REDTRIP_OPPOSING_CURATOR=0 关闭（省一次 LLM 调用）。
        if os.getenv("REDTRIP_OPPOSING_CURATOR", "1") != "0":
            try:
                review = review_envelope(polished, plan=plan, voice=voice)
                if review:
                    polished["curator_review"] = review
                    r_warn = review.get("warnings") or []
                    notes.extend(r_warn)
                    if r_warn:
                        notes.append(
                            f"反方策展人提出 {len(r_warn)} 条评审意见（非阻断，供复核）"
                        )
            except Exception as e:  # noqa: BLE001
                notes.append(f"反方策展人评审跳过：{e}")
        return polished, notes, "llm_polish", sp

    # ── 典籍新生修复：Gate 判废时先局部清洗，不直接整本回退 ──
    # 大部分 Gate blocker 是 Q8（禁用词）：几篇文章里出现「你站在」「时间叠层」
    # 等少数词。原逻辑会把这些词判废整本，让一次成功的润色（6 卡 + 6 essay，
    # 数十秒 LLM 调用）全部白费，回退到模板骨架。
    # 新逻辑：先清洗掉含禁用词的句子，重新评估；只有清洗后仍不过（说明有
    # 更严重的问题，如 G4 溯源失败）才回退模板。
    q8_only = all("Q8" in blk for blk in verdict.blockers)
    if q8_only and verdict.blockers:
        scrubbed, scrub_notes = _scrub_forbidden(polished)
        if scrub_notes:
            notes.extend(scrub_notes)
            verdict2 = evaluate_envelope(scrubbed)
            if verdict2.passed:
                notes.append(
                    "叙事：LLM 润色经局部清洗后通过 Gate（保留大部分润色成果）"
                )
                notes.extend(verdict2.warnings)
                if os.getenv("REDTRIP_OPPOSING_CURATOR", "1") != "0":
                    try:
                        review = review_envelope(scrubbed, plan=plan, voice=voice)
                        if review:
                            scrubbed["curator_review"] = review
                            r_warn = review.get("warnings") or []
                            notes.extend(r_warn)
                            if r_warn:
                                notes.append(
                                    f"反方策展人提出 {len(r_warn)} 条评审意见（非阻断，供复核）"
                                )
                    except Exception as e:  # noqa: BLE001
                        notes.append(f"反方策展人评审跳过：{e}")
                return scrubbed, notes, "llm_polish", sp
            else:
                notes.append(
                    "叙事：LLM 润色经局部清洗后仍未过 Gate（"
                    + "；".join(verdict2.blockers[:3])
                    + "），回退模板"
                )
        else:
            notes.append("叙事：Gate blocker 非 Q8 类，无法清洗，回退模板")

    notes.append(
        "叙事：LLM 润色未过 Gate，已回退模板 — "
        + "；".join(verdict.blockers[:3])
    )
    return draft, notes, "template", None


def curate(
    *,
    slots: dict[str, Any] | None = None,
    message: str | None = None,
    client: SlcClient | None = None,
    retry_count: int = 0,
    hongyuan_seed: int | None = None,
    on_progress: "Callable[[str, float, str], None] | None" = None,
    on_event: "Callable[[str, dict], None] | None" = None,
) -> CurateResult:
    def _emit(stage: str, progress: float, message: str = "") -> None:
        if on_progress is not None:
            on_progress(stage, progress, message)

    client = client or SlcClient()
    _emit("init", 2.0, "已接收策展请求")
    intent = parse_intent(slots, message)
    _emit("intent", 6.0, "已解析出行意图")
    # 取证候选数随时长放宽（4h→20、8h→28、24h→36），保证长程路线不缺素材
    _dur = intent.duration_min or 90
    _limit = max(
        12,
        int(os.getenv("REDTRIP_EVIDENCE_LIMIT", "12")),
        20 if _dur <= 240 else 28 if _dur <= 480 else 36,
    )
    pack = fetch_evidence(client, intent, limit=_limit)
    # SLC 调用完成 → 20%（用户指定：SLC 好即 20%）
    _emit("evidence", 20.0, f"SLC 取证完成（{len(pack.buildings)} 处建筑）")
    pack = join_layers(pack)
    _emit("join", 24.0, "图层融合完成")

    # L2 lexicon lottery (rules unchanged)
    voice = draw_voice_pack(
        tone=intent.tone,
        companions=intent.companions,
        duration_min=intent.duration_min,
        seed=hongyuan_seed,
    )
    _emit("voice", 28.0, "红鸢词库抽选完成")

    if len(pack.buildings) < 3:
        # L3 with scene-only places when route unavailable
        voice = attach_layer3(
            voice, places=[intent.scene], tone=intent.tone
        )
        assumptions = _assumptions_with_voice(intent.assumptions, voice)
        _emit("failed", 100.0, "取证候选不足（<3），无法策展")
        return CurateResult(
            ok=False,
            envelope=None,
            assumptions=assumptions,
            reasons=["取证候选不足（<3），无法策展"],
            warnings=[g.get("note", "") for g in pack.gaps],
            mode="indexed",
            evidence_count=len(pack.buildings),
            narrative="template",
            hongyuan=voice.as_dict(),
        )

    try:
        plan = plan_route(intent, pack)
        _emit("route", 34.0, "路线规划完成")
    except ValueError as e:
        voice = attach_layer3(
            voice, places=[intent.scene], tone=intent.tone
        )
        assumptions = _assumptions_with_voice(intent.assumptions, voice)
        _emit("failed", 100.0, f"路线规划失败：{e}")
        return CurateResult(
            ok=False,
            envelope=None,
            assumptions=assumptions,
            reasons=[str(e)],
            mode="indexed",
            evidence_count=len(pack.buildings),
            narrative="template",
            hongyuan=voice.as_dict(),
        )

    # L3 hotword RAG — place-scoped after stops known
    place_hints = [intent.scene, *[s.evidence.name for s in plan.stops]]
    voice = attach_layer3(voice, places=place_hints, tone=intent.tone)
    assumptions = _assumptions_with_voice(intent.assumptions, voice)
    hongyuan_meta = voice.as_dict()
    _emit("layer3", 38.0, "L3 热词注入完成")

    draft = narrate(intent, plan, pack.sources_used)
    # 第一次模型调用完成（命题 + 叙事初稿）→ 50%
    _emit("narrate", 50.0, "命题与叙事初稿完成")

    # B4：先落中间产物（build_artifacts 纯本地计算），把「模板 envelope」立即
    # 交付（story_ready）——前端先进序章、模板章节即可读；随后 LLM 逐卡润色并行，
    # 每完成一张推 chapter_ready（on_chapter → on_event），前端增量替换为润色版。
    # 等待感从「整本 160s」降到「首章 ~50s、之后每 ~20-30s 多一章」。
    artifacts = build_artifacts(intent, plan, pack)
    artifacts.embed(draft)  # 模板版 envelope（含 curated_story 模板章节）
    if on_event is not None:
        on_event(
            "story_ready",
            {
                "envelope": draft,
                "assumptions": assumptions,
                "hongyuan": hongyuan_meta,
            },
        )

    # B5 进度：第二次模型调用（逐卡润色）期间按完成卡数推进 52 → 90，
    # 让进度条真实反映 LLM 工作量，而不是在 narrate 后空转到 done。
    _total_cards = sum(
        1 for b in (draft.get("blocks") or []) if b.get("type") == "story_card"
    ) or 1
    _cards_done = 0

    def _on_chapter(payload: dict) -> None:
        nonlocal _cards_done
        _cards_done += 1
        frac = min(1.0, _cards_done / _total_cards)
        _emit(
            "polish",
            52.0 + 38.0 * frac,
            f"章节润色进行中（{_cards_done}/{_total_cards}）",
        )
        if on_event is not None:
            on_event("chapter_ready", payload)

    envelope, narrative_notes, narrative_mode, sp = _finalize_narrative(
        draft, voice, plan, on_chapter=_on_chapter
    )

    if sp is not None:
        artifacts.sentence_provenance = sp
    artifacts.embed(envelope)
    _emit("artifacts", 95.0, "中间产物生成完成")

    verdict = evaluate_envelope(envelope)
    _emit("done", 100.0, "策展完成")

    if not verdict.passed:
        # D：顶层 Gate 未通过 → 不再递归重跑全流水线（避免 48 次 SLC + 全部 LLM
        # 的 2x 翻倍），改为回退到基于证据的模板叙事（draft）。仍返回 ok=True 的
        # 可用策展结果，并把 Gate 阻断项作为告警透出，避免空白/静态兜底。
        fb_notes = [
            "顶层 Gate 未通过，已回退模板叙事（不再重跑流水线）",
            *verdict.blockers[:3],
        ]
        artifacts.embed(draft)
        return CurateResult(
            ok=True,
            envelope=draft,
            assumptions=assumptions,
            reasons=[],
            warnings=[*narrative_notes, *fb_notes, *verdict.warnings],
            mode="indexed",
            evidence_count=len(pack.buildings),
            narrative="template",
            hongyuan=hongyuan_meta,
            artifacts=artifacts,
        )

    return CurateResult(
        ok=True,
        envelope=envelope,
        assumptions=assumptions,
        reasons=[],
        warnings=[*narrative_notes, *verdict.warnings],
        mode="indexed",
        evidence_count=len(pack.buildings),
        narrative=narrative_mode,
        hongyuan=hongyuan_meta,
        artifacts=artifacts,
    )


def _assumptions_with_voice(
    base: list[str], voice: VoicePack
) -> list[str]:
    out = [*base, voice.summary_line()]
    l3 = voice.layer3_line()
    if l3:
        out.append(l3)
    return out
