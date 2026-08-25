"""高德 Web 服务客户端（POI 检索 + 地理编码）。

用途：场景词 → 真实点位的通用通道。当场景不在 R-20 白名单（如外滩、
临港新城）时，白名单取证拿不到点，此客户端负责把用户输入的地点词
解析成带坐标的真实 POI，作为策展路线的证据锚点。

签名规则（高德 Web 服务官方）：
1. 对除 sig 外的所有请求参数（含 key）按参数名升序排列；
2. 用「原始值」拼接为 k1=v1&k2=v2（不做 URL 编码——服务端按解码后重算）；
3. 末尾拼接私钥（REDTRIP_AMAP_SIG）；
4. 对整串取 MD5 作为 sig；发送时再整体 URL 编码。

坐标系：高德返回 GCJ-02。现有白名单/上游证据坐标本就混用（GCJ/WGS），
本客户端不额外转换，与 fetch_evidence 现状保持一致（坐标统一为独立待办）。
"""

from __future__ import annotations

import hashlib
import json
import os
import urllib.parse
import urllib.request
from typing import Any

_BASE = "https://restapi.amap.com"

# 城市 → 高德 city 参数（高德 place/text 的 city 支持行政区名/区号/adcode）。
# RedTrip 城市 key（cities.CITY_REGISTRY）→ 高德行政区名。
CITY_AMAP_NAME: dict[str, str] = {
    "shanghai": "上海",
    "suzhou": "苏州",
    "hangzhou": "杭州",
    "yangzhou": "扬州",
    "nanjing": "南京",
    "jiaxing": "嘉兴",
    "nantong": "南通",
    "changzhou": "常州",
    "wuxi": "无锡",
    "beijing": "北京",
    "guangzhou": "广州",
    "shenzhen": "深圳",
    "chengdu": "成都",
    "chongqing": "重庆",
    "xian": "西安",
    "hefei": "合肥",
}


def amap_city_param(city_key: str | None) -> str:
    """把 RedTrip 城市 key 转成高德 city 参数；缺省/未知回退上海区号 021。"""
    if not city_key:
        return "021"
    name = CITY_AMAP_NAME.get(city_key, "")
    if name:
        return name
    return city_key  # 允许直接传高德行政区名/区号


class AmapClient:
    """极简高德 Web API 客户端（零第三方依赖，纯 stdlib）。"""

    def __init__(self, key: str | None = None, secret: str | None = None) -> None:
        self.key = key if key is not None else os.getenv("REDTRIP_AMAP_KEY", "").strip()
        self.secret = (
            secret
            if secret is not None
            else os.getenv("REDTRIP_AMAP_SIG", "").strip()
        )

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        if not self.key:
            return {"status": "0", "info": "missing REDTRIP_AMAP_KEY"}
        q: dict[str, Any] = dict(params)
        q["key"] = self.key
        if self.secret:
            raw = "&".join(f"{k}={v}" for k, v in sorted(q.items())) + self.secret
            q["sig"] = hashlib.md5(raw.encode("utf-8")).hexdigest()
        url = f"{_BASE}{path}?{urllib.parse.urlencode(q)}"
        try:
            with urllib.request.urlopen(url, timeout=8) as r:
                return json.load(r)
        except Exception as exc:  # noqa: BLE001 —— 网络/解析失败统一降级
            return {"status": "0", "info": str(exc)}

    def place_text(
        self,
        keywords: str,
        city: str = "021",
        offset: int = 20,
        page: int = 1,
        city_key: str | None = None,
    ) -> list[dict[str, Any]]:
        """POI 关键词检索。

        city：高德 city 参数（行政区名/区号，默认 021 上海区号）。
        city_key：RedTrip 城市 key（如 suzhou/hangzhou），会自动转成高德行政区名，
                  优先于 city 参数（兼容旧调用；新代码传 city_key 即可）。
        返回 [{name, address, lng, lat, type}]（已解析坐标的条目）。
        失败/空结果返回 []，不抛异常（取证层据此降级）。
        """
        if not self.key:
            return []
        city_param = amap_city_param(city_key) if city_key else city
        d = self._get(
            "/v3/place/text",
            {
                "keywords": keywords,
                "city": city_param,
                "citylimit": "true",
                "offset": str(offset),
                "page": str(page),
                "extensions": "base",
            },
        )
        pois = d.get("pois") if d.get("status") == "1" else []
        out: list[dict[str, Any]] = []
        for p in pois:
            if not isinstance(p, dict):
                continue
            loc = str(p.get("location") or "")
            if "," not in loc:
                continue
            lng_s, lat_s = loc.split(",", 1)
            try:
                out.append(
                    {
                        "name": str(p.get("name") or keywords),
                        "address": str(p.get("address") or "").strip() or None,
                        "lng": float(lng_s),
                        "lat": float(lat_s),
                        "type": str(p.get("type") or ""),
                    }
                )
            except ValueError:
                continue
        return out

    def geocode(
        self, address: str, city_key: str | None = None
    ) -> tuple[float, float] | None:
        """地理编码：地址 → (lng, lat)。city_key 为 RedTrip 城市 key（自动转高德名）。失败返回 None。"""
        if not self.key:
            return None
        city_param = amap_city_param(city_key) if city_key else "021"
        d = self._get("/v3/geocode/geo", {"address": address, "city": city_param})
        if d.get("status") != "1":
            return None
        geocodes = d.get("geocodes") or []
        if not geocodes or not geocodes[0].get("location"):
            return None
        lng_s, lat_s = str(geocodes[0]["location"]).split(",", 1)
        try:
            return float(lng_s), float(lat_s)
        except ValueError:
            return None
