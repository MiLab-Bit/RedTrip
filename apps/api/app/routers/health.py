from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, Query
from redtrip_curator.cities import list_cities
from redtrip_curator.llm import llm_configured, llm_model
from redtrip_library import SlcClient
from redtrip_library.providers import health_probe as _provider_health

from app.main import (
    CACHE_SCHEMA,
    CACHE_TTL_S,
    WHITELIST_PATH,
    _cache_mem,
    _cache_stats,
    _hotwords_health,
    _probe_live_providers,
)

router = APIRouter()


@router.get("/v1/health")
def health(probe: bool = Query(default=False, description="probe live providers")) -> dict[str, Any]:
    mode = os.getenv("REDTRIP_MODE", "indexed")
    has_key = bool(os.getenv("SLC_API_KEY", "").strip())
    live_results: dict[str, bool] = {}
    live_probe: dict[str, Any] | None = None
    if probe:
        live_results, live_probe = _probe_live_providers(SlcClient())
    provider_health = _provider_health(live_results)
    payload: dict[str, Any] = {
        "ok": True,
        "service": "redtrip-api",
        "mode": mode,
        "slc_key_configured": has_key,
        "slc_api": {
            "status": "/v1/slc/status",
            "buildings": "/v1/slc/buildings?q=",
            "building_detail": "/v1/slc/buildings/detail?uri=",
            "events": "/v1/slc/events?buri=",
            "red_events": "/v1/slc/red-events?q=",
        },
        "llm": {
            "configured": llm_configured(),
            "model": llm_model() if llm_configured() else None,
        },
        "library_client": True,
        "curator": True,
        "gate": True,
        "cities": len(list_cities()),
        "providers": provider_health.get("total"),
        "providers_ingested": provider_health.get("ingested"),
        "providers_live_ready": provider_health.get("live_ready"),
        "whitelist": WHITELIST_PATH.exists(),
        "whitelist_hint": (
            "R-20 points.json loaded"
            if WHITELIST_PATH.exists()
            else "R-20 missing; indexed curate may fall back"
        ),
        "hotwords": _hotwords_health(),
        "curate_cache": {
            "entries": len(_cache_mem),
            "hits": _cache_stats["hits"],
            "misses": _cache_stats["misses"],
            "ttl_s": CACHE_TTL_S,
            "schema": CACHE_SCHEMA,
        },
    }
    if live_probe is not None:
        payload["provider_probe"] = live_probe
        payload["ok"] = all(live_results.values())
    return payload
