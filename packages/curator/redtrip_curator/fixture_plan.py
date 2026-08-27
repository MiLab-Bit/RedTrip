"""从冻结 RouteEnvelope 重建 RoutePlan（不改站序/whitelist）。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import BuildingEvidence, IdentityLayer, PlannedStop, RoutePlan, SourceRef

_ROOT = Path(__file__).resolve().parents[3]
_LANDMARK_PATH = _ROOT / "content" / "curated" / "exterior-bund.json"

_LANDMARK_INDEX: dict[str, dict[str, Any]] | None = None


def _load_landmark_index() -> dict[str, dict[str, Any]]:
    global _LANDMARK_INDEX
    if _LANDMARK_INDEX is not None:
        return _LANDMARK_INDEX
    idx: dict[str, dict[str, Any]] = {}
    if _LANDMARK_PATH.exists():
        try:
            rows = json.loads(_LANDMARK_PATH.read_text(encoding="utf-8"))
            if isinstance(rows, list):
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    name = str(row.get("name") or "").strip()
                    if name:
                        idx[name] = row
                    for alias in row.get("alias") or []:
                        if isinstance(alias, str) and alias.strip():
                            idx[alias.strip()] = row
        except Exception:  # noqa: BLE001
            pass
    _LANDMARK_INDEX = idx
    return idx


def _match_landmark(name: str, record_id: str | None) -> dict[str, Any] | None:
    idx = _load_landmark_index()
    for key in (name, record_id or ""):
        key = (key or "").strip()
        if key and key in idx:
            return idx[key]
    for key, row in idx.items():
        if key and (key in name or name in key):
            return row
    return None


def _layer_from_dict(layer: dict[str, Any]) -> IdentityLayer:
    src = layer.get("source") if isinstance(layer.get("source"), dict) else {}
    return IdentityLayer(
        kind=layer.get("kind") or "building",
        label=str(layer.get("label") or ""),
        claim=str(layer.get("claim") or ""),
        source=SourceRef(
            dataset=str(src.get("dataset") or "source"),
            record_id=str(src.get("record_id") or ""),
            excerpt=src.get("excerpt") if isinstance(src.get("excerpt"), str) else None,
        ),
    )


def building_evidence_from_stop(stop: dict[str, Any]) -> BuildingEvidence:
    geo = stop.get("geo") if isinstance(stop.get("geo"), dict) else {}
    layers = [
        _layer_from_dict(l)
        for l in (stop.get("layers") or [])
        if isinstance(l, dict)
    ]
    name = str(stop.get("name") or "")
    buri = stop.get("buri")
    record_id = None
    for layer in stop.get("layers") or []:
        if not isinstance(layer, dict):
            continue
        src = layer.get("source") or {}
        if isinstance(src, dict) and src.get("record_id"):
            record_id = str(src["record_id"])
            break
    lm = _match_landmark(name, record_id)
    raw_detail: dict[str, Any] = {}
    if lm:
        raw_detail = {
            "landmark_year_built": lm.get("year_built"),
            "landmark_style": lm.get("style"),
            "landmark_architect": lm.get("architect"),
            "landmark_description": lm.get("description"),
            "address": lm.get("address"),
            "category": "historic",
        }
    uri = buri if isinstance(buri, str) and buri.strip() else f"fixture://{stop.get('whitelist_id') or name}"
    pitfalls = stop.get("pitfalls") if isinstance(stop.get("pitfalls"), dict) else {}
    return BuildingEvidence(
        buri=uri,
        name=name,
        address=raw_detail.get("address") or lm.get("address") if lm else None,
        lat=geo.get("lat"),
        lng=geo.get("lng"),
        layers=layers,
        raw_detail=raw_detail or None,
        whitelist_id=stop.get("whitelist_id"),
        coord_source=str(geo.get("coord_source") or "none"),
        precision=str(geo.get("precision") or "approximate"),
        evidence_channel=str(stop.get("evidence_channel") or "manual"),
        pitfalls={
            "open_hours": str(pitfalls.get("open_hours") or "未收录"),
            "enterable": str(pitfalls.get("enterable") or "未收录"),
            "need_reservation": str(pitfalls.get("need_reservation") or "未收录"),
        },
    )


def plan_from_envelope(envelope: dict[str, Any]) -> RoutePlan:
    route = envelope.get("route") if isinstance(envelope.get("route"), dict) else {}
    stops: list[PlannedStop] = []
    for raw in route.get("stops") or []:
        if not isinstance(raw, dict):
            continue
        order = int(raw.get("order") or len(stops) + 1)
        act = raw.get("act")
        if act not in ("prologue", "focus", "transit", "epilogue", "bridge", None):
            act = None
        if act == "bridge":
            act = "transit"
        stops.append(
            PlannedStop(
                order=order,
                evidence=building_evidence_from_stop(raw),
                minutes=int(raw.get("minutes") or 12),
                meaning=str(raw.get("meaning") or ""),
                transition_to_next=raw.get("transition_to_next"),
                act=act,  # type: ignore[arg-type]
            )
        )
    stops.sort(key=lambda s: s.order)
    return RoutePlan(
        stops=stops,
        duration_min=int(route.get("duration_min") or 90),
        walk_meters_est=int(route.get("walk_meters_est") or 4200),
    )
