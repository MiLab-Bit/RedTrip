from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from redtrip_gate import evaluate_envelope

router = APIRouter()


@router.get("/v1/gate/check")
def gate_check(envelope: dict[str, Any]) -> dict[str, Any]:
    """Evaluate a RouteEnvelope against publish blockers (debug / CI)."""
    return evaluate_envelope(envelope).as_dict()
