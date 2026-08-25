"""R-20 whitelist loader — geo/pitfalls/buri join for curator."""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any


def _default_path() -> Path:
    # packages/curator/redtrip_curator → RedTrip/content/whitelist/points.json
    return Path(__file__).resolve().parents[3] / "content" / "whitelist" / "points.json"


@dataclass(frozen=True)
class WhitelistPoint:
    id: str
    name: str
    buri: str | None
    lat: float
    lng: float
    coord_source: str
    precision: str
    open_hours: str
    enterable: str
    need_reservation: str
    photo_spot: str | None
    district_tag: str

    def pitfalls(self) -> dict[str, str]:
        return {
            "open_hours": self.open_hours or "未收录",
            "enterable": self.enterable or "未收录",
            "need_reservation": self.need_reservation or "未收录",
        }


@dataclass
class Whitelist:
    points: list[WhitelistPoint]
    by_id: dict[str, WhitelistPoint]
    by_buri: dict[str, WhitelistPoint]

    @property
    def count(self) -> int:
        return len(self.points)

    def mapped_buris(self) -> list[str]:
        return [p.buri for p in self.points if p.buri]

    def for_buri(self, buri: str) -> WhitelistPoint | None:
        return self.by_buri.get(buri)

    def filter_by_district(self, tag: str | None) -> list[WhitelistPoint]:
        if not tag:
            return list(self.points)
        return [p for p in self.points if tag in (p.district_tag or "")]


def _parse_point(raw: dict[str, Any]) -> WhitelistPoint | None:
    try:
        buri = raw.get("buri")
        if buri is not None and not isinstance(buri, str):
            buri = None
        if isinstance(buri, str) and not buri.strip():
            buri = None
        return WhitelistPoint(
            id=str(raw["id"]),
            name=str(raw["name"]),
            buri=buri,
            lat=float(raw["lat"]),
            lng=float(raw["lng"]),
            coord_source=str(raw.get("coord_source") or "manual"),
            precision=str(raw.get("precision") or "schematic"),
            open_hours=str(raw.get("open_hours") or "未收录"),
            enterable=str(raw.get("enterable") or "未收录"),
            need_reservation=str(raw.get("need_reservation") or "未收录"),
            photo_spot=raw.get("photo_spot") if isinstance(raw.get("photo_spot"), str) else None,
            district_tag=str(raw.get("district_tag") or ""),
        )
    except (KeyError, TypeError, ValueError):
        return None


@lru_cache(maxsize=4)
def load_whitelist(path: str | None = None) -> Whitelist:
    p = Path(path) if path else _default_path()
    if not p.exists():
        return Whitelist(points=[], by_id={}, by_buri={})
    with p.open(encoding="utf-8") as f:
        data = json.load(f)
    rows = data.get("points") if isinstance(data, dict) else data
    if not isinstance(rows, list):
        return Whitelist(points=[], by_id={}, by_buri={})
    points: list[WhitelistPoint] = []
    by_id: dict[str, WhitelistPoint] = {}
    by_buri: dict[str, WhitelistPoint] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        pt = _parse_point(row)
        if not pt:
            continue
        points.append(pt)
        by_id[pt.id] = pt
        if pt.buri:
            by_buri[pt.buri] = pt
    return Whitelist(points=points, by_id=by_id, by_buri=by_buri)


def clear_whitelist_cache() -> None:
    load_whitelist.cache_clear()
