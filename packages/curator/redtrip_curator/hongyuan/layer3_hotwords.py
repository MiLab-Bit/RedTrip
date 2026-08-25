"""L3 · 小红书上海周热词 RAG（景点优先）。

只提供当代读法口吻；不提供史实。每周二更新 content/hotwords/latest.json。
"""
from __future__ import annotations

import json
import random
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[4]  # RedTrip/
_HOTWORDS_PATH = _ROOT / "content" / "hotwords" / "latest.json"


@dataclass(frozen=True)
class HotwordHit:
    id: str
    term: str
    places: tuple[str, ...]
    hint: str
    heat: float
    week: str
    score: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _iso_week_fallback() -> str:
    from datetime import date

    return date.today().strftime("%G-W%V")


def load_hotword_index(path: Path | None = None) -> dict[str, Any]:
    p = path or _HOTWORDS_PATH
    if not p.exists():
        return {
            "week": _iso_week_fallback(),
            "updated_at": None,
            "source": "missing",
            "entries": [],
        }
    with p.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        return {"week": _iso_week_fallback(), "entries": []}
    data.setdefault("week", _iso_week_fallback())
    data.setdefault("entries", [])
    return data


def _norm_places(places: list[str] | None) -> list[str]:
    out: list[str] = []
    for raw in places or []:
        s = re.sub(r"\s+", "", str(raw or "").strip())
        if s and s not in out:
            out.append(s)
    return out


def _place_overlap(entry_places: list[str], query_places: list[str]) -> float:
    if not entry_places:
        return 0.15  # generic
    score = 0.0
    for ep in entry_places:
        for qp in query_places:
            if not ep or not qp:
                continue
            if ep == qp:
                score = max(score, 1.0)
            elif ep in qp or qp in ep:
                score = max(score, 0.82)
            elif len(ep) >= 2 and len(qp) >= 2 and (ep[:2] == qp[:2]):
                score = max(score, 0.35)
    return score


def retrieve_hotwords(
    *,
    places: list[str] | None,
    tone: str | None = None,
    top_k: int = 4,
    seed: int | None = None,
    index: dict[str, Any] | None = None,
) -> tuple[str, list[HotwordHit]]:
    """Agentic RAG retrieve: place-first, then heat, light stochastic among ties."""
    idx = index or load_hotword_index()
    week = str(idx.get("week") or _iso_week_fallback())
    entries = [e for e in (idx.get("entries") or []) if isinstance(e, dict)]
    if not entries:
        return week, []

    q = _norm_places(places)
    tone_key = None
    if tone:
        for key in ("硬核", "文艺", "轻社交"):
            if key in tone:
                tone_key = key
                break

    scored: list[tuple[float, dict[str, Any]]] = []
    for e in entries:
        place_score = _place_overlap(
            [str(x) for x in (e.get("places") or [])],
            q,
        )
        if place_score < 0.3 and q:
            # keep a few citywide fallbacks
            if place_score < 0.15:
                continue
        heat = float(e.get("heat") or 0.5)
        tone_tags = e.get("tone_tags") or []
        tone_boost = 0.08 if (tone_key and tone_key in tone_tags) else 0.0
        # Prefer concrete attractions over citywide
        specificity = 0.12 if any(
            p not in ("上海", "徐汇", "静安", "虹口", "黄浦")
            for p in (e.get("places") or [])
        ) else 0.0
        total = place_score * 0.62 + heat * 0.28 + tone_boost + specificity
        scored.append((total, e))

    if not scored:
        # fallback: top heat citywide
        scored = [
            (float(e.get("heat") or 0.4), e)
            for e in entries
        ]

    scored.sort(key=lambda x: x[0], reverse=True)
    # Take a wider pool then sample for mild lottery within RAG top
    pool = scored[: max(top_k * 3, top_k)]
    rng = random.Random(seed if seed is not None else 0)
    # Weighted sample without replacement
    picks: list[tuple[float, dict[str, Any]]] = []
    remaining = list(pool)
    k = min(top_k, len(remaining))
    for _ in range(k):
        if not remaining:
            break
        weights = [max(0.01, s) for s, _ in remaining]
        choice = rng.choices(remaining, weights=weights, k=1)[0]
        picks.append(choice)
        remaining.remove(choice)

    hits: list[HotwordHit] = []
    for total, e in picks:
        places_t = tuple(str(x) for x in (e.get("places") or []))
        hits.append(
            HotwordHit(
                id=str(e.get("id") or e.get("term") or "hot"),
                term=str(e.get("term") or "").strip(),
                places=places_t,
                hint=str(e.get("hint") or "仅作当代读法"),
                heat=float(e.get("heat") or 0.5),
                week=week,
                score=round(float(total), 4),
            )
        )
    hits = [h for h in hits if h.term]
    return week, hits


