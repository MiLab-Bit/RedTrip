from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter
from redtrip_curator.llm import llm_configured, llm_model

router = APIRouter()


@router.get("/v1/llm/status")
def llm_status() -> dict[str, Any]:
    """LLM 网关是否已配置（不发起实际生成）。"""
    configured = llm_configured()
    return {
        "ok": configured,
        "configured": configured,
        "model": llm_model() if configured else None,
        "policy": os.getenv("REDTRIP_LLM_POLICY", "cloud"),
        "curate": "/v1/curate",
        "curate_async": "/v1/curate/start",
    }
