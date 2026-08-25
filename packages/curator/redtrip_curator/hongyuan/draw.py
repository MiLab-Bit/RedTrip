"""红鸢抽签：在用户时长/调性/同行约束下抽取读法组合（L2）。

L3 周热词通过 attach_layer3() 叠加上，不改变 L2 规则。
"""
from __future__ import annotations

import random
from dataclasses import asdict, dataclass, replace
from typing import Any

from .layer3_hotwords import (
    HotwordHit,
    hotwords_prompt_block,
    hotwords_summary_line,
    retrieve_hotwords,
)
from .lexicon import LEXICON, Entry, lexicon_stats

AGENT_NAME = "红鸢"


@dataclass(frozen=True)
class DrawnSlot:
    category: str
    id: str
    label: str
    hint: str


@dataclass(frozen=True)
class VoicePack:
    agent: str
    seed: int
    emotion: DrawnSlot
    voice_style: DrawnSlot
    narrative: DrawnSlot
    knowledge_angle: DrawnSlot
    pacing: DrawnSlot
    # L3
    layer3_week: str | None = None
    layer3: tuple[HotwordHit, ...] = ()

    def summary_line(self) -> str:
        return (
            f"{self.agent}今日读法："
            f"{self.emotion.label} · {self.voice_style.label} · "
            f"{self.narrative.label} · {self.knowledge_angle.label} · {self.pacing.label}"
        )

    def layer3_line(self) -> str | None:
        if not self.layer3:
            return None
        return hotwords_summary_line(self.layer3_week or "?", list(self.layer3))

    def as_prompt_block(self) -> str:
        lines = [
            f"你正在以「{self.agent}」的身份润色（读法可变，史实不可变）。",
            f"本次抽签 seed={self.seed}。",
            "【第二层 · 红鸢词库抽签】",
            f"- 情绪：{self.emotion.label}（{self.emotion.hint}）",
            f"- 说话风格：{self.voice_style.label}（{self.voice_style.hint}）",
            f"- 叙事方式：{self.narrative.label}（{self.narrative.hint}）",
            f"- 知识延伸角度：{self.knowledge_angle.label}（{self.knowledge_angle.hint}）",
            f"- 节奏：{self.pacing.label}（{self.pacing.hint}）",
            "延伸角度只影响读法与提问，禁止当作新史实写入正文。",
            "",
            hotwords_prompt_block(self.layer3_week or "?", list(self.layer3)),
        ]
        return "\n".join(lines)

    def as_dict(self) -> dict[str, Any]:
        return {
            "agent": self.agent,
            "seed": self.seed,
            "summary": self.summary_line(),
            "emotion": asdict(self.emotion),
            "voice_style": asdict(self.voice_style),
            "narrative": asdict(self.narrative),
            "knowledge_angle": asdict(self.knowledge_angle),
            "pacing": asdict(self.pacing),
            "lexicon_size": lexicon_stats(),
            "layer3_week": self.layer3_week,
            "layer3_summary": self.layer3_line(),
            "layer3": [h.as_dict() for h in self.layer3],
            "rag_layers": ["evidence", "lexicon", "hotwords"],
        }


def _norm_tone(tone: str | None) -> str:
    t = (tone or "轻社交").strip()
    for key in ("硬核", "文艺", "轻社交"):
        if key in t:
            return key
    return "轻社交"


def _norm_companions(companions: str | None) -> str:
    c = (companions or "2人").strip()
    if "独" in c:
        return "独自"
    if "3" in c or "4" in c:
        return "3–4人"
    return "2人"


def _norm_duration(duration_min: int | None) -> str:
    d = int(duration_min or 90)
    if d <= 40:
        return "30"
    if d <= 75:
        return "60"
    return "90"


def _matches(entry: Entry, tone: str, companions: str, duration: str) -> bool:
    tones = entry.get("tone_tags") or []
    comps = entry.get("companion_tags") or []
    durs = entry.get("duration_tags") or []
    if tones and tone not in tones:
        return False
    if comps and companions not in comps:
        return False
    if durs and duration not in durs:
        return False
    return True


def _pick(
    rng: random.Random,
    category: str,
    tone: str,
    companions: str,
    duration: str,
) -> DrawnSlot:
    pool = [
        e
        for e in LEXICON[category]
        if _matches(e, tone, companions, duration)
    ]
    if not pool:
        pool = list(LEXICON[category])
    tagged = [
        e
        for e in pool
        if e.get("tone_tags") or e.get("companion_tags") or e.get("duration_tags")
    ]
    if tagged and rng.random() < 0.65:
        pool = tagged
    e = rng.choice(pool)
    return DrawnSlot(
        category=category,
        id=e["id"],
        label=e["label"],
        hint=e["hint"],
    )


def draw_voice_pack(
    *,
    tone: str | None,
    companions: str | None,
    duration_min: int | None,
    seed: int | None = None,
) -> VoicePack:
    """L2 only — rules unchanged. Call attach_layer3 for L3."""
    seed = int(seed if seed is not None else random.SystemRandom().randint(1, 2**31 - 1))
    rng = random.Random(seed)
    t = _norm_tone(tone)
    c = _norm_companions(companions)
    d = _norm_duration(duration_min)
    return VoicePack(
        agent=AGENT_NAME,
        seed=seed,
        emotion=_pick(rng, "emotion", t, c, d),
        voice_style=_pick(rng, "voice_style", t, c, d),
        narrative=_pick(rng, "narrative", t, c, d),
        knowledge_angle=_pick(rng, "knowledge_angle", t, c, d),
        pacing=_pick(rng, "pacing", t, c, d),
    )


def attach_layer3(
    voice: VoicePack,
    *,
    places: list[str] | None,
    tone: str | None = None,
    top_k: int = 4,
) -> VoicePack:
    """L3 Agentic RAG: retrieve weekly Shanghai hotwords by place."""
    week, hits = retrieve_hotwords(
        places=places,
        tone=tone,
        top_k=top_k,
        seed=voice.seed ^ 0xC0FFEE,
    )
    return replace(voice, layer3_week=week, layer3=tuple(hits))
