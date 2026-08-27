from types import SimpleNamespace

from app import main


def test_sync_curate_exposes_gate_fallback_as_degraded(monkeypatch):
    monkeypatch.setenv("REDTRIP_MODE", "indexed")
    result = SimpleNamespace(
        ok=True,
        degraded=True,
        gate_passed=False,
        envelope={"envelope_version": "1.0"},
        artifacts=None,
        assumptions=[],
        evidence_count=3,
        narrative="template",
        hongyuan=None,
        reasons=[],
        warnings=["Q8: 示例阻断项"],
    )
    monkeypatch.setattr(main, "run_curator", lambda **_: result)
    monkeypatch.setattr(main, "_cache_get", lambda _: None)
    monkeypatch.setattr(main, "_cache_put", lambda *_: None)

    response = main._run_curate_sync(main.CurateRequest(message="测试"), provider=None)

    assert response.status == "degraded"
    assert response.meta.gate.passed is False
    assert "Q8: 示例阻断项" in response.meta.gate.warnings
