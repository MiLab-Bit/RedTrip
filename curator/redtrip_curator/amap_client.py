"""高德开放平台 Web服务 全接口客户端（env-gated，best-effort 降级）。

读取环境变量：
  - REDTRIP_AMAP_KEY   高德 Web服务 key（必需）
  - REDTRIP_AMAP_SIG   数字签名私钥（开启数字签名后必须提供并随请求发送 sig）

所有请求自动按高德算法追加 sig（若配置了私钥）。
缺失 key / 调用失败 / 网络异常 -> 返回 None 或 []，绝不抛异常、不影响主链路。

提供能力：
  - geocode(address, city="上海") -> (lat, lng) | None        地理编码（场景中心点，默认上海）
  - regeo(lng, lat, extensions="all") -> dict | None          逆地理：坐标 -> 地址/AOI/周边
  - district_of(lng, lat) -> str | None                      逆地理取区/街道（内容标注「位于 X 区」）
  - poi_text(keywords, city=None, types=None, offset=25)       POI 关键词搜索
  - poi_around(lng, lat, radius=2000, types=None, ...)         POI 周边搜索
  - walking(lng1, lat1, lng2, lat2) -> dict | None            步行路径（真实距离/时长/步骤）
  - get_weather(adcode="310000") -> dict | None               天气（实时 + 预报）
  - weather_tip(adcode="310000") -> str | None                出行天气一句话提示
  - district(keywords, subdistrict=1) -> list[dict]           行政区查询
  - inputtips(keywords, city=None) -> list[dict]              输入提示（模糊词 -> 真实地名）
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import urllib.parse
import urllib.request

logger = logging.getLogger("redtrip.amap")

AMAP_KEY = (os.environ.get("REDTRIP_AMAP_KEY") or "").strip()
AMAP_SIG = (os.environ.get("REDTRIP_AMAP_SIG") or "").strip()
HTTP_TIMEOUT = 5.0

GEO_URL = "https://restapi.amap.com/v3/geocode/geo"
REGO_URL = "https://restapi.amap.com/v3/geocode/regeo"
TEXT_URL = "https://restapi.amap.com/v3/place/text"
AROUND_URL = "https://restapi.amap.com/v3/place/around"
WALK_URL = "https://restapi.amap.com/v3/direction/walking"
WEATHER_URL = "https://restapi.amap.com/v3/weather/weatherInfo"
DISTRICT_URL = "https://restapi.amap.com/v3/config/district"
TIPS_URL = "https://restapi.amap.com/v3/assistant/inputtips"


def _key_ready() -> bool:
    return bool(AMAP_KEY)


def _sign_params(params: dict) -> dict:
    """若配置了数字签名私钥，按高德算法追加 sig。

    sig = md5( 按 key 字典序拼接的 k=v&k=v...（含 key 本身） + 私钥 )，32 位小写。
    参数值使用原始（未编码）字符串参与签名，发送时再整体 urlencode。
    """
    if not AMAP_SIG:
        return params
    p = dict(params)
    p["key"] = AMAP_KEY
    raw = "&".join(f"{k}={p[k]}" for k in sorted(p))
    p["sig"] = hashlib.md5((raw + AMAP_SIG).encode("utf-8")).hexdigest()
    return p


def _call(path: str, params: dict, timeout: float = HTTP_TIMEOUT) -> dict:
    """发起请求并解析 JSON；失败返回含 _error 的 dict，不抛异常。

    网络层自动重试 1 次（高德免费配额偶发抖动/限流时提升稳定性）。
    """
    if not _key_ready():
        return {"_error": "no_key"}
    url = "https://restapi.amap.com" + path + "?" + urllib.parse.urlencode(_sign_params(params))
    last_err = None
    for _attempt in range(2):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            logger.warning("amap %s failed (attempt %d): %s", path, _attempt + 1, exc)
    return {"_error": str(last_err)}


def _parse_loc(loc: str | None) -> tuple[float | None, float | None]:
    if not loc or "," not in loc:
        return None, None
    lng_s, lat_s = loc.split(",", 1)
    try:
        return float(lat_s), float(lng_s)
    except (TypeError, ValueError):
        return None, None


# ----------------------------------------------------------------------------
# 1. 地理编码
# ----------------------------------------------------------------------------
def geocode(address: str, city: str | None = "上海") -> tuple[float, float] | None:
    if not address:
        return None
    params = {"address": address}
    if city:
        params["city"] = city
    data = _call("/v3/geocode/geo", params)
    if data.get("_error") or data.get("status") != "1" or not data.get("geocodes"):
        return None
    loc = (data["geocodes"][0] or {}).get("location", "")
    return _parse_loc(loc)


# ----------------------------------------------------------------------------
# 2. 逆地理编码
# ----------------------------------------------------------------------------
def regeo(lng: float, lat: float, extensions: str = "all") -> dict | None:
    if lng is None or lat is None:
        return None
    data = _call("/v3/geocode/regeo", {"location": f"{lng},{lat}", "extensions": extensions})
    if data.get("_error") or data.get("status") != "1":
        return None
    return data.get("regeocode")


def regeo_area(lng: float, lat: float) -> str | None:
    """返回坐标所在片区/地标名（AOI），用于叙事语境补充。"""
    rg = regeo(lng, lat, extensions="all")
    if not rg:
        return None
    aois = rg.get("aois") or []
    if aois:
        return (aois[0] or {}).get("name")
    return rg.get("formatted_address")


# ----------------------------------------------------------------------------
# 2b. 行政区（逆地理取区/街道，用于内容标注「位于 X 区」）
# ----------------------------------------------------------------------------
_DISTRICT_CACHE: dict[tuple, str | None] = {}


def district_of(lng: float, lat: float, max_cache: int = 2048) -> str | None:
    """坐标所在行政区（区/街道），如「黄浦区」「外滩街道」。best-effort，失败返 None。

    模块级缓存（按四舍五入坐标）避免重复逆地理调用，控制配额与延迟。
    """
    if lng is None or lat is None:
        return None
    key = (round(lat, 4), round(lng, 4))
    if key in _DISTRICT_CACHE:
        return _DISTRICT_CACHE[key]
    val: str | None = None
    rg = regeo(lng, lat, extensions="base")
    if rg:
        comp = (rg.get("addressComponent") or {})
        val = comp.get("district") or comp.get("township") or None
    if len(_DISTRICT_CACHE) < max_cache:
        _DISTRICT_CACHE[key] = val
    return val


# ----------------------------------------------------------------------------
# 3. POI 搜索（关键词 / 周边）
# ----------------------------------------------------------------------------
def _normalize_poi(p: dict) -> dict:
    lat, lng = _parse_loc(p.get("location"))
    return {
        "name": p.get("name"),
        "address": p.get("address"),
        "type": p.get("type"),
        "lat": lat,
        "lng": lng,
        "adcode": p.get("adcode"),
        "poi_id": p.get("id"),
    }


def poi_text(keywords: str, city: str | None = None, types: str | None = None,
             offset: int = 25) -> list[dict]:
    if not keywords:
        return []
    params = {"keywords": keywords, "offset": str(offset), "page": "1"}
    if city:
        params["city"] = city
    if types:
        params["types"] = types
    data = _call("/v3/place/text", params)
    if data.get("_error") or data.get("status") != "1":
        return []
    return [_normalize_poi(p) for p in (data.get("pois") or [])]


def poi_around(lng: float, lat: float, radius: int = 2000, types: str | None = None,
               keywords: str | None = None, offset: int = 25) -> list[dict]:
    if lng is None or lat is None:
        return []
    params = {
        "location": f"{lng},{lat}",
        "radius": str(radius),
        "offset": str(offset),
        "page": "1",
    }
    if types:
        params["types"] = types
    if keywords:
        params["keywords"] = keywords
    data = _call("/v3/place/around", params)
    if data.get("_error") or data.get("status") != "1":
        return []
    return [_normalize_poi(p) for p in (data.get("pois") or [])]


# ----------------------------------------------------------------------------
# 4. 步行路径规划
# ----------------------------------------------------------------------------
def walking(lng1: float, lat1: float, lng2: float, lat2: float) -> dict | None:
    if None in (lng1, lat1, lng2, lat2):
        return None
    data = _call(
        "/v3/direction/walking",
        {"origin": f"{lng1},{lat1}", "destination": f"{lng2},{lat2}"},
    )
    if data.get("_error") or data.get("status") != "1":
        return None
    paths = (data.get("route") or {}).get("paths") or []
    if not paths:
        return None
    path = paths[0]
    steps = []
    for st in (path.get("steps") or []):
        slat, slng = _parse_loc(st.get("polyline", "").split(";")[0] if st.get("polyline") else None)
        steps.append({
            "instruction": st.get("instruction"),
            "duration_s": int(st.get("duration") or 0),
            "distance_m": int(st.get("distance") or 0),
        })
    return {
        "distance_m": int(path.get("distance") or 0),
        "duration_s": int(path.get("duration") or 0),
        "steps": steps,
    }


# ----------------------------------------------------------------------------
# 5. 天气
# ----------------------------------------------------------------------------
def get_weather(adcode: str = "310000") -> dict | None:
    """返回 {live: {...}, forecast: [cast,...]}。adcode 默认上海 310000。"""
    live = (_call("/v3/weather/weatherInfo", {"city": adcode, "extensions": "base"})
            .get("lives") or [{}])
    live = live[0] if live else {}
    fc = (_call("/v3/weather/weatherInfo", {"city": adcode, "extensions": "all"})
          .get("forecasts") or [{}])
    fc = fc[0] if fc else {}
    return {"live": live, "forecast": fc.get("casts") or []}


def weather_tip(adcode: str = "310000") -> str | None:
    """出行天气一句话提示，例如「上海今日多云 22~28°C，东南风3级，适宜步行游览」。"""
    w = get_weather(adcode)
    if not w:
        return None
    live = w.get("live") or {}
    if live:
        wth = live.get("weather") or ""
        t = live.get("temperature") or ""
        wind = f"{live.get('winddirection','')}风{live.get('windpower','')}级" if live.get("winddirection") else ""
        tail = "，适宜步行游览" if wth and ("晴" in wth or "云" in wth or "阴" in wth) else ""
        return f"上海当前{wth} {t}°C{('，' + wind) if wind else ''}{tail}".strip("，")
    casts = w.get("forecast") or []
    if casts:
        c = casts[0]
        return (f"上海今日{c.get('dayweather','')} "
                f"{c.get('nighttemp','')}~{c.get('daytemp','')}°C，"
                f"{c.get('daywind','')}风").strip("，")
    return None


# ----------------------------------------------------------------------------
# 6. 行政区 / 输入提示
# ----------------------------------------------------------------------------
def district(keywords: str, subdistrict: int = 1, extensions: str = "base") -> list[dict]:
    if not keywords:
        return []
    data = _call("/v3/config/district",
                {"keywords": keywords, "subdistrict": str(subdistrict), "extensions": extensions})
    if data.get("_error") or data.get("status") != "1":
        return []
    out = []
    for d in (data.get("districts") or []):
        out.append({"name": d.get("name"), "adcode": d.get("adcode"),
                    "level": d.get("level"), "center": d.get("center")})
        for sub in (d.get("districts") or []):
            out.append({"name": sub.get("name"), "adcode": sub.get("adcode"),
                        "level": sub.get("level"), "center": sub.get("center")})
    return out


def inputtips(keywords: str, city: str | None = None) -> list[dict]:
    if not keywords:
        return []
    params = {"keywords": keywords}
    if city:
        params["city"] = city
    data = _call("/v3/assistant/inputtips", params)
    if data.get("_error") or data.get("status") != "1":
        return []
    out = []
    for t in (data.get("tips") or []):
        if t.get("location") and t["location"] != "[]":
            lat, lng = _parse_loc(t["location"])
            out.append({"name": t.get("name"), "district": t.get("district"),
                        "address": t.get("address"), "lat": lat, "lng": lng,
                        "adcode": t.get("adcode")})
    return out
