from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Query
from redtrip_curator.cities import list_cities
from redtrip_curator.hongyuan import place_ranking
from redtrip_curator.place_suggest import suggest_places
from redtrip_library import SlcClient
from redtrip_library.providers import health_probe as _provider_health

from app.main import WHITELIST_PATH, _probe_live_providers

router = APIRouter()


@router.get("/v1/hotwords/ranking")
def hotwords_ranking(
    top_k: int = Query(default=10, ge=3, le=20, description="榜单条数"),
) -> dict[str, Any]:
    """L3 小红书上海热门景点排行（每周二更新），供出题「从哪里走起」。"""
    return place_ranking(top_k=top_k)


@router.get("/v1/places/suggest")
def places_suggest(
    q: str = Query(default="", description="输入关键词，空则返回热门/默认"),
    limit: int = Query(default=8, ge=1, le=20),
) -> dict[str, Any]:
    """多源地点联想：馆藏白名单 · 街区走廊 · 小红书热词。"""
    return suggest_places(q, limit=limit)


@router.get("/v1/cities")
def cities() -> dict[str, Any]:
    """城市选择器数据源：返回注册城市 + OSM 语料就绪标记（前端据此启用/禁用）。"""
    return {
        "default": "shanghai",
        "count": len(list_cities()),
        "cities": list_cities(),
    }


@router.get("/v1/providers")
def providers(
    probe: bool = Query(default=False, description="实际探测 live provider"),
) -> dict[str, Any]:
    """数据源注册表与可达性矩阵；默认不把未探测的 live 源标为 ready。"""
    live_results: dict[str, bool] = {}
    details: dict[str, Any] | None = None
    if probe:
        live_results, details = _probe_live_providers(SlcClient())
    payload = _provider_health(live_results)
    if details is not None:
        payload["probe"] = details
    return payload


@router.get("/v1/whitelist")
def whitelist() -> dict[str, Any]:
    if WHITELIST_PATH.exists():
        with WHITELIST_PATH.open(encoding="utf-8") as f:
            data = json.load(f)
        points = data.get("points") if isinstance(data, dict) else data
        if isinstance(points, list):
            slim = []
            for p in points:
                if not isinstance(p, dict):
                    continue
                slim.append(
                    {
                        "id": p.get("id"),
                        "name": p.get("name"),
                        "buri": p.get("buri"),
                        "lat": p.get("lat"),
                        "lng": p.get("lng"),
                        "precision": p.get("precision"),
                        "district_tag": p.get("district_tag"),
                        "open_hours": p.get("open_hours"),
                        "enterable": p.get("enterable"),
                        "need_reservation": p.get("need_reservation"),
                    }
                )
            return {
                "count": len(slim),
                "source": "content/whitelist/points.json",
                "points": slim,
            }
    # Demo fixture 兜底已彻底拆除：返回空清单（前端会自然空地图而非显示 demo 内容）
    return {"count": 0, "source": "none", "points": []}
