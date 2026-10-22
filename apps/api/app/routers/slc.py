from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from redtrip_library import SlcClient

from app.main import _slc_payload

router = APIRouter()


@router.get("/v1/slc/probe")
def slc_probe() -> dict[str, Any]:
    """兼容旧探针；推荐运维使用 /v1/slc/status。"""
    client = SlcClient()
    return client.health_probe()


@router.get("/v1/slc/status")
def slc_status() -> dict[str, Any]:
    """上图 API 连通性探针（building_list + detail + event_list）。"""
    return SlcClient().health_probe()


@router.get("/v1/slc/buildings")
def slc_buildings(
    q: str = Query(default="", description="建筑 freetext 检索词"),
) -> dict[str, Any]:
    """上图建筑列表 — `building/list`。"""
    return _slc_payload(SlcClient().building_list(q))


@router.get("/v1/slc/buildings/detail")
def slc_building_detail(
    uri: str = Query(..., description="建筑 URI（buri）"),
) -> dict[str, Any]:
    """上图建筑详情 — `building/detail`。"""
    return _slc_payload(SlcClient().building_detail(uri))


@router.get("/v1/slc/events")
def slc_events(
    buri: str = Query(..., description="建筑 buri"),
) -> dict[str, Any]:
    """上图建筑关联事件 — `building/event/list`。"""
    return _slc_payload(SlcClient().event_list(buri))


@router.get("/v1/slc/red-events")
def slc_red_events(
    q: str = Query(default="", description="红色旅游事件关键词"),
) -> dict[str, Any]:
    """上图红色旅游事件 — `route/getEventList`。"""
    return _slc_payload(SlcClient().red_event_list(keyword=q))
