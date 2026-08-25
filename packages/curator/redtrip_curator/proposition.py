"""G1 命题分解：propose（生成）+ critique（独立批判）两步分离。

输入：Intent（含用户原始留言）+ RoutePlan + EvidencePack（已取证证据）。
输出：PropositionSet（title / open_question / scope_note / propositions[]）。

命题维度映射到 EvidenceGraph 的 cluster id（cl-{dimension}），从而
G2-1 Theme 的 research_axes 与 G2-2 证据图天然对齐。

两步分离（消除「生成者自我辩护」偏差）：
  1) propose：一次调用生成 2–4 条命题假设（云端，不自我批判）。
  2) critique：一次独立调用逐条批判，判 verdict + rewritten（云端）。
  3) 启发式兜底 _heuristic_over_extended：捕捉 critique 漏判 / 未配 LLM。

降级策略：
  - propose 失败 / 未配置 → 返回 None，由 build_artifacts 回退规则逻辑。
  - critique 失败 → 全部命题 allowed，启发式兜底接管（不阻断流程）。
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from .llm import chat_json, llm_configured
from .models import EvidencePack, Intent, RoutePlan

_DIMENSIONS = ("person", "event", "building", "era", "poem", "theme")
_YEAR = re.compile(r"(?:18|19|20)\d{2}")


@dataclass
class Proposition:
    axis: str
    hypothesis: str
    dimension: str  # person/event/building/era/poem/theme
    question: str
    # 红队字段：默认 allowed；被收敛为中性框架 → rewritten；证据完全无法支撑 → dropped
    status: str = "allowed"  # allowed | rewritten | dropped
    flag_reason: str = ""


@dataclass
class PropositionSet:
    title: str
    open_question: str
    scope_note: str
    propositions: list[Proposition] = field(default_factory=list)
    redteam_applied: bool = False
    redteam_notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "open_question": self.open_question,
            "scope_note": self.scope_note,
            "redteam_applied": self.redteam_applied,
            "redteam_notes": self.redteam_notes,
            "propositions": [
                {
                    "axis": p.axis,
                    "hypothesis": p.hypothesis,
                    "dimension": p.dimension,
                    "question": p.question,
                    "status": p.status,
                    "flag_reason": p.flag_reason,
                }
                for p in self.propositions
            ],
        }


def _evidence_summary(plan: RoutePlan, pack: EvidencePack, limit_chars: int = 1500) -> tuple[str, list[str]]:
    """构造给 LLM 的证据摘要 + 实际出现的维度列表。"""
    lines: list[str] = []
    kinds: set[str] = set()
    for s in plan.stops:
        be = s.evidence
        lines.append(f"- 点位：{be.name}（buri={be.buri or '无'}）")
        for l in be.layers:
            kinds.add(l.kind)
            claim = (l.claim or "")[:90]
            lines.append(f"    · [{l.kind}] {l.label}：{claim}")
    summary = "\n".join(lines)[:limit_chars]
    return summary, sorted(kinds)


_PROPOSE_SYSTEM = (
    "你是城市文化策展的研究命题拆解器。给定用户的行走意图与已取证史实，"
    "把模糊意图拆成 2–4 个可研究命题（研究轴）。"
    "每个命题必须可证伪、能落到给定证据维度之一"
    "（person/event/building/era/poem/theme）。"
    "只输出 JSON，不要任何解释。字段：\n"
    "title(路线主题，≤18字)、open_question(统领性开放问题，≤40字)、"
    "scope_note(策展边界说明，≤60字)、"
    "propositions(数组，每项 {axis, hypothesis, dimension, question})。"
    "dimension 必须是给定维度之一。严禁编造证据未覆盖的维度或事实。\n"
    "【关键约束】hypothesis 是『研究视角假设』，必须写成可被证据检验的"
    "开放框架（例如『同一栋楼的用途随年代被改写』），"
    "禁止写成『某人在某年某月做了某事』式的具体断言句。"
    "具体的人名/年代/事件若出现在 hypothesis 中，必须是证据摘要里"
    "已经出现过的；否则一律删去。question 才是具体的求证提问。"
)

_CRITIQUE_SYSTEM = (
    "你是独立的命题批判者，与命题生成者分离，职责是严格挑出过度引申。"
    "给定一组已生成的命题假设与已取证史实摘要，对每条命题独立判定：\n"
    "  - verdict='allowed'：该假设为中性研究框架，不含证据摘要未直接支撑的"
    "具体断言；\n"
    "  - verdict='over_extended'：含证据摘要未出现过的"
    "（具体人名+具体年代+具体事件）组合断言。\n"
    "若 over_extended，必须给出 rewritten_hypothesis：去掉具体未证断言、"
    "保留研究视角的中性框架（例如『围绕 X，以证据可核验的视角展开』）。\n"
    "不要评价命题内容的好坏，只看它是否越过了证据边界。"
    "只输出 JSON：{\"verdicts\": [{\"index\": <命题序号>, \"verdict\": \"...\", "
    "\"rewritten_hypothesis\": \"...\"}]}"
)


def _heuristic_over_extended(hypothesis: str, summary: str) -> bool:
    """回退：未配 LLM / critique 漏判时用 token 粗筛过度引申。

    判据：假设中出现证据摘要未覆盖的具体年代（4 位数字），或含断言落点动词
    （曾/在此/建于/死于…）且出现证据摘要未出现过的 2–4 字中文专名。
    """
    sum_years = set(_YEAR.findall(summary))
    hyp_years = set(_YEAR.findall(hypothesis))
    if hyp_years - sum_years:
        return True
    assertion_markers = ("曾", "在此", "于此处", "建于", "死于", "创办", "秘密", "亲历", "在此地")
    if not any(m in hypothesis for m in assertion_markers):
        return False
    tokens = set(re.findall(r"[\u4e00-\u9fff]{2,4}", hypothesis))
    sum_tokens = set(re.findall(r"[\u4e00-\u9fff]{2,4}", summary))
    return bool(tokens - sum_tokens)


def _neutralize(p: Proposition) -> None:
    """把过度引申假设收敛为中性研究框架（去掉具体未证断言）。"""
    p.hypothesis = f"围绕『{p.axis}』，以证据可核验的视角展开，不预设未证结论。"
    p.status = "rewritten"


def _propose(intent: Intent, summary: str, dims: list[str]) -> dict[str, Any] | None:
    """第一步：生成命题假设（不自我批判）。失败返回 None。"""
    user = (
        f"用户原始留言：{intent.message or '（未提供，仅给场景）'}\n"
        f"行走场景：{intent.scene}\n"
        f"可用证据维度：{', '.join(dims)}\n\n"
        f"已取证史实摘要：\n{summary}\n\n"
        "请拆成研究命题。"
    )
    try:
        return chat_json(
            system=_PROPOSE_SYSTEM, user=user, temperature=0.3,
            backend="cloud", role="creative",
            max_tokens=2048,  # 结构化输出紧凑(JSON)，封顶仅防失控，不影响质量
        )
    except Exception:  # noqa: BLE001
        return None


def _critique(props: list[dict[str, Any]], summary: str) -> dict[str, Any] | None:
    """第二步：独立批判每条命题。失败返回 None（调用方降级为全部 allowed）。"""
    numbered = [{"index": i, **p} for i, p in enumerate(props)]
    user = (
        f"已取证史实摘要：\n{summary}\n\n"
        "待审查命题：\n"
        + json.dumps(numbered, ensure_ascii=False)
        + "\n\n请逐条判定。"
    )
    try:
        return chat_json(
            system=_CRITIQUE_SYSTEM, user=user, temperature=0.2,
            backend="cloud", role="structured",
            max_tokens=2048,
        )
    except Exception:  # noqa: BLE001
        return None


def decompose_intent(
    intent: Intent,
    plan: RoutePlan,
    pack: EvidencePack,
    available_dimensions: list[str] | None = None,
) -> PropositionSet | None:
    """propose → critique 两步分解；propose 失败/未配置返回 None（调用方回退规则）。"""
    if not llm_configured():
        return None

    summary, kinds = _evidence_summary(plan, pack)
    dims = available_dimensions or sorted(kinds)

    # 第一步：生成命题假设（不自我批判）
    proposed = _propose(intent, summary, dims)
    if proposed is None:
        return None

    props_raw = [
        p for p in (proposed.get("propositions") or []) if isinstance(p, dict)
    ]
    if not props_raw:
        return None

    # 第二步：独立批判（失败则全部 allowed，启发式兜底接管）
    crit = _critique(props_raw, summary) or {}
    verdicts: dict[int, dict[str, Any]] = {}
    for v in crit.get("verdicts") or []:
        if not isinstance(v, dict):
            continue
        idx = v.get("index")
        if idx is None:
            continue
        try:
            verdicts[int(idx)] = v
        except (TypeError, ValueError):
            continue

    props: list[Proposition] = []
    for i, p in enumerate(props_raw):
        dim = str(p.get("dimension") or "theme")
        if dim not in _DIMENSIONS:
            dim = "theme"
        hypothesis = str(p.get("hypothesis") or "")
        status = "allowed"
        flag_reason = ""
        v = verdicts.get(i)
        if v and str(v.get("verdict") or "").strip() == "over_extended":
            rw = str(v.get("rewritten_hypothesis") or "").strip()
            if rw:
                hypothesis = rw
                flag_reason = "独立批判收敛过度引申假设"
            else:
                flag_reason = "独立批判标记过度引申（未给改写，走启发式兜底）"
            status = "rewritten"
        props.append(
            Proposition(
                axis=str(p.get("axis") or "研究轴"),
                hypothesis=hypothesis,
                dimension=dim,
                question=str(p.get("question") or ""),
                status=status,
                flag_reason=flag_reason,
            )
        )

    # 启发式兜底：捕捉 critique 漏判 / critique 不可用
    rt_notes: list[str] = []
    rt_applied = any(p.status == "rewritten" for p in props)
    for p in props:
        if p.status != "allowed":
            continue
        if _heuristic_over_extended(p.hypothesis, summary):
            _neutralize(p)
            p.flag_reason = "假设含证据未覆盖的具体断言（启发式）"
            rt_notes.append(f"红队收敛「{p.axis}」：{p.flag_reason}")
            rt_applied = True

    scope_note = str(proposed.get("scope_note") or "")
    if rt_applied:
        scope_note = (
            scope_note + "（红队已收敛过度引申假设）"
            if scope_note
            else "红队已收敛过度引申的假设"
        )

    return PropositionSet(
        title=str(proposed.get("title") or intent.scene),
        open_question=str(proposed.get("open_question") or intent.message or ""),
        scope_note=scope_note,
        propositions=props,
        redteam_applied=rt_applied,
        redteam_notes=rt_notes,
    )