def hotwords_prompt_block(week: str, hits: list[HotwordHit]) -> str:
    if not hits:
        return "第三层周热词：本周索引为空或未命中景点，跳过。"
    lines = [
        f"第三层 · 本周上海热词（week={week}，景点优先 RAG）：",
        "以下词条只可影响当代口吻与提问语气；禁止写成史实、开放时间、坐标或新增事件。",
    ]
    for h in hits:
        place = "、".join(h.places[:3]) if h.places else "上海"
        lines.append(f"- 「{h.term}」（关联：{place}；{h.hint}）")
    return "\n".join(lines)


def hotwords_summary_line(week: str, hits: list[HotwordHit]) -> str:
    if not hits:
        return f"本周热词（{week}）：未命中"
    terms = " · ".join(h.term for h in hits[:3])
    return f"本周热词（{week}）：{terms}"


_GENERIC_PLACES = frozenset(
    {"上海", "徐汇", "静安", "虹口", "黄浦", "魔都", "梧桐区", "衡复"}
)


def place_ranking(
    *,
    top_k: int = 10,
    index: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Aggregate weekly hotwords into a place leaderboard for brief scene picker."""
    idx = index or load_hotword_index()
    week = str(idx.get("week") or _iso_week_fallback())
    entries = [e for e in (idx.get("entries") or []) if isinstance(e, dict)]

    # place -> stats
    bucket: dict[str, dict[str, Any]] = {}
    for e in entries:
        heat = float(e.get("heat") or 0.5)
        term = str(e.get("term") or "").strip()
        places = [str(p).strip() for p in (e.get("places") or []) if str(p).strip()]
        concrete = [p for p in places if p not in _GENERIC_PLACES]
        if not concrete:
            continue
        # Primary place = first concrete; also credit co-places lightly
        for i, place in enumerate(concrete[:3]):
            weight = 1.0 if i == 0 else 0.45
            row = bucket.setdefault(
                place,
                {
                    "place": place,
                    "heat": 0.0,
                    "mentions": 0,
                    "terms": [],
                },
            )
            row["heat"] = max(float(row["heat"]), heat * weight)
            # accumulate soft score
            row["_score"] = float(row.get("_score") or 0) + heat * weight
            row["mentions"] = int(row["mentions"]) + (1 if i == 0 else 0)
            if term and term not in row["terms"] and i == 0:
                row["terms"].append(term)

    ranked = sorted(
        bucket.values(),
        key=lambda r: (float(r.get("_score") or 0), float(r.get("heat") or 0)),
        reverse=True,
    )[: max(1, top_k)]

    items = []
    for rank, r in enumerate(ranked, start=1):
        place = str(r["place"])
        # Scene value for curator intent
        if place.endswith(("路", "街", "道", "浜")):
            scene = f"{place}一带"
        else:
            scene = place
        items.append(
            {
                "rank": rank,
                "place": place,
                "scene": scene,
                "heat": round(float(r["heat"]), 3),
                "score": round(float(r.get("_score") or 0), 3),
                "mentions": int(r["mentions"]),
                "top_term": (r["terms"][0] if r["terms"] else place),
                "terms": r["terms"][:3],
            }
        )

    return {
        "week": week,
        "updated_at": idx.get("updated_at"),
        "source": idx.get("source") or "xiaohongshu_weekly",
        "label": "小红书热门景点",
        "count": len(items),
        "items": items,
    }
