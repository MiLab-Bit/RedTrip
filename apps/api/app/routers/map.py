from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter
from redtrip_library import bbox_from_points, fetch_building_footprints

from app.main import (
    FootprintRequest,
    _fixture_for_bbox,
)

router = APIRouter()


@router.post("/v1/map/footprints")
def map_footprints(req: FootprintRequest) -> dict[str, Any]:
    """OSM building footprints for the route corridor (real outlines)."""
    pts: list[tuple[float, float]] = []
    for p in req.points:
        lat, lng = p.get("lat"), p.get("lng")
        if isinstance(lat, (int, float)) and isinstance(lng, (int, float)):
            pts.append((float(lat), float(lng)))
    if len(pts) < 1:
        return {"type": "FeatureCollection", "features": [], "error": "no points"}
    south, west, north, east = bbox_from_points(pts, pad=0.0022)
    bbox = {"south": south, "west": west, "north": north, "east": east}

    # 默认走真实 Overpass（演示才优先 fixture）：仅在显式 REDTRIP_OSM_PREFER_FIXTURE=1
    # 时优先 fixture。生产模式（REDTRIP_MODE=production）强制禁用 fixture，杜绝误触
    # 假数据（审查疑点#6）。实时拉取超时/空结果仍会安全回退 fixture（见下文 fallback）。
    _mode = (os.getenv("REDTRIP_MODE") or "indexed").lower()
    if _mode == "production":
        prefer_fixture = False
    else:
        prefer_fixture = os.getenv("REDTRIP_OSM_PREFER_FIXTURE") == "1"
    if prefer_fixture:
        clipped = _fixture_for_bbox(south=south, west=west, north=north, east=east)
        if clipped:
            clipped["bbox"] = bbox
            return clipped

    from concurrent.futures import ThreadPoolExecutor
    from concurrent.futures import TimeoutError as FuturesTimeout

    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            fut = pool.submit(
                fetch_building_footprints,
                south=south,
                west=west,
                north=north,
                east=east,
                limit=90,
            )
            result = fut.result(timeout=float(os.getenv("REDTRIP_OSM_BUDGET_S", "14")))
    except FuturesTimeout:
        result = {
            "type": "FeatureCollection",
            "features": [],
            "error": "overpass budget timeout",
        }
    result["bbox"] = bbox

    if not result.get("features"):
        clipped = _fixture_for_bbox(south=south, west=west, north=north, east=east)
        if clipped:
            clipped["bbox"] = bbox
            clipped["fallback_of"] = result.get("error")
            return clipped
    result["live"] = True
    return result
