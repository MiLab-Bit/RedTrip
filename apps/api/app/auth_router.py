"""RedTrip 鉴权路由 — 复刻 auth-core 契约，前端零改动。

挂载前缀 /v1：/v1/auth/* 公开；/v/me、/v1/apikeys/* 需 Bearer。
完成 #27：RedTrip 自身承载鉴权，停用独立 auth-core。
"""
from __future__ import annotations

import json
import os
import smtplib
import ssl
import time
from email.message import EmailMessage

import httpx
from fastapi import APIRouter, HTTPException, Request

from app import auth_lib as auth
from app import auth_store as store
from app import crypto as crypto

router = APIRouter(prefix="/v1")

SHARED_SMTP = "/opt/shared/smtp_config.json"
ACCESS_TTL = 60 * 60 * 24 * 7
REFRESH_TTL = 60 * 60 * 24 * 30


def _secret() -> str:
    s = (
        os.environ.get("REDTRIP_AUTH_SECRET", "").strip()
        or os.environ.get("AUTH_JWT_SECRET", "").strip()
    )
    if not s:
        raise HTTPException(500, "REDTRIP_AUTH_SECRET 未配置")
    return s


def _require_verified() -> bool:
    return str(os.environ.get("REDTRIP_AUTH_REQUIRE_VERIFIED", "true")).lower() != "false"


def _email_base() -> str:
    return os.environ.get(
        "REDTRIP_EMAIL_BASE_URL", "https://sy-realm.ltd/redtrip"
    ).rstrip("/")


def _email_ttl() -> int:
    return int(os.environ.get("REDTRIP_EMAIL_TOKEN_TTL", "86400"))


def _send_email(to: str, subject: str, text: str) -> bool:
    """读共享 SMTP 配置发信；无配置或失败返回 False（单用户系统降级处理）。"""
    try:
        with open(SHARED_SMTP, "r", encoding="utf-8") as f:
            data = json.load(f)
        s = data.get("smtp") or data
        if not (s.get("host") and s.get("username")):
            raise ValueError("no smtp config")
    except Exception:
        # 不打印正文（可能含验证/重置 token）
        print(f"[mail:noop] -> {to} | {subject} | body_len={len(text)}")
        return False
    msg = EmailMessage()
    msg["From"] = s["from"]
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(text)
    ctx = ssl.create_default_context()
    try:
        enc = s.get("encryption", "ssl")
        if enc == "tls":
            with smtplib.SMTP(s["host"], int(s.get("port", 587)), timeout=15) as m:
                m.starttls(ctx)
                m.login(s["username"], s["password"])
                m.send_message(msg)
        else:
            with smtplib.SMTP_SSL(s["host"], int(s.get("port", 465)), context=ctx, timeout=15) as m:
                m.login(s["username"], s["password"])
                m.send_message(msg)
    except Exception as exc:  # noqa: BLE001
        print(f"[mail:error] -> {to} | {exc}")
        return False
    return True


def _current_user(request: Request) -> dict:
    h = request.headers.get("Authorization", "")
    if not h.startswith("Bearer "):
        raise HTTPException(401, "missing token")
    payload = auth.decode_token(h[7:], _secret(), expect_typ="access")
    if not payload:
        raise HTTPException(401, "invalid token")
    uid = payload.get("sub")
    u = store.get_user(uid) if uid else None
    if not u:
        raise HTTPException(401, "user gone")
    if u.get("status") == "disabled":
        raise HTTPException(403, "账号已停用")
    ver = int(payload.get("ver", 0) or 0)
    if ver != store.get_token_version(uid):
        raise HTTPException(401, "token 已失效，请重新登录")
    return payload


