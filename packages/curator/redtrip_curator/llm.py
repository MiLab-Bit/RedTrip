"""Minimal OpenAI-compatible chat client (stdlib only).

支持「混合路由」：通过 REDTRIP_LLM_POLICY 选择云端 / 本地小模型 / 二者混合。
- 云端：abc-ai.cn 网关（Qwen-flash），质量高、但并发仅 ~2 路、延迟波动大。
- 本地：ollama 暴露的 OpenAI 兼容端点（默认 127.0.0.1:11434），零网络、
  可预测，适合把「结构化抽取」类子调用从云端网关卸载下来。
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
import urllib.error
import urllib.request
from typing import Any

_LOGGER = logging.getLogger("redtrip.llm")

# 线程级 LLM provider 覆盖：API 进程在调用 curator 前，可以把用户通过
# UI 配置并落入 DB 的 active provider 注入当前线程，让原本只读环境变量的
# llm.py 也能使用用户自带密钥（Bug #1）。
_THREAD_PROVIDER = threading.local()


def set_thread_provider(provider: dict[str, str] | None) -> None:
    """为当前线程设置/cloud/provider 覆盖（API → curator 桥接）。

    provider 格式：{"api_base": str, "api_key": str, "model": str}。
    传 None 等价于清除覆盖。
    """
    if not provider:
        _THREAD_PROVIDER.cloud = None
        return
    _THREAD_PROVIDER.cloud = {
        "api_base": (provider.get("api_base") or "").strip(),
        "api_key": (provider.get("api_key") or "").strip(),
        "model": (provider.get("model") or "").strip(),
    }


def clear_thread_provider() -> None:
    """清除当前线程的 provider 覆盖。"""
    _THREAD_PROVIDER.cloud = None


def _thread_provider() -> dict[str, str] | None:
    p = getattr(_THREAD_PROVIDER, "cloud", None)
    if not p:
        return None
    if not (p.get("api_base") and p.get("api_key")):
        return None
    return p


def _env_int(name: str, default: int | None) -> int | None:
    v = os.getenv(name)
    if not v:
        return default
    try:
        return int(v)
    except ValueError:
        return default


def llm_configured() -> bool:
    p = _thread_provider()
    if p:
        return bool(p["api_base"] and p["api_key"])
    base = (os.getenv("LLM_API_BASE") or "").strip()
    key = (os.getenv("LLM_API_KEY") or "").strip()
    return bool(base and key)


def llm_model() -> str:
    p = _thread_provider()
    if p and p["model"]:
        return p["model"]
    return (os.getenv("LLM_MODEL") or "Qwen-flash").strip()


def chat_completion(
    *,
    system: str,
    user: str,
    temperature: float = 0.4,
    timeout: float | None = None,
    max_tokens: int | None = None,
    provider: dict[str, str] | None = None,
) -> str:
    """Return assistant text content. Raises on hard failure.

    provider: 显式传入 {api_base, api_key, model} 覆盖当前线程/环境变量配置。
              用于 API 把用户 DB 中的 active provider 桥接到 curator。
    """
    # 优先级：显式 provider > 线程覆盖 > 环境变量
    if provider and provider.get("api_base") and provider.get("api_key"):
        base = str(provider["api_base"]).rstrip("/")
        key = str(provider["api_key"]).strip()
        model = (provider.get("model") or "").strip() or (os.getenv("LLM_MODEL") or "Qwen-flash").strip()
    elif _thread_provider():
        p = _thread_provider()
        base = p["api_base"].rstrip("/")
        key = p["api_key"]
        model = p["model"] or (os.getenv("LLM_MODEL") or "Qwen-flash").strip()
    else:
        if not llm_configured():
            raise RuntimeError("LLM not configured")
        base = (os.getenv("LLM_API_BASE") or "").rstrip("/")
        key = (os.getenv("LLM_API_KEY") or "").strip()
        model = (os.getenv("LLM_MODEL") or "Qwen-flash").strip()
    timeout = timeout or float(os.getenv("LLM_TIMEOUT_S", "180"))

    url = f"{base}/chat/completions"
    payload: dict[str, Any] = {
        "model": model,
        "temperature": temperature,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "response_format": {"type": "json_object"},
    }
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Bearer {key}",
            "Accept": "application/json",
            "User-Agent": "RedTrip-Curator/0.1",
        },
    )
    try:
        # Force direct connection: local Clash proxy (7897) often breaks the
        # LLM host (same convention as SlcClient). Host is CN-side anyway.
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({})
        )
        with opener.open(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:400]
        raise RuntimeError(f"LLM HTTP {e.code}: {body}") from e
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f"LLM request failed: {e}") from e

    try:
        parsed: dict[str, Any] = json.loads(raw)
    except json.JSONDecodeError as e:
        raise RuntimeError("LLM response is not JSON") from e

    choices = parsed.get("choices") or []
    if not choices:
        raise RuntimeError("LLM response missing choices")
    msg = choices[0].get("message") or {}
    content = msg.get("content")
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("LLM response missing content")
    return content.strip()


def _parse_json_object(text: str) -> dict[str, Any]:
    """Tolerate fenced ```json blocks; enforce object root."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.startswith("json"):
            cleaned = cleaned[4:].strip()
    try:
        obj = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"LLM content is not a JSON object: {cleaned[:200]}") from e
    if not isinstance(obj, dict):
        raise RuntimeError("LLM JSON root must be an object")
    return obj


def local_llm_configured() -> bool:
    """本地小模型是否可用：需要配置 BASE 与 MODEL 且端点可达。"""
    base = (os.getenv("LOCAL_LLM_BASE") or "").strip()
    model = (os.getenv("LOCAL_LLM_MODEL") or "").strip()
    if not (base and model):
        return False
    return _local_reachable()


def _local_reachable() -> bool:
    base = (os.getenv("LOCAL_LLM_BASE") or "http://127.0.0.1:11434/v1").rstrip("/")
    # 用 ollama 原生 /api/tags 探活（比 /v1/models 更稳）
    native = base.replace("/v1", "") or "http://127.0.0.1:11434"
    try:
        req = urllib.request.Request(
            f"{native}/api/tags", method="GET",
            headers={"User-Agent": "RedTrip-Curator/0.1-local"},
        )
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(req, timeout=2.0) as resp:
            return resp.status == 200
    except Exception:  # noqa: BLE001
        return False


def _local_completion(
    *,
    system: str,
    user: str,
    temperature: float = 0.4,
    timeout: float | None = None,
    max_tokens: int | None = None,
) -> str:
    """本地 ollama OpenAI 兼容端点。Raises on hard failure."""
    base = (os.getenv("LOCAL_LLM_BASE") or "http://127.0.0.1:11434/v1").rstrip("/")
    model = (os.getenv("LOCAL_LLM_MODEL") or "qwen2.5:1.5b").strip()
    api_key = (os.getenv("LOCAL_LLM_API_KEY") or "ollama").strip()
    timeout = timeout or float(os.getenv("LOCAL_LLM_TIMEOUT_S", "90"))
    # 本地小模型仅承接结构化抽取（hybrid 策略下 structured→[local,cloud]），
    # 由 proposition.py 显式传 max_tokens 做安全封顶；不再读 LOCAL_LLM_MAX_TOKENS
    # 做全局截断（会误伤创意成品）。
    max_tokens = max_tokens

    url = f"{base}/chat/completions"
    payload: dict[str, Any] = {
        "model": model,
        "temperature": temperature,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "response_format": {"type": "json_object"},
    }
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "User-Agent": "RedTrip-Curator/0.1-local",
        },
    )
    try:
        # 本地端点同样强制直连（避免误走代理）
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:400]
        raise RuntimeError(f"local LLM HTTP {e.code}: {body}") from e
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f"local LLM request failed: {e}") from e

    try:
        parsed: dict[str, Any] = json.loads(raw)
    except json.JSONDecodeError as e:
        raise RuntimeError("local LLM response is not JSON") from e
    choices = parsed.get("choices") or []
    if not choices:
        raise RuntimeError("local LLM response missing choices")
    content = (choices[0].get("message") or {}).get("content")
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("local LLM response missing content")
    return content.strip()


def _resolve_backend_order(*, backend: str, role: str) -> list[str]:
    """根据策略解析后端尝试顺序。

    REDTRIP_LLM_POLICY:
      - cloud  (默认): 全部走云端
      - hybrid : 结构化(structured)→[本地, 云端]；创意(creative)→云端(失败由 pipeline 回退模板)
      - local  : 全部→[本地, 云端]（离线/兜底）
    """
    policy = (os.getenv("REDTRIP_LLM_POLICY") or "cloud").lower()
    if backend == "cloud":
        return ["cloud"]
    if backend == "local":
        return ["local"]
    # backend == "auto"
    if policy == "local":
        return ["local", "cloud"]
    if policy == "hybrid":
        return ["local", "cloud"] if role == "structured" else ["cloud"]
    return ["cloud"]


def chat_json(
    *,
    system: str,
    user: str,
    temperature: float = 0.35,
    backend: str = "cloud",
    role: str = "structured",
    timeout: float | None = None,
    max_tokens: int | None = None,
    provider: dict[str, str] | None = None,
) -> dict[str, Any]:
    """带混合路由的 JSON 调用。

    backend: "cloud"(默认, 旧行为) | "local" | "auto"(按策略)。
    role:    "structured"(命题分解/红队/溯源) | "creative"(润色)。
    任一后端失败自动尝试下一个；全部失败则抛错（由调用方回退）。

    provider: 显式 {api_base, api_key, model} 覆盖（用于 API 把用户 DB 的
              active provider 桥接到 curator）。不传则沿用线程级覆盖
              （set_thread_provider）或环境变量（Bug #1 修复的两条路径）。
    """
    order = _resolve_backend_order(backend=backend, role=role)
    last_exc: Exception | None = None
    for b in order:
        if b == "local" and not local_llm_configured():
            continue
        t0 = time.perf_counter()
        try:
            if b == "cloud":
                text = chat_completion(
                    system=system, user=user, temperature=temperature,
                    timeout=timeout, max_tokens=max_tokens, provider=provider,
                )
            else:
                text = _local_completion(
                    system=system, user=user, temperature=temperature,
                    timeout=timeout, max_tokens=max_tokens,
                )
            obj = _parse_json_object(text)
            _LOGGER.warning(
                "LLM route backend=%s role=%s t=%.1fs",
                b, role, time.perf_counter() - t0,
            )
            return obj
        except Exception as e:  # noqa: BLE001
            last_exc = e
            _LOGGER.warning("LLM route backend=%s role=%s failed: %s", b, role, e)
            continue
    if last_exc:
        raise last_exc
    raise RuntimeError(f"no LLM backend available (policy={order})")
