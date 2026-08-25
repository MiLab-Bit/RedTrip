"""Multi-source place suggest for brief「从哪里走起」.

Sources:
  - R-20 whitelist (馆藏可走点)
  - district corridors (梧桐区 / 一大周边)
  - L3 hotwords places (小红书周热词)
  - static street aliases (街区别名)
"""
from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

from .hongyuan.layer3_hotwords import load_hotword_index, place_ranking
from .whitelist import load_whitelist

_GENERIC = frozenset({"上海", "徐汇", "静安", "虹口", "黄浦", "魔都"})

# Hand-curated corridor / street aliases that map cleanly to evidence routing
_STREET_ALIASES: list[dict[str, str]] = [
    {"label": "武康路一带", "scene": "武康路一带", "aliases": "武康路,武康,Wukang,wukang,梧桐"},
    {"label": "武康路—华山路一带", "scene": "武康路—华山路一带", "aliases": "华山路,华山"},
    {"label": "安福路一带", "scene": "安福路一带", "aliases": "安福路,安福"},
    {"label": "衡山路一带", "scene": "衡山路一带", "aliases": "衡山路,衡山,衡复"},
    {"label": "思南路一带", "scene": "思南公馆周边", "aliases": "思南路,思南公馆,思南"},
    {"label": "一大周边", "scene": "中共一大会址一带", "aliases": "一大,一大会址,兴业路,石库门,黄陂南路"},
    {"label": "愚园路一带", "scene": "愚园路一带", "aliases": "愚园路,愚园"},
    {"label": "多伦路一带", "scene": "多伦路一带", "aliases": "多伦路,多伦"},
    {"label": "外滩一带", "scene": "外滩一带", "aliases": "外滩,Bund"},
    {"label": "西岸滨江", "scene": "西岸一带", "aliases": "西岸,龙腾大道,徐汇滨江"},
]


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", (s or "").strip().lower())


def _scene_for_place(name: str) -> str:
    n = name.strip()
    if n.endswith(("路", "街", "道", "浜", "区")):
        return f"{n}一带" if not n.endswith("一带") else n
    if "周边" in n or "一带" in n:
        return n
    return n


@lru_cache(maxsize=1)
def _index_fingerprint() -> str:
    wl = load_whitelist()
    hot = load_hotword_index()
    return f"{wl.count}:{hot.get('week')}:{len(hot.get('entries') or [])}"


@lru_cache(maxsize=4)
def build_place_index(fingerprint: str) -> list[dict[str, Any]]:
    _ = fingerprint  # cache key
    items: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(
        *,
        label: str,
        scene: str,
        source: str,
        source_label: str,
        aliases: str = "",
        district: str = "",
        heat: float = 0.0,
        hint: str = "",
        id_: str = "",
    ) -> None:
        key = _norm(scene) or _norm(label)
        if not key or key in seen:
            return
        # allow same label from stronger source later — first write wins by priority order
        seen.add(key)
        items.append(
            {
                "id": id_ or f"{source}:{key}",
                "label": label,
                "scene": scene,
                "source": source,
                "source_label": source_label,
                "district": district,
                "heat": heat,
                "hint": hint,
                "search_text": _norm(
                    f"{label} {scene} {aliases} {district} {hint}"
                ),
            }
        )

    # 1) Whitelist — highest trust for curate
    wl = load_whitelist()
    for p in wl.points:
        add(
            id_=p.id,
            label=p.name,
            scene=_scene_for_place(p.name),
            source="whitelist",
            source_label="馆藏白名单",
            aliases="",
            district=p.district_tag or "",
            heat=0.7 if p.buri else 0.55,
            hint=p.district_tag or "R-20",
        )

    # 2) District corridors
    for tag in ("梧桐区", "一大周边"):
        add(
            label=f"{tag}走廊",
            scene=f"{tag}一带" if tag != "一大周边" else "中共一大会址一带",
            source="corridor",
            source_label="街区走廊",
            aliases=tag,
            district=tag,
            heat=0.75,
            hint="按片区取证",
        )

    # 3) Street aliases
    for a in _STREET_ALIASES:
        add(
            label=a["label"],
            scene=a["scene"],
            source="corridor",
            source_label="街区走廊",
            aliases=a.get("aliases", ""),
            heat=0.8,
            hint="常用起点",
        )

    # 4) Hotwords places
    ranking = place_ranking(top_k=30)
    for row in ranking.get("items") or []:
        place = str(row.get("place") or "")
        if not place or place in _GENERIC:
            continue
        add(
            label=place,
            scene=str(row.get("scene") or _scene_for_place(place)),
            source="hotwords",
            source_label="小红书热词",
            aliases=" ".join(row.get("terms") or []),
            heat=float(row.get("heat") or 0.5),
            hint=str(row.get("top_term") or ""),
        )

    return items


def suggest_places(q: str, *, limit: int = 8) -> dict[str, Any]:
    query = (q or "").strip()
    fp = _index_fingerprint()
    catalog = build_place_index(fp)
    limit = max(1, min(20, int(limit)))

    if not query:
        # Idle: blend hot ranking + a few whitelist anchors
        hot = [x for x in catalog if x["source"] == "hotwords"]
        hot.sort(key=lambda x: float(x.get("heat") or 0), reverse=True)
        wl = [x for x in catalog if x["source"] == "whitelist"][:4]
        merged: list[dict[str, Any]] = []
        seen: set[str] = set()
        for x in hot[:6] + wl:
            k = x["scene"]
            if k in seen:
                continue
            seen.add(k)
            merged.append(x)
            if len(merged) >= limit:
                break
        return {
            "q": "",
            "mode": "browse",
            "count": len(merged),
            "items": merged,
            "sources": ["hotwords", "whitelist", "corridor"],
        }

    nq = _norm(query)
    scored: list[tuple[float, dict[str, Any]]] = []
    for item in catalog:
        text = item["search_text"]
        label_n = _norm(item["label"])
        scene_n = _norm(item["scene"])
        score = 0.0
        if label_n == nq or scene_n == nq:
            score = 100.0
        elif label_n.startswith(nq) or scene_n.startswith(nq):
            score = 80.0
        elif nq in label_n or nq in scene_n:
            score = 60.0
        elif nq in text:
            score = 40.0
        else:
            # loose: all chars of query appear in order
            idx = 0
            ok = True
            for ch in nq:
                j = text.find(ch, idx)
                if j < 0:
                    ok = False
                    break
                idx = j + 1
            if ok and len(nq) >= 2:
                score = 22.0
        if score <= 0:
            continue
        # source priority bump
        bump = {
            "whitelist": 8.0,
            "corridor": 6.0,
            "hotwords": 4.0,
        }.get(item["source"], 0.0)
        score += bump + float(item.get("heat") or 0) * 5.0
        scored.append((score, item))

    scored.sort(key=lambda x: x[0], reverse=True)
    items = [x for _, x in scored[:limit]]
    return {
        "q": query,
        "mode": "search",
        "count": len(items),
        "items": items,
        "sources": sorted({x["source"] for x in items}) or ["whitelist", "hotwords", "corridor"],
    }
