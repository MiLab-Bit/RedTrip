"""反方策展人：单视角对抗性评审（升级版：非阻断，可回写修正）。

仅取「城市漫步策展委员会」9 视角中的「视角 8 · 反方策展人」，
在 polish 之后、Gate 判定通过之后跑一次 LLM 调用，
产出评审意见（concerns / missed_voices / warnings）与**可执行的 fixes**。

升级点（典籍新生）：
- 旧版只读告警，意见（如「含导游腔『驻足时』」）无法落回正文，人力复核成本高。
- 新版 review 额外输出 `fixes`：每条 fix 指明 stop_order + 问题片段 + 替换文本，
  由 _apply_review_fixes 对正文做精准局部替换（删除/改写违规句），
  替换后重新过 Gate；替换不触碰 sources、不新增史实。
- 语义上仍是「非阻断」：fixes 只在替换后 Gate 仍通过时才落地；否则保留原文。

设计要点（避免「降智 bug」）：
- 只读取已生成的叙事文本（各节点故事卡 + 路线零件长散文）与已标注的命题字段，
  不自行补史；模型若要质疑薄弱处，应指明「此处证据等级偏低」，而非编造反证。
- fixes 只做「措辞修正」（导游腔/套话/重复），不得改动事实与出处。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .hongyuan import VoicePack
from .llm import chat_json, llm_configured
from .models import RoutePlan

_REVIEW_PROMPT_PATH = (
    Path(__file__).resolve().parents[1] / "prompts" / "opposing_curator.txt"
)

_REVIEW_SCHEMA = """JSON schema（只输出评审意见与措辞修正建议，绝不新增史实）：
{
  "concerns": [
    {"claim": "一条反对意见（具体、落到节点或叙事机制）",
     "node": "节点名或「全路线」",
     "mechanism": "属于哪一种叙事捷径 / 盲区 / 伦理风险",
     "fix": "对应的可执行修改方案"}
  ],
  "missed_voices": ["被忽略的声音或群体"],
  "skipped_harder_node": "一个更重要但被跳过的地点或议题（无则 null）",
  "alternative_thesis": "完全不同的备选策展命题（一句话）",
  "reverse_route_note": "若从终点走回起点，故事会发生什么变化",
  "warnings": ["面向参与者的可读告警；每条都落到具体节点、可被执行、不要求统一答案"],
  "fixes": [
    {"stop_order": 2,
     "problem": "出现导游腔命令式『驻足时』",
     "replace": "（若只是删除该句则填空字符串；若改写则给整句替换文本，须与原文同义同事实）"}
  ]
}
concerns 最多 5 条；warnings 最多 5 条；fixes 最多 5 条，只修措辞不改事实。"""


def _review_system_prompt() -> str:
    if _REVIEW_PROMPT_PATH.exists():
        return _REVIEW_PROMPT_PATH.read_text(encoding="utf-8")
    return (
        "你是反方策展人，对一条 Citywalk 路线做对抗性评审，只输出 JSON。"
        "字段：concerns, missed_voices, skipped_harder_node, alternative_thesis, "
        "reverse_route_note, warnings。"
    )


def _review_payload(envelope: dict[str, Any], plan: RoutePlan | None) -> dict[str, Any]:
    """把已生成的叙事文本整理成「待评审文档」，不新增任何内容。"""
    doc: dict[str, Any] = {
        "curatorial_thesis": {
            "theme": envelope.get("theme"),
            "logic_line": envelope.get("logic_line"),
            "why_visit": envelope.get("why_visit"),
            "curator_note": envelope.get("curator_note"),
        },
        "route_nodes": [],
        "narrative_by_stop": [],
    }
    for s in envelope.get("route", {}).get("stops") or []:
        if not isinstance(s, dict):
            continue
        doc["route_nodes"].append(
            {
                "order": s.get("order"),
                "name": s.get("name"),
                "meaning": s.get("meaning"),
                "transition_to_next": s.get("transition_to_next"),
            }
        )

    by_stop: dict[Any, dict[str, Any]] = {}
    for b in envelope.get("blocks") or []:
        if not isinstance(b, dict):
            continue
        so = b.get("stop_order")
        t = b.get("type")
        if t == "story_card":
            by_stop.setdefault(so, {})["card"] = b.get("body") or ""
        elif t == "essay":
            by_stop.setdefault(so, {})["essay"] = b.get("body") or ""
    for so, parts in by_stop.items():
        doc["narrative_by_stop"].append({"stop_order": so, **parts})
    return doc


def review_envelope(
    envelope: dict[str, Any],
    plan: RoutePlan | None = None,
    voice: VoicePack | None = None,
) -> dict[str, Any] | None:
    """对已成形的叙事做一次「反方策展人」评审。

    返回结构化评审（含 warnings 列表）；失败或无 LLM 时返回 None，调用方忽略即可。
    本函数绝不修改传入的 envelope。
    """
    if not llm_configured():
        return None
    payload = _review_payload(envelope, plan)
    voice_block = voice.as_prompt_block() if voice else ""
    user = (
        (f"{voice_block}\n\n" if voice_block else "")
        + "以下是已生成的路线与其叙事文本（含各节点故事卡与路线零件长散文）。\n"
        "请作为「反方策展人」做一次对抗性评审：找出盲点、叙事捷径、伦理风险与参与门槛，"
        "产出非阻断的评审告警。只输出 JSON。\n"
        + json.dumps(payload, ensure_ascii=False)
        + "\n\n" + _REVIEW_SCHEMA
    )
    try:
        obj = chat_json(
            system=_review_system_prompt(),
            user=user,
            temperature=0.5,
            backend="auto",
            role="creative",
            timeout=180,
        )
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(obj, dict):
        return None
    # 规整：确保 warnings 是 list[str]，空内容时不报错
    raw_w = obj.get("warnings")
    warnings = (
        [str(w) for w in raw_w if isinstance(w, (str, int, float))]
        if isinstance(raw_w, list)
        else []
    )
    obj["warnings"] = warnings
    # 规整 concerns 为 list[dict]，丢弃异常项并封顶 5 条
    raw_c = obj.get("concerns")
    concerns = (
        [c for c in raw_c if isinstance(c, dict)]
        if isinstance(raw_c, list)
        else []
    )
    obj["concerns"] = concerns[:5]
    # 规整 fixes 为 list[dict]，丢弃异常项并封顶 5 条
    raw_f = obj.get("fixes")
    fixes = (
        [f for f in raw_f if isinstance(f, dict) and f.get("stop_order") is not None]
        if isinstance(raw_f, list)
        else []
    )
    obj["fixes"] = fixes[:5]
    return obj


def apply_review_fixes(
    envelope: dict[str, Any],
    review: dict[str, Any],
) -> list[str]:
    """把反方策展人的 fixes 精准落地到对应 story_card 正文（典籍新生升级）。

    仅做「措辞修正」：problem 指出的问题片段若在正文中，按 replace 处理——
    - replace 为空字符串 → 删除该句（连同句号）；
    - replace 非空 → 替换原文中与 problem 最接近的句子。
    不触碰 sources、不新增史实；替换后若句子缺失（原文不含 problem），跳过该条。
    返回修复记录 notes（供写入 warnings 追踪）。
    """
    notes: list[str] = []
    fixes = review.get("fixes") or []
    if not isinstance(fixes, list):
        return notes
    for fix in fixes:
        if not isinstance(fix, dict):
            continue
        so = fix.get("stop_order")
        problem = str(fix.get("problem") or "").strip()
        replace = str(fix.get("replace") or "").strip()
        if not problem:
            continue
        # 定位对应 story_card
        card = next(
            (
                b for b in envelope.get("blocks") or []
                if isinstance(b, dict) and b.get("type") == "story_card"
                and int(b.get("stop_order") or 0) == int(so or 0)
            ),
            None,
        )
        if not card:
            continue
        body = str(card.get("body") or "")
        if not body:
            continue
        # 按问题片段删除/替换所在句子（保守：只处理 problem 出现的那一句）
        import re as _re
        sentences = _re.split(r"(?<=[。！？\n])", body)
        changed = False
        out_sents: list[str] = []
        for s in sentences:
            if problem and problem in s:
                if replace:
                    out_sents.append(s.replace(problem, replace))
                # replace 为空 → 删句
                changed = True
            else:
                out_sents.append(s)
        if changed:
            card["body"] = "".join(out_sents)
            notes.append(
                f"反方策展人修正: stop{so} 「{problem[:20]}…」"
                + (" 已改写" if replace else " 已删除该句")
            )
    return notes