def _issue_pair(uid: str, email: str) -> dict:
    sec = _secret()
    ver = store.get_token_version(uid)
    at = auth.issue_token(uid, email, sec, ACCESS_TTL, typ="access", token_version=ver)
    rt = auth.issue_token(uid, email, sec, REFRESH_TTL, typ="refresh", token_version=ver)
    return {
        "accessToken": at,
        "refreshToken": rt,
        "expiresIn": ACCESS_TTL,
        "user": store._public_user(store.get_user(uid)),
    }


def _public(uid: str) -> dict:
    u = store.get_user(uid)
    if not u:
        raise HTTPException(401, "user gone")
    return store._public_user(u)


# 注意：不再在此路由定义 /health —— main.py 已有 @app.get("/v1/health")，
# 挂载后若重复注册同路径（GET /v1/health）会引发路由冲突。
# （服务器原版带此端点，但从未真正挂载，冲突从未暴露。）

@router.post("/auth/register")
async def register(request: Request) -> dict:
    body = await request.json()
    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""
    nickname = (body.get("nickname") or "").strip()
    if "@" not in email or len(password) < 8:
        raise HTTPException(400, "邮箱格式或密码长度(>=8)不合法")
    if store.get_user_by_email(email):
        raise HTTPException(409, "邮箱已注册")
    uid = store.create_user(email, auth.hash_password(password), nickname)
    if not uid:
        raise HTTPException(409, "邮箱已注册")
    tok = auth.make_verify_token()
    exp = str(int(time.time()) + _email_ttl())
    store.save_verify_token(auth.hash_token(tok), uid, "verify_email", exp)
    link = f"{_email_base()}/verify-email?token={tok}"
    ok = _send_email(email, "RedTrip 邮箱验证", f"欢迎注册 RedTrip。请点击验证：\n{link}\n（24 小时内有效）")
    if not ok:
        # 不再降级自动激活：避免未持有邮箱即可注册
        print(f"[auth] 注册邮件发送失败，账号保持未验证 {email}")
        return {
            "user": store._public_user(store.get_user(uid)),
            "emailSent": False,
            "message": "账号已创建，但验证邮件发送失败。请稍后使用「重发验证邮件」或联系管理员。",
        }
    u = store.get_user(uid)
    return {"user": store._public_user(u), "emailSent": True}


@router.post("/auth/verify-email")
async def verify_email(request: Request) -> dict:
    body = await request.json()
    token = (body.get("token") or request.query_params.get("token") or "").strip()
    rec = store.get_verify_token(auth.hash_token(token))
    if not rec:
        raise HTTPException(400, "无效或已过期的验证链接")
    if rec["purpose"] != "verify_email":
        raise HTTPException(400, "token 用途不符")
    if int(rec["expires_at"]) < int(time.time()):
        store.delete_verify_token(auth.hash_token(token))
        raise HTTPException(400, "验证链接已过期")
    store.set_email_verified(rec["user_id"])
    store.delete_verify_token(auth.hash_token(token))
    return {"user": _public(rec["user_id"])}


@router.post("/auth/resend-verification")
async def resend(request: Request) -> dict:
    body = await request.json()
    email = (body.get("email") or "").strip().lower()
    u = store.get_user_by_email(email)
    if not u:
        raise HTTPException(404, "邮箱不存在")
    if u["email_verified"]:
        raise HTTPException(400, "已验证")
    tok = auth.make_verify_token()
    store.save_verify_token(
        auth.hash_token(tok), u["id"], "verify_email", str(int(time.time()) + _email_ttl())
    )
    ok = _send_email(email, "RedTrip 邮箱验证", f"{_email_base()}/verify-email?token={tok}")
    if not ok:
        raise HTTPException(503, "验证邮件发送失败，请稍后重试")
    return {"ok": True}


@router.post("/auth/login")
async def login(request: Request) -> dict:
    body = await request.json()
    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""
    r = store.verify_user(email, password)
    if not r:
        raise HTTPException(401, "邮箱或密码错误")
    uid, phash = r
    if not auth.verify_password(phash, password):
        raise HTTPException(401, "邮箱或密码错误")
    u = store.get_user(uid)
    if u.get("status") == "disabled":
        raise HTTPException(403, "账号已停用")
    if _require_verified() and not u["email_verified"]:
        raise HTTPException(403, "邮箱未验证，请查收验证邮件")
    return _issue_pair(uid, email)


