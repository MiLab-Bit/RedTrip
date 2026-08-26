"""llm.py 线程级 provider 覆盖测试：修复「UI 配置密钥不生效」Bug #1。

运行：.venv/Scripts/python.exe -m pytest tests/test_llm_provider.py -q
"""
from unittest.mock import patch

import pytest

from redtrip_curator.llm import (
    chat_completion,
    clear_thread_provider,
    llm_configured,
    llm_model,
    set_thread_provider,
)


@pytest.fixture(autouse=True)
def _clean_thread_provider():
    clear_thread_provider()
    yield
    clear_thread_provider()


def test_thread_provider_configures_llm():
    set_thread_provider({"api_base": "https://api.test/v1", "api_key": "sk-test", "model": "m-test"})
    assert llm_configured() is True
    assert llm_model() == "m-test"


def test_clear_thread_provider_falls_back():
    set_thread_provider({"api_base": "https://api.test/v1", "api_key": "sk-test"})
    clear_thread_provider()
    assert llm_configured() is False
    # 回落到环境变量默认值
    assert llm_model() == "Qwen-flash"


def test_explicit_provider_overrides_thread_and_env():
    set_thread_provider({"api_base": "https://thread.test/v1", "api_key": "sk-thread", "model": "m-thread"})
    with patch("redtrip_curator.llm.urllib.request.build_opener") as mock_build:
        mock_resp = mock_build.return_value.open.return_value.__enter__.return_value
        mock_resp.read.return_value = (
            '{"choices":[{"message":{"content":"hi"}}]}'.encode("utf-8")
        )
        chat_completion(
            system="s", user="u",
            provider={"api_base": "https://explicit.test/v1", "api_key": "sk-explicit", "model": "m-explicit"},
        )
        req = mock_build.return_value.open.call_args[0][0]
        assert req.get_full_url() == "https://explicit.test/v1/chat/completions"
        assert req.headers.get("Authorization") == "Bearer sk-explicit"


def test_thread_provider_propagates_to_executor():
    """ContextVar + copy_context 必须让线程池子任务看到 BYOK。"""
    from concurrent.futures import ThreadPoolExecutor

    from redtrip_curator.llm import submit_with_provider

    set_thread_provider({"api_base": "https://api.test/v1", "api_key": "sk-test", "model": "m-test"})

    def worker():
        return llm_configured(), llm_model()

    with ThreadPoolExecutor(max_workers=1) as pool:
        configured, model = submit_with_provider(pool, worker).result(timeout=5)
    assert configured is True
    assert model == "m-test"
