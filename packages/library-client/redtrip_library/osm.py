"""Fetch OSM building footprints via Overpass (corridor only)."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

OVERPASS_URLS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
)


def _http_post(url: str, body: str, *, bypass_proxy: bool, timeout: float = 12.0) -> tuple[int, str]:
    data = body.encode("utf-8")
    # Overpass public instances reject empty / default urllib User-Agent with HTTP 406.
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
            "Accept": "application/json",
            "User-Agent": "RedTrip/0.1 (Shanghai Library contest demo; local)",
        },
    )
    handlers: list[Any] = []
    if bypass_proxy:
        handlers.append(urllib.request.ProxyHandler({}))
    opener = urllib.request.build_opener(*handlers)
    try:
        with opener.open(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")
    except Exception as e:  # noqa: BLE001
        return 0, str(e)


def fetch_building_footprints(
    *,
    south: float,
    west: float,
    north: float,
    east: float,
    limit: int = 80,
) -> dict[str, Any]:
    """Return GeoJSON-like FeatureCollection of building polygons."""
    # pad tiny bbox
    if north - south < 0.001:
        south -= 0.0015
        north += 0.0015
    if east - west < 0.001:
        west -= 0.0015
        east += 0.0015

    query = f"""
[out:json][timeout:10];
(
  way["building"]({south},{west},{north},{east});
);
out body;
>;
out skel qt;
""".strip()
    payload = "data=" + urllib.parse.quote(query)

    last_err = "overpass failed"
    raw: dict[str, Any] | None = None
    # Try direct first (local proxy often TLS-breaks overseas mirrors), then system proxy.
    bypass_modes = (True, False)
    if os.getenv("REDTRIP_OSM_BYPASS_PROXY", "1") == "0":
        bypass_modes = (False, True)

    # Keep demo snappy: at most 2 mirrors × 1 bypass mode unless forced.
    max_attempts = int(os.getenv("REDTRIP_OSM_MAX_ATTEMPTS", "3"))
    attempts = 0
    for url in OVERPASS_URLS:
        for bypass in bypass_modes:
            if attempts >= max_attempts:
                break
            attempts += 1
            status, text = _http_post(url, payload, bypass_proxy=bypass, timeout=12.0)
            if status != 200:
                last_err = f"{url} bypass={int(bypass)} HTTP {status}: {text[:160]}"
                continue
            try:
                raw = json.loads(text)
                break
            except json.JSONDecodeError:
                last_err = f"{url} bypass={int(bypass)} invalid json"
                continue
        if raw is not None or attempts >= max_attempts:
            break

    if not raw:
        return {"type": "FeatureCollection", "features": [], "error": last_err}

    nodes: dict[int, tuple[float, float]] = {}
    for el in raw.get("elements") or []:
        if el.get("type") == "node":
            nodes[int(el["id"])] = (float(el["lon"]), float(el["lat"]))

    features: list[dict[str, Any]] = []
    for el in raw.get("elements") or []:
        if el.get("type") != "way":
            continue
        tags = el.get("tags") or {}
        if "building" not in tags:
            continue
        ring: list[list[float]] = []
        for nid in el.get("nodes") or []:
            pt = nodes.get(int(nid))
            if pt:
                ring.append([pt[0], pt[1]])
        if len(ring) < 4:
            continue
        if ring[0] != ring[-1]:
            ring.append(ring[0])
        levels = tags.get("building:levels")
        try:
            h = float(levels) * 3.0 if levels is not None else None
        except (TypeError, ValueError):
            h = None
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "osm_id": el.get("id"),
                    "levels": levels,
                    "height_m": h,
                    "height_schematic": h is None,
                    "name": tags.get("name"),
                },
                "geometry": {"type": "Polygon", "coordinates": [ring]},
            }
        )
        if len(features) >= limit:
            break

    return {
        "type": "FeatureCollection",
        "features": features,
        "source": "OpenStreetMap/Overpass",
        "count": len(features),
    }


def bbox_from_points(points: list[tuple[float, float]], pad: float = 0.0012) -> tuple[float, float, float, float]:
    lats = [p[0] for p in points]
    lngs = [p[1] for p in points]
    return (
        min(lats) - pad,
        min(lngs) - pad,
        max(lats) + pad,
        max(lngs) + pad,
    )
