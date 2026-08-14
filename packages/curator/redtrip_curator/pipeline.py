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
