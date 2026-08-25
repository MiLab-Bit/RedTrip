from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class SourceRef:
    dataset: str
    record_id: str
    excerpt: str | None = None

    def as_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "dataset": self.dataset,
            "record_id": self.record_id,
        }
        if self.excerpt:
            d["excerpt"] = self.excerpt
        return d


@dataclass
class IdentityLayer:
    kind: Literal["building", "event", "era", "poem", "person", "geoname", "literary"]
    label: str
    claim: str
    source: SourceRef

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "label": self.label,
            "claim": self.claim,
            "source": self.source.as_dict(),
        }


@dataclass
class BuildingEvidence:
    buri: str
    name: str
    address: str | None
    lat: float | None
    lng: float | None
    layers: list[IdentityLayer] = field(default_factory=list)
    raw_detail: dict[str, Any] | None = None
    whitelist_id: str | None = None
    coord_source: str = "none"
    precision: str = "schematic"
    pitfalls: dict[str, str] = field(
        default_factory=lambda: {
            "open_hours": "未收录",
            "enterable": "未收录",
            "need_reservation": "未收录",
        }
    )

    road_context: str | None = None
    photo_spot: str | None = None


@dataclass
class EvidencePack:
    buildings: list[BuildingEvidence]
    gaps: list[dict[str, str]]
    fetched_at: str
    mode: Literal["snapshot", "indexed", "mcp"] = "indexed"
    sources_used: list[str] = field(default_factory=list)


@dataclass
class Intent:
    audience: str
    scene: str
    duration_min: int
    tone: str
    delivery: str
    companions: str
    assumptions: list[str]
    message: str | None = None
    daypart: str = "day"  # day 白天 / night 夜晚 / full 全天 / suburb 郊区（自然景点）
    city: str = "shanghai"  # 策展城市 key（见 redtrip_curator.cities.CITY_REGISTRY）


@dataclass
class PlannedStop:
    order: int
    evidence: BuildingEvidence
    minutes: int
    meaning: str
    transition_to_next: str | None


@dataclass
class RoutePlan:
    stops: list[PlannedStop]
    duration_min: int
    walk_meters_est: int
