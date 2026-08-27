"""黑黛：单视角对抗性评审（非阻断，仅告警）。

「黑黛」为黑玫瑰花形象的对抗性策展人格；仅取委员会 9 视角中的留白挑刺位，
在 polish 之后、Gate 判定通过之后跑一次 LLM 调用，
产出非阻断的评审意见（concerns / missed_voices / warnings），
供人类复核或下一轮 curate 参考。本模块不修改正文、不新增史实。

设计要点（避免「降智 bug」）：
- 只读取已生成的叙事文本（各节点故事卡 + 路线零件长散文）与已标注的命题字段，
  不自行补史；模型若要质疑薄弱处，应指明「此处证据等级偏低」，而非编造反证。
- 产出的 warnings 一律非阻断：进入 CurateResult.warnings 与 envelope.curator_review，
  由人或下一轮 curate 决定如何处理，绝不直接改写正文。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .hongyuan import VoicePack
from .llm import chat_json, llm_configured
from .models import RoutePlan
from .personas import HEIDAI_NAME

_REVIEW_PROMPT_PATH = (
    Path(__file__).resolve().parents[1] / "prompts" / "opposing_curator.txt"
)

_REVIEW_SCHEMA = """JSON schema（只输出评审意见，绝不修改正文）：
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
  "warnings": ["面向参与者的可读告警；每条都落到具体节点、可被执行、不要求统一答案"]
}
concerns 最多 5 条；warnings 最多 5 条，必须具体、可执行。"""


def _review_system_prompt() -> str:
    if _REVIEW_PROMPT_PATH.exists():
        return _REVIEW_PROMPT_PATH.read_text(encoding="utf-8")
    return (
        f"你是「{HEIDAI_NAME}」（黑玫瑰形象的对抗性策展人），"
        "对一条 Citywalk 路线做对抗性评审，只输出 JSON。"
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
    """对已成形的叙事做一次「黑黛」对抗性评审。

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
        + f"请作为「{HEIDAI_NAME}」做一次对抗性评审：找出盲点、叙事捷径、伦理风险与参与门槛，"
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
    return obj
