"""RedTrip 密钥加解密 — Fernet（AES-128 + HMAC）。

用户自带的大模型 API Key 在落库前加密，读取时解密用于调用供应商。
密钥文件持久化在 data 目录，权限受限；缺失时自动生成。
"""
from __future__ import annotations

import os
from pathlib import Path

from cryptography.fernet import Fernet

_KEY_PATH = os.environ.get("REDTRIP_CRYPTO_KEY_PATH") or str(
    Path(__file__).resolve().parents[3] / "data" / ".crypto_key"
)


def _load_key() -> bytes:
    p = Path(_KEY_PATH)
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists():
        return p.read_bytes().strip()
    key = Fernet.generate_key()
    p.write_bytes(key)
    try:
        os.chmod(_KEY_PATH, 0o600)
    except OSError:
        pass
    return key


_FERNET = Fernet(_load_key())


def encrypt(plaintext: str) -> str:
    return _FERNET.encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt(token: str) -> str:
    return _FERNET.decrypt(token.encode("utf-8")).decode("utf-8")


# ── 常见大模型供应商预设（仅展示用，不含任何密钥）──
PROVIDER_PRESETS = [
    {"provider": "openai", "label": "OpenAI", "baseUrl": "https://api.openai.com/v1", "defaultModel": "gpt-4o-mini"},
    {"provider": "anthropic", "label": "Anthropic", "baseUrl": "https://api.anthropic.com/v1", "defaultModel": "claude-3-5-sonnet-latest"},
    {"provider": "deepseek", "label": "DeepSeek", "baseUrl": "https://api.deepseek.com/v1", "defaultModel": "deepseek-chat"},
    {"provider": "moonshot", "label": "Moonshot 月之暗面", "baseUrl": "https://api.moonshot.cn/v1", "defaultModel": "moonshot-v1-8k"},
    {"provider": "qwen", "label": "通义千问", "baseUrl": "https://dashscope.aliyuncs.com/compatible-mode/v1", "defaultModel": "qwen-plus"},
    {"provider": "zhipu", "label": "智谱 GLM", "baseUrl": "https://open.bigmodel.cn/api/paas/v4", "defaultModel": "glm-4-flash"},
    {"provider": "ollama", "label": "Ollama（本地）", "baseUrl": "http://localhost:11434/v1", "defaultModel": "llama3.1"},
    {"provider": "custom", "label": "自定义 / 兼容 OpenAI", "baseUrl": "", "defaultModel": ""},
]
