"""单一阈值真相源（Plan / Gate 共用）。

P0-1 根因：规划器（plan.py）按档位产出 4h→8 站 / 8h→10 站 / 24h→12 站，
且 `_cap = max(120, intent.duration_min)`；而门禁（engine.py）硬拦 `n>10` 与
`duration>120`。两者各写一套阈值 → 凡 >2h 的真实 Citywalk 请求都会被门禁打回，
pipeline 静默回退到模板，LLM 海派润色根本到不了用户面前（"电子垃圾"成因）。

修复：规划器与门禁都只读这里的常量，谁都不准再硬编码。调阈值只改这一处。
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class PlanEnvelope:
    min_stops: int = 5          # 路线最少站点（步行连贯性下限）
    warn_max_stops: int = 8     # 建议上限：超过仅告警，不阻断
    max_stops: int = 12         # 硬上限：25h(24h) 档位满档
    min_duration_min: int = 30  # 路线最短时长
    max_duration_min: int = 480  # 最长 8h（24h 档位封顶），正常 3–4h walk 都能过


PLAN_ENVELOPE = PlanEnvelope()
