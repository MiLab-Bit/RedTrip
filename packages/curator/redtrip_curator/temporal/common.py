"""Temporal 跨边界数据类（纯 dataclass，JSON DataConverter 可序列化）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CurateInput:
    """策展工作流输入。"""
    slots: dict[str, Any] = field(default_factory=dict)
    message: str | None = None
    hongyuan_seed: int | None = None
    workflow_id: str | None = None


@dataclass
class CurateProgressEvent:
    """进度事件（写入 Workflow.progress，供 Query 轮询）。"""
    stage: str
    progress: float
    message: str = ""