@router.post("/auth/refresh")
async def refresh(request: Request) -> dict:
    body = await request.json()
    rt = body.get("refreshToken") or ""
    payload = auth.decode_token(rt, _secret(), expect_typ="refresh")
    if not payload:
        raise HTTPException(401, "refresh token 无效")
    uid = payload.get("sub")
    email = payload.get("email")
    u = store.get_user(uid)
    if not u:
        raise HTTPException(401, "用户不存在")
    if u.get("status") == "disabled":
        raise HTTPException(403, "账号已停用")
    ver = int(payload.get("ver", 0) or 0)
    if ver != store.get_token_version(uid):
        raise HTTPException(401, "token 已失效，请重新登录")
    return _issue_pair(uid, email)


@router.post("/auth/logout")
async def logout(request: Request) -> dict:
    """登出：递增 token_version，使 access/refresh 全部失效。"""
    try:
        p = _current_user(request)
        store.bump_token_version(p["sub"])
    except HTTPException:
        # 无 token / 已失效也视为登出成功
        pass
    return {"ok": True}


@router.post("/auth/request-password-reset")
async def request_reset(request: Request) -> dict:
    body = await request.json()
    email = (body.get("email") or "").strip().lower()
    u = store.get_user_by_email(email)
    if u:
        tok = auth.make_verify_token()
        store.save_verify_token(
            auth.hash_token(tok),
            u["id"],
            "reset_password",
            str(int(time.time()) + _email_ttl()),
        )
        ok = _send_email(
            email, "RedTrip 密码重置", f"{_email_base()}/reset-password?token={tok}"
        )
        if not ok:
            print(f"[auth] 密码重置邮件发送失败 {email}")
    return {"ok": True, "message": "若邮箱存在，重置链接已发送"}


@router.post("/auth/reset-password")
async def reset_password(request: Request) -> dict:
    body = await request.json()
    token = (body.get("token") or "").strip()
    npw = body.get("newPassword") or ""
    if len(npw) < 8:
        raise HTTPException(400, "密码长度需>=8")
    rec = store.get_verify_token(auth.hash_token(token))
    if not rec or rec["purpose"] != "reset_password":
        raise HTTPException(400, "无效 token")
    if int(rec["expires_at"]) < int(time.time()):
        store.delete_verify_token(auth.hash_token(token))
        raise HTTPException(400, "链接已过期")
    store.set_password(rec["user_id"], auth.hash_password(npw))
    store.delete_verify_token(auth.hash_token(token))
    store.bump_token_version(rec["user_id"])
    return {"ok": True}


@router.get("/me")
def me(request: Request) -> dict:
    p = _current_user(request)
    return {"user": _public(p["sub"])}


@router.get("/me/permissions")
def permissions(request: Request) -> dict:
    _current_user(request)
    return {"permissions": []}


@router.get("/apikeys")
def list_keys(request: Request) -> dict:
    p = _current_user(request)
    return {"status": "ok", "keys": store.list_api_keys(p["sub"])}


@router.post("/apikeys")
async def create_key(request: Request) -> dict:
    p = _current_user(request)
    body = await request.json()
    name = (body.get("name") or "untitled")
    scopes = body.get("scopes") or []
    plain, prefix, kh = auth.generate_api_key("rt_")
    kid = store.create_api_key(p["sub"], name, kh, prefix, scopes)
    return {"status": "ok", "key": plain, "id": kid, "prefix": prefix}


