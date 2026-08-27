"""高德开放平台 Web服务 API 适配层（env-gated, best-effort）。

读取环境变量：
  - REDTRIP_AMAP_KEY   高德 Web服务 key（必需）
  - REDTRIP_AMAP_SIG   数字签名私钥（可选；开启数字签名后必须提供并随请求发送 sig）
缺失或调用失败则全部降级为 no-op，不影响主链路。

提供：
  - geocode_address(name, city=None) -> (lat, lng) | None   地理编码
  - search_poi(keywords, city=None, types=None) -> list[dict]  POI 搜索
  - enrich_buildings_with_coords(buildings, city=None)        坐标纠偏（best-effort）
"""
import hashlib
import json
import logging
import os
import urllib.parse
import urllib.request

logger = logging.getLogger("redtrip.geocode")

AMAP_KEY = (os.environ.get("REDTRIP_AMAP_KEY") or "").strip()
AMAP_SIG = (os.environ.get("REDTRIP_AMAP_SIG") or "").strip()
GEO_URL = "https://restapi.amap.com/v3/geocode/geo"
POI_URL = "https://restapi.amap.com/v3/place/text"
HTTP_TIMEOUT = 4.0


def _key_ready() -> bool:
    return bool(AMAP_KEY)


def _sign_params(params: dict) -> dict:
    """若配置了数字签名私钥，则在 params 上追加 sig。

    sig = md5( 按 key 字典序拼接的 k=v&k=v... + 私钥 )，32 位小写。
    参数值使用原始（未编码）字符串参与签名，发送时再整体 urlencode。
    """
    if not AMAP_SIG:
        return params
    p = dict(params)
    p["key"] = AMAP_KEY
    raw = "&".join(f"{k}={p[k]}" for k in sorted(p))
    p["sig"] = hashlib.md5((raw + AMAP_SIG).encode("utf-8")).hexdigest()
    return p


def _get_json(url: str):
    with urllib.request.urlopen(url, timeout=HTTP_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def geocode_address(name, city="上海"):
    if not _key_ready() or not name:
        return None
    params = {"address": name}
    if city:
        params["city"] = city
    url = GEO_URL + "?" + urllib.parse.urlencode(_sign_params(params))
    try:
        data = _get_json(url)
        if data.get("status") != "1" or not data.get("geocodes"):
            return None
        loc = (data["geocodes"][0] or {}).get("location", "")
        if "," not in loc:
            return None
        lng_s, lat_s = loc.split(",", 1)
        return (float(lat_s), float(lng_s))
    except Exception as exc:  # noqa: BLE001
        logger.warning("amap geocode failed for %r: %s", name, exc)
        return None


def search_poi(keywords, city=None, types=None):
    if not _key_ready() or not keywords:
        return []
    params = {"keywords": keywords, "offset": "25"}
    if city:
        params["city"] = city
    if types:
        params["types"] = types
    url = POI_URL + "?" + urllib.parse.urlencode(_sign_params(params))
    try:
        data = _get_json(url)
        if data.get("status") != "1":
            return []
        out = []
        for p in data.get("pois", []) or []:
            loc = p.get("location", "") or ""
            lat = lng = None
            if "," in loc:
                lng_s, lat_s = loc.split(",", 1)
                lat, lng = float(lat_s), float(lng_s)
            out.append({
                "name": p.get("name"),
                "address": p.get("address"),
                "type": p.get("type"),
                "lat": lat,
                "lng": lng,
            })
        return out
    except Exception as exc:  # noqa: BLE001
        logger.warning("amap poi search failed for %r: %s", keywords, exc)
        return []


def enrich_buildings_with_coords(buildings, city=None):
    """Best-effort 坐标纠偏：对没有上游坐标（coord_source != 'upstream'）的建筑做
    地理编码，成功则写回真实经纬度并把 coord_source 升级为 'upstream'。
    无 key / 失败 / 入参为空则原样返回。"""
    if not buildings:
        return buildings
    if not _key_ready():
        return buildings
    for b in buildings:
        cs = getattr(b, "coord_source", None)
        if cs == "upstream":
            continue
        name = getattr(b, "name", None)
        if not name:
            continue
        try:
            coord = geocode_address(name, city)
            if coord:
                lat, lng = coord
                if hasattr(b, "lat"):
                    b.lat = lat
                    b.lng = lng
                    b.coord_source = "upstream"
                    b.precision = "approximate"
        except Exception as exc:  # noqa: BLE001
            logger.warning("enrich failed for %r: %s", name, exc)
            continue
    return buildings
