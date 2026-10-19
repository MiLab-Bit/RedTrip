"""RedTrip LLM 每日配额测试 — 不调 LLM（urllib.build_opener 打桩，返回假响应）。

配额门位于 chat_completion 入口（_quota_gate）；BYOK（带 api_key）跳过，平台网关超限抛
RuntimeError（proposition/polish 已 catch 降级）。curate 无强制认证，scope 默认 anon（全局）。

运行（仓库根）：
    venv/bin/python -m pytest tests/test_llm_quota.py -q
"""
from __future__ import annotations

import json
import sys

import pytest

sys.path.insert(0, "/opt/redtrip/packages")
sys.path.insert(0, "/opt/shared")

import redtrip_curator.llm as llm  # noqa: E402
from redtrip_curator.llm import chat_completion, set_llm_scope  # noqa: E402


@pytest.fixture()
def fake_http(monkeypatch, tmp_path):
    """真实 chat_completion + _quota_gate 执行；仅 urllib HTTP 被替换。"""
    calls: list = []

    class _Resp:
        def read(self):
            return json.dumps({"choices": [{"message": {"content": "ok"}}]}).encode()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    class _Opener:
        def __init__(self, *a, **k):
            pass

        def open(self, req, *args, **kwargs):
            calls.append(getattr(req, "full_url", None))
            return _Resp()

    monkeypatch.setenv("LLM_API_BASE", "http://x")
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("LLM_MODEL", "m")
    monkeypatch.setattr(llm.urllib.request, "build_opener", lambda *a, **k: _Opener())
    monkeypatch.setenv("REDTRIP_QUOTA_DB", str(tmp_path / "q.db"))
    return calls


def test_exhausted_raises(fake_http):
    set_llm_scope("anon")
    for _ in range(3):
        assert chat_completion(system="s", user="u") == "ok"
    with pytest.raises(RuntimeError):
        chat_completion(system="s", user="u")
    assert len(fake_http) == 3  # 第 4 次被配额门拦截，零 HTTP


def test_byok_skips_quota(fake_http):
    set_llm_scope("anon")
    for _ in range(3):
        assert chat_completion(system="s", user="u") == "ok"
    out = chat_completion(
        system="s", user="u",
        provider={"api_base": "http://own", "api_key": "own", "model": "m"},
    )
    assert out == "ok"
    assert len(fake_http) == 4  # BYOK 不计平台额度，仍放行


def test_quota_env_unlimited(fake_http, monkeypatch):
    monkeypatch.setenv("LLM_QUOTA_LIMIT", "0")
    set_llm_scope("anon")
    for i in range(5):
        assert chat_completion(system="s", user=f"u{i}") == "ok"
    assert len(fake_http) == 5