@router.post("/apikeys/rotate")
async def rotate_key(request: Request) -> dict:
    p = _current_user(request)
    body = await request.json()
    kid = body.get("id")
    plain, prefix, kh = auth.generate_api_key("rt_")
    if not store.rotate_api_key(kid, p["sub"], kh, prefix):
        raise HTTPException(404, "key 不存在")
    return {"status": "ok", "key": plain, "id": kid, "prefix": prefix}


@router.post("/apikeys/revoke")
async def revoke_key(request: Request) -> dict:
    p = _current_user(request)
    body = await request.json()
    kid = body.get("id")
    if not store.revoke_api_key(kid, p["sub"]):
        raise HTTPException(404, "key 不存在")
    return {"status": "ok"}


# ── 模型配置（用户自带大模型供应商密钥）──
def _blocked_base_url(base: str) -> str | None:
    """基础 SSRF 防护：禁止明显内网/元数据地址（Ollama localhost 例外）。"""
    from urllib.parse import urlparse

    try:
        u = urlparse(base)
    except Exception:
        return "Base URL 无效"
    host = (u.hostname or "").lower()
    if not host:
        return "Base URL 缺少主机名"
    if host in ("localhost", "127.0.0.1", "::1"):
        return None  # 允许本地 Ollama
    if host.endswith(".local") or host.endswith(".internal"):
        return "不允许访问内网主机"
    # 粗粒度私网/链路本地
    blocked_prefixes = (
        "10.", "192.168.", "169.254.", "0.", "100.64.",
    )
    if any(host.startswith(p) for p in blocked_prefixes):
        return "不允许访问私网地址"
    if host.startswith("172."):
        try:
            second = int(host.split(".")[1])
            if 16 <= second <= 31:
                return "不允许访问私网地址"
        except Exception:
            pass
    if u.scheme not in ("http", "https"):
        return "Base URL 仅支持 http/https"
    return None


def _test_provider(api_key: str, base_url: str, model: str, provider: str = "") -> dict:
    """直连供应商做一次最小 chat 调用，验证 key 可用。返回 {ok, latency_ms, model}。"""
    base = (base_url or "").rstrip("/")
    if not base:
        raise HTTPException(400, "自定义供应商需填写 Base URL")
    block = _blocked_base_url(base)
    if block:
        return {"ok": False, "latency_ms": 0, "error": block}
    # Anthropic 使用 /v1/messages 而非 OpenAI 兼容 /chat/completions，当前尚未接入。
    if provider == "anthropic" or "anthropic.com" in base:
        return {
            "ok": False,
            "latency_ms": 0,
            "error": "Anthropic 尚未支持，请选择 OpenAI/DeepSeek/通义千问等兼容供应商",
        }
    url = f"{base}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model or "gpt-4o-mini",
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 4,
        "temperature": 0,
    }
    t0 = time.time()
    try:
        with httpx.Client(timeout=20.0, follow_redirects=False) as cli:
            r = cli.post(url, headers=headers, json=payload)
        latency = int((time.time() - t0) * 1000)
        if r.status_code != 200:
            detail = r.text[:300]
            try:
                detail = r.json().get("error", {}).get("message", detail)
            except Exception:
                pass
            return {"ok": False, "latency_ms": latency, "error": f"HTTP {r.status_code}: {detail}"}
        try:
            body = r.json()
        except Exception:
            return {"ok": False, "latency_ms": latency, "error": "响应不是 JSON"}
        choices = body.get("choices") if isinstance(body, dict) else None
        if not choices:
            return {"ok": False, "latency_ms": latency, "error": "响应缺少 choices，可能不是 OpenAI 兼容接口"}
        return {"ok": True, "latency_ms": latency, "model": model or "gpt-4o-mini"}
    except Exception as exc:  # noqa: BLE001
        latency = int((time.time() - t0) * 1000)
        return {"ok": False, "latency_ms": latency, "error": str(exc)[:300]}


@router.get("/model-providers/presets")
def provider_presets() -> dict:
    """公开的供应商预设（不含任何密钥）。"""
    return {"providers": crypto.PROVIDER_PRESETS}


