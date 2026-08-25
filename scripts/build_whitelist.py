"""Seed / refresh content/whitelist/points.json from live building_list + hand seeds.

Usage (from RedTrip root, with .env):
  .venv\\Scripts\\python.exe scripts\\build_whitelist.py
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "library-client"))
os.environ.setdefault("PYTHONUTF8", "1")

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from redtrip_library import SlcClient  # noqa: E402

TODAY = date.today().isoformat()

# 一大周边：示意坐标，无 buri（诚实 gaps）
SEED_YIDA: list[dict] = [
    {
        "id": "wl-001",
        "name": "中共一大会址纪念馆周边",
        "buri": None,
        "lat": 31.2224,
        "lng": 121.4706,
        "coord_source": "manual",
        "precision": "approximate",
        "open_hours": "以现场公示为准",
        "enterable": "场馆需按开放安排参观",
        "need_reservation": "高峰期可能需预约（未收录精确规则）",
        "photo_spot": "纪念馆正门外侧人行道，朝向石库门立面",
        "district_tag": "一大周边",
    },
    {
        "id": "wl-002",
        "name": "兴业路石库门街巷",
        "buri": None,
        "lat": 31.2216,
        "lng": 121.4698,
        "coord_source": "manual",
        "precision": "schematic",
        "open_hours": "街巷全天可步行",
        "enterable": "部分民居不可入内",
        "need_reservation": "未收录",
        "photo_spot": "兴业路街巷中段，避免正对民居门洞",
        "district_tag": "一大周边",
    },
    {
        "id": "wl-003",
        "name": "黄陂南路—太仓路转角",
        "buri": None,
        "lat": 31.2205,
        "lng": 121.4718,
        "coord_source": "manual",
        "precision": "schematic",
        "open_hours": "未收录",
        "enterable": "公共人行区域可停留",
        "need_reservation": "未收录",
        "photo_spot": "转角人行道外侧，看弄堂—马路界面",
        "district_tag": "一大周边",
    },
    {
        "id": "wl-004",
        "name": "淮海中路近旁（示意点）",
        "buri": None,
        "lat": 31.2192,
        "lng": 121.4735,
        "coord_source": "manual",
        "precision": "schematic",
        "open_hours": "未收录",
        "enterable": "公共人行区域",
        "need_reservation": "未收录",
        "photo_spot": None,
        "district_tag": "一大周边",
    },
    {
        "id": "wl-005",
        "name": "思南公馆周边（示意点）",
        "buri": None,
        "lat": 31.2168,
        "lng": 121.4692,
        "coord_source": "manual",
        "precision": "schematic",
        "open_hours": "园区开放以现场为准",
        "enterable": "部分区域可参观",
        "need_reservation": "未收录",
        "photo_spot": "公馆区人行道，勿入未开放庭院",
        "district_tag": "一大周边",
    },
    {
        "id": "wl-006",
        "name": "回望点：香山路—兴业路意象",
        "buri": None,
        "lat": 31.2219,
        "lng": 121.4701,
        "coord_source": "manual",
        "precision": "schematic",
        "open_hours": "未收录",
        "enterable": "公共区域",
        "need_reservation": "未收录",
        "photo_spot": None,
        "district_tag": "一大周边",
    },
]

# Known Wukang buris already verified in curated-live / live-sample
KNOWN_BURIS: list[tuple[str, str, str]] = [
    ("wl-101", "巴金故居", "http://data.library.sh.cn/entity/architecture/if3k5yb021u3c4vd"),
    ("wl-102", "密丹公寓", "http://data.library.sh.cn/entity/architecture/rkdm0anh4h5wenaw"),
    ("wl-103", "国富门公寓", "http://data.library.sh.cn/entity/architecture/y7x57sifpaahpe52"),
    ("wl-104", "周作民旧居", "http://data.library.sh.cn/entity/architecture/n6bjgtjhduhim6st"),
    ("wl-105", "周璇旧居", "http://data.library.sh.cn/entity/architecture/p8lpy1b17cgrkse4"),
    ("wl-106", "上海汽车工业公司办公楼", "http://data.library.sh.cn/entity/architecture/fcryfptin8zm6qe4"),
    ("wl-107", "丁香花园", "http://data.library.sh.cn/entity/architecture/sm4repfu8n3ga66j"),
]


def _as_list(payload) -> list[dict]:
    if not isinstance(payload, dict):
        return []
    for key in ("data", "result", "list", "buildings", "items"):
        val = payload.get(key)
        if isinstance(val, list):
            return [x for x in val if isinstance(x, dict)]
        if isinstance(val, dict):
            for k2 in ("list", "items", "data", "result"):
                if isinstance(val.get(k2), list):
                    return [x for x in val[k2] if isinstance(x, dict)]
    return []


def _uri_of(item: dict) -> str | None:
    for k in ("uri", "buri", "id", "buildingUri", "building_uri"):
        v = item.get(k)
        if isinstance(v, str) and len(v) > 8:
            return v
    return None


def _name_of(item: dict) -> str:
    for k in ("name", "title", "buildingName", "label"):
        v = item.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return "未命名建筑"


def _coords(detail: dict) -> tuple[float | None, float | None]:
    loc = detail.get("location")
    if isinstance(loc, list) and loc:
        first = loc[0]
        if isinstance(first, dict):
            try:
                lat = float(first.get("lat"))
                lng = float(first.get("long") or first.get("lng") or first.get("lon"))
                return lat, lng
            except (TypeError, ValueError):
                return None, None
    return None, None


def _point_shell(
    *,
    id_: str,
    name: str,
    buri: str | None,
    lat: float,
    lng: float,
    coord_source: str,
    precision: str,
    district_tag: str,
    open_hours: str = "未收录",
    enterable: str = "未收录",
    need_reservation: str = "未收录",
    photo_spot: str | None = None,
) -> dict:
    return {
        "id": id_,
        "name": name,
        "buri": buri,
        "lat": lat,
        "lng": lng,
        "coord_source": coord_source,
        "precision": precision,
        "open_hours": open_hours,
        "enterable": enterable,
        "need_reservation": need_reservation,
        "photo_spot": photo_spot,
        "district_tag": district_tag,
        "verified_at": TODAY,
        "field_sources": {
            "lat": "人工核录" if coord_source == "manual" else "building_detail.location",
            "lng": "人工核录" if coord_source == "manual" else "building_detail.location",
            "buri": "SLC architecture uri" if buri else "未映射",
            "open_hours": "人工核录或未收录",
        },
    }


def main() -> int:
    out_dir = ROOT / "content" / "whitelist"
    out_dir.mkdir(parents=True, exist_ok=True)

    points: list[dict] = []
    for s in SEED_YIDA:
        points.append(
            _point_shell(
                id_=s["id"],
                name=s["name"],
                buri=s["buri"],
                lat=s["lat"],
                lng=s["lng"],
                coord_source=s["coord_source"],
                precision=s["precision"],
                district_tag=s["district_tag"],
                open_hours=s["open_hours"],
                enterable=s["enterable"],
                need_reservation=s["need_reservation"],
                photo_spot=s.get("photo_spot"),
            )
        )

    client = SlcClient()
    seen_uris = {p["buri"] for p in points if p.get("buri")}
    next_id = 101

    # Fill known buris with live detail coords when available
    for wid, name, buri in KNOWN_BURIS:
        if buri in seen_uris:
            continue
        lat, lng = 31.215, 121.447
        coord_source = "manual"
        precision = "schematic"
        detail_resp = client.building_detail(buri)
        if detail_resp.ok and isinstance(detail_resp.data, dict):
            detail = detail_resp.data.get("data")
            if not isinstance(detail, dict):
                detail = detail_resp.data
            if isinstance(detail, dict):
                clat, clng = _coords(detail)
                if clat is not None and clng is not None:
                    lat, lng = clat, clng
                    coord_source = "upstream"
                    precision = "approximate"
                name = str(detail.get("name") or name)
        points.append(
            _point_shell(
                id_=wid,
                name=name,
                buri=buri,
                lat=lat,
                lng=lng,
                coord_source=coord_source,
                precision=precision,
                district_tag="梧桐区",
            )
        )
        seen_uris.add(buri)
        next_id = max(next_id, int(wid.split("-")[1]) + 1)

    listing = client.building_list("")
    items = _as_list(listing.data) if listing.ok else []
    # Prefer Wukang / Huashan / Hengshan names for 梧桐区 fill
    keywords = ("武康", "华山", "衡山", "复兴", "思南", "淮海", "湖南", "天平")
    ranked = sorted(
        items,
        key=lambda it: (
            0
            if any(k in _name_of(it) or k in str(it.get("address") or "") for k in keywords)
            else 1
        ),
    )

    for item in ranked:
        if len(points) >= 30:
            break
        uri = _uri_of(item)
        if not uri or uri in seen_uris:
            continue
        detail_resp = client.building_detail(uri)
        if not detail_resp.ok or not isinstance(detail_resp.data, dict):
            continue
        detail = detail_resp.data.get("data")
        if not isinstance(detail, dict):
            detail = detail_resp.data
        if not isinstance(detail, dict):
            continue
        name = str(detail.get("name") or _name_of(item))
        lat, lng = _coords(detail)
        if lat is None or lng is None:
            # still allow with schematic fallback near Wukang
            lat, lng = 31.2145, 121.4465
            coord_source = "manual"
            precision = "schematic"
        else:
            coord_source = "upstream"
            precision = "approximate"
        wid = f"wl-{next_id:03d}"
        next_id += 1
        points.append(
            _point_shell(
                id_=wid,
                name=name,
                buri=uri,
                lat=lat,
                lng=lng,
                coord_source=coord_source,
                precision=precision,
                district_tag="梧桐区",
            )
        )
        seen_uris.add(uri)

    # Pad to 30 with schematic neighborhood anchors if upstream thin
    pad_names = [
        ("武康路口意象点", 31.2140, 121.4460, "梧桐区"),
        ("华山路梧桐意象点", 31.2132, 121.4418, "梧桐区"),
        ("衡山路转角意象点", 31.2108, 121.4475, "梧桐区"),
        ("复兴西路意象点", 31.2125, 121.4502, "梧桐区"),
        ("安福路意象点", 31.2188, 121.4485, "梧桐区"),
        ("乌鲁木齐中路意象点", 31.2175, 121.4430, "梧桐区"),
        ("湖南路意象点", 31.2158, 121.4490, "梧桐区"),
        ("天平路意象点", 31.2115, 121.4448, "梧桐区"),
        ("桃江路意象点", 31.2098, 121.4495, "梧桐区"),
        ("永嘉路意象点", 31.2088, 121.4520, "梧桐区"),
        ("嘉善路意象点", 31.2102, 121.4555, "梧桐区"),
        ("陕西南路意象点", 31.2165, 121.4568, "梧桐区"),
        ("茂名南路意象点", 31.2180, 121.4605, "梧桐区"),
        ("瑞金二路意象点", 31.2195, 121.4638, "一大周边"),
        ("淡水路意象点", 31.2210, 121.4672, "一大周边"),
        ("马当路意象点", 31.2202, 121.4688, "一大周边"),
        ("顺昌路意象点", 31.2230, 121.4725, "一大周边"),
        ("自忠路意象点", 31.2212, 121.4740, "一大周边"),
    ]
    for name, lat, lng, district in pad_names:
        if len(points) >= 30:
            break
        wid = f"wl-{next_id:03d}"
        next_id += 1
        points.append(
            _point_shell(
                id_=wid,
                name=name,
                buri=None,
                lat=lat,
                lng=lng,
                coord_source="manual",
                precision="schematic",
                district_tag=district,
                photo_spot="人行道外侧，勿影响交通",
            )
        )

    points = points[:30]
    payload = {
        "version": "1.0",
        "scope": "梧桐区 + 一大周边",
        "count": len(points),
        "generated_at": TODAY,
        "notes": [
            "NG-10: 渲染只读 lat/lng/precision，不按 coord_source 分叉业务逻辑",
            "buri 为空 = 诚实未映射；叙事不得编造上游事件",
            "避坑四字段禁止推测：未知一律「未收录」",
        ],
        "points": points,
    }

    points_path = out_dir / "points.json"
    with points_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")

    buri_map = {
        "version": "1.0",
        "mapped": [
            {"id": p["id"], "name": p["name"], "buri": p["buri"]}
            for p in points
            if p.get("buri")
        ],
        "unmapped": [
            {"id": p["id"], "name": p["name"], "reason": "暂无数据支撑"}
            for p in points
            if not p.get("buri")
        ],
    }
    map_path = out_dir / "buri-map.json"
    with map_path.open("w", encoding="utf-8") as f:
        json.dump(buri_map, f, ensure_ascii=False, indent=2)
        f.write("\n")

    mapped = len(buri_map["mapped"])
    print(f"points={len(points)} mapped_buri={mapped} unmapped={len(points) - mapped}")
    print(f"wrote {points_path}")
    print(f"wrote {map_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
