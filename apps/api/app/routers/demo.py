from __future__ import annotations

from fastapi import APIRouter

from app.main import (
    DEMO_WUKANG_PATH,
    DEMO_YIDA_PATH,
    CurateResponse,
    _load_demo_fixture,
)

router = APIRouter()


@router.get("/v1/demo/wukang", response_model=CurateResponse, response_model_exclude_none=True)
def demo_wukang() -> CurateResponse:
    """竞赛冻结演示线 A：显式一键加载武康，绝不作为普通 curate 失败兜底。"""
    return _load_demo_fixture(DEMO_WUKANG_PATH, label="武康冻结包", theme_check="武康")


@router.get("/v1/demo/yida", response_model=CurateResponse, response_model_exclude_none=True)
def demo_yida() -> CurateResponse:
    """竞赛冻结演示线 B：一大—外滩，诚实通道标注。"""
    return _load_demo_fixture(DEMO_YIDA_PATH, label="一大外滩冻结包", theme_check="外滩")
