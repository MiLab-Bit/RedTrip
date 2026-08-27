from __future__ import annotations

from typing import Any

from .cities import get_city
from .models import Intent

DEFAULTS = {
    "audience": "成人",
    "scene": "武康路—华山路一带",
    "duration_min": 90,
    "tone": "轻社交",
    "delivery": "路线",
    "companions": "2人",
    "daypart": "day",
    "city": "shanghai",
}


def parse_intent(
    slots: dict[str, Any] | None,
    message: str | None = None,
) -> Intent:
    slots = slots or {}
    filled = 0
    assumptions: list[str] = []
    values: dict[str, Any] = {}

    for key, default in DEFAULTS.items():
        raw = slots.get(key)
        if raw is None or raw == "":
            values[key] = default
            if key != "city":  # 城市有默认上海，不必作为「未填」假设暴露给用户
                assumptions.append(f"未填{key} → 默认{default}")
        else:
            values[key] = raw
            filled += 1

    # 缺 ≥3 本应追问 1 问；API 演示路径直接用默认并声明
    if filled <= 3 and not assumptions:
        assumptions.append("槽位较少 → 已按默认假设补全")

    duration = values["duration_min"]
    try:
        duration_min = int(duration)
    except (TypeError, ValueError):
        duration_min = 90
        assumptions.append("时长无法解析 → 默认90")

    # 档位放开：45min ~ 24h（1440）。之前 clamp 到 120 导致 4h/8h/24h 全失效。
    duration_min = max(45, min(1440, duration_min))

    daypart = str(values["daypart"] or "day")
    if daypart not in ("day", "night", "full", "suburb"):
        daypart = "day"

    # city 会拼进语料文件名：必须经白名单 + 注册表，非法回退 shanghai
    city_key = get_city(str(values.get("city") or "")).key

    return Intent(
        audience=str(values["audience"]),
        scene=str(values["scene"]),
        duration_min=duration_min,
        tone=str(values["tone"]),
        delivery=str(values["delivery"]),
        companions=str(values["companions"]),
        assumptions=assumptions,
        message=message,
        daypart=daypart,
        city=city_key,
    )


def companions_enum(companions: str) -> str:
    if companions in ("独自", "solo", "1人"):
        return "solo"
    if companions in ("3–4人", "3-4人", "小团体", "small_group"):
        return "small_group"
    return "duo"