@router.get("/model-providers")
def list_providers(request: Request) -> dict:
    p = _current_user(request)
    return {"status": "ok", "providers": store.list_model_providers(p["sub"])}


@router.post("/model-providers")
async def create_provider(request: Request) -> dict:
    p = _current_user(request)
    body = await request.json()
    name = (body.get("name") or "").strip()
    provider = (body.get("provider") or "").strip()
    api_key = (body.get("apiKey") or "").strip()
    base_url = (body.get("baseUrl") or "").strip() or None
    model = (body.get("model") or "").strip() or None
    slot = (body.get("slot") or "text").strip()
    if slot not in ("text", "multimodal"):
        slot = "text"
    if not name or not provider or not api_key:
        raise HTTPException(400, "名称、供应商、密钥均为必填")
    # 保存前先验证
    test = _test_provider(
        api_key, base_url or _preset_base(provider), model or _preset_model(provider), provider=provider,
    )
    status = "active" if test["ok"] else "error"
    pid = store.create_model_provider(
        p["sub"], name, provider, crypto.encrypt(api_key), base_url, model, slot=slot
    )
    store.update_model_provider_status(
        pid, p["sub"], status, (test.get("error") if not test["ok"] else None),
        str(int(time.time())),
    )
    rec = store.get_model_provider(pid, p["sub"])
    rec.pop("api_key_enc", None)
    return {"status": "ok", "provider": rec, "test": test}


@router.post("/model-providers/test")
async def test_provider(request: Request) -> dict:
    _current_user(request)
    body = await request.json()
    provider = (body.get("provider") or "").strip()
    api_key = (body.get("apiKey") or "").strip()
    base_url = (body.get("baseUrl") or "").strip() or None
    model = (body.get("model") or "").strip() or None
    if not api_key:
        raise HTTPException(400, "请先填写密钥")
    return _test_provider(
        api_key, base_url or _preset_base(provider), model or _preset_model(provider), provider=provider,
    )


@router.post("/model-providers/{pid}/retest")
def retest_saved_provider(pid: str, request: Request) -> dict:
    """用库内已存密钥重测，并写回 active/error 状态。"""
    p = _current_user(request)
    rec = store.get_model_provider(pid, p["sub"])
    if not rec:
        raise HTTPException(404, "配置不存在")
    try:
        api_key = crypto.decrypt(rec["api_key_enc"])
    except Exception as exc:  # noqa: BLE001
        store.update_model_provider_status(
            pid, p["sub"], "error", f"解密失败: {exc}", str(int(time.time()))
        )
        raise HTTPException(400, "密钥解密失败，请重新保存配置") from exc
    base = rec.get("base_url") or _preset_base(rec.get("provider") or "")
    model = rec.get("model") or _preset_model(rec.get("provider") or "")
    test = _test_provider(api_key, base or "", model or "", provider=rec.get("provider") or "")
    status = "active" if test["ok"] else "error"
    store.update_model_provider_status(
        pid, p["sub"], status, (test.get("error") if not test["ok"] else None),
        str(int(time.time())),
    )
    out = store.get_model_provider(pid, p["sub"]) or {}
    out.pop("api_key_enc", None)
    return {"status": "ok", "provider": out, "test": test}


@router.delete("/model-providers/{pid}")
def delete_provider(pid: str, request: Request) -> dict:
    p = _current_user(request)
    if not store.delete_model_provider(pid, p["sub"]):
        raise HTTPException(404, "配置不存在")
    return {"status": "ok"}


def _preset_base(provider: str):
    for pr in crypto.PROVIDER_PRESETS:
        if pr["provider"] == provider:
            return pr["baseUrl"]
    return ""


def _preset_model(provider: str):
    for pr in crypto.PROVIDER_PRESETS:
        if pr["provider"] == provider:
            return pr["defaultModel"]
    return ""
