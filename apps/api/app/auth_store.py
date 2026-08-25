"""RedTrip 鉴权数据层 — SQLite（与 Cardio 同范式）。

表：users / email_verifications / api_keys。
机器凭证前缀 rt_；user.id 即 JWT sub 与数据 owner。
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path

DB_PATH = os.environ.get("REDTRIP_DB_PATH") or str(
    Path(__file__).resolve().parents[3] / "data" / "redtrip.db"
)


def _now() -> str:
    return str(int(time.time()))


def _connect() -> sqlite3.Connection:
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    _migrate(conn)
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            name TEXT,
            password_hash TEXT NOT NULL,
            email_verified INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'active',
            avatar_url TEXT,
            roles TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS email_verifications (
            token_hash TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            purpose TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS api_keys (
            id TEXT PRIMARY KEY,
            owner_id TEXT NOT NULL,
            name TEXT NOT NULL,
            key_hash TEXT NOT NULL,
            prefix TEXT NOT NULL,
            scopes TEXT NOT NULL DEFAULT '[]',
            status TEXT NOT NULL DEFAULT 'active',
            last_used_at TEXT,
            created_at TEXT NOT NULL,
            revoked_at TEXT
        );
        CREATE TABLE IF NOT EXISTS model_providers (
            id TEXT PRIMARY KEY,
            owner_id TEXT NOT NULL,
            name TEXT NOT NULL,
            provider TEXT NOT NULL,
            api_key_enc TEXT NOT NULL,
            base_url TEXT,
            model TEXT,
            slot TEXT NOT NULL DEFAULT 'text',
            status TEXT NOT NULL DEFAULT 'unverified',
            last_error TEXT,
            last_tested_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_owner ON api_keys(owner_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_model_providers_owner ON model_providers(owner_id)")
    # 双模型槽位迁移：旧库补 slot 列（已存在则静默跳过）
    try:
        conn.execute(
            "ALTER TABLE model_providers ADD COLUMN slot TEXT NOT NULL DEFAULT 'text'"
        )
    except sqlite3.OperationalError:
        pass
    conn.commit()


def _public_user(u: dict) -> dict:
    """输出与前端 AuthUser 对齐的 camelCase 结构（不含 email）。"""
    return {
        "publicId": u["id"],
        "nickname": u["name"],
        "avatarUrl": u["avatar_url"],
        "status": u["status"],
        "emailVerified": bool(u["email_verified"]),
        "roles": json.loads(u["roles"] or "[]"),
        "createdAt": int(u["created_at"]),
    }


# ── users ──
def create_user(email: str, password_hash: str, name: str = "") -> str | None:
    uid = os.urandom(16).hex()
    try:
        with _connect() as c:
            c.execute(
                "INSERT INTO users (id,email,name,password_hash,created_at) VALUES (?,?,?,?,?)",
                (uid, email.lower().strip(), name or "", password_hash, _now()),
            )
    except sqlite3.IntegrityError:
        return None
    return uid


def verify_user(email: str, password: str):
    with _connect() as c:
        r = c.execute(
            "SELECT id,password_hash FROM users WHERE email=?", (email.lower().strip(),)
        ).fetchone()
    if not r:
        return None
    return r["id"], r["password_hash"]


def get_user(uid: str) -> dict | None:
    with _connect() as c:
        r = c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    return dict(r) if r else None


def get_user_by_email(email: str) -> dict | None:
    with _connect() as c:
        r = c.execute("SELECT * FROM users WHERE email=?", (email.lower().strip(),)).fetchone()
    return dict(r) if r else None


def set_email_verified(uid: str) -> None:
    with _connect() as c:
        c.execute("UPDATE users SET email_verified=1 WHERE id=?", (uid,))


def set_password(uid: str, password_hash: str) -> None:
    with _connect() as c:
        c.execute("UPDATE users SET password_hash=? WHERE id=?", (password_hash, uid))


# ── email_verifications（验证邮件 + 密码重置共用，purpose 区分）──
def save_verify_token(token_hash: str, uid: str, purpose: str, expires_at: str) -> None:
    with _connect() as c:
        c.execute(
            "INSERT OR REPLACE INTO email_verifications "
            "(token_hash,user_id,purpose,expires_at,created_at) VALUES (?,?,?,?,?)",
            (token_hash, uid, purpose, expires_at, _now()),
        )


def get_verify_token(token_hash: str) -> dict | None:
    with _connect() as c:
        r = c.execute(
            "SELECT * FROM email_verifications WHERE token_hash=?", (token_hash,)
        ).fetchone()
    return dict(r) if r else None


def delete_verify_token(token_hash: str) -> None:
    with _connect() as c:
        c.execute("DELETE FROM email_verifications WHERE token_hash=?", (token_hash,))


# ── api_keys（机器凭证）──
def create_api_key(owner_id: str, name: str, key_hash: str, prefix: str, scopes: list) -> str:
    kid = os.urandom(16).hex()
    with _connect() as c:
        c.execute(
            "INSERT INTO api_keys (id,owner_id,name,key_hash,prefix,scopes,created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (kid, owner_id, name, key_hash, prefix, json.dumps(scopes), _now()),
        )
    return kid


def list_api_keys(owner_id: str) -> list[dict]:
    with _connect() as c:
        rows = c.execute(
            "SELECT id,name,prefix,scopes,status,last_used_at,created_at,revoked_at "
            "FROM api_keys WHERE owner_id=?",
            (owner_id,),
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["scopes"] = json.loads(d["scopes"] or "[]")
        out.append(d)
    return out


def get_api_key_by_hash(key_hash: str) -> dict | None:
    with _connect() as c:
        r = c.execute(
            "SELECT id,owner_id,status,scopes FROM api_keys WHERE key_hash=?", (key_hash,)
        ).fetchone()
    return dict(r) if r else None


def rotate_api_key(key_id: str, owner_id: str, key_hash: str, prefix: str) -> bool:
    with _connect() as c:
        cur = c.execute(
            "UPDATE api_keys SET key_hash=?, prefix=?, status='active', revoked_at=NULL "
            "WHERE id=? AND owner_id=?",
            (key_hash, prefix, key_id, owner_id),
        )
        return cur.rowcount > 0


def revoke_api_key(key_id: str, owner_id: str) -> bool:
    with _connect() as c:
        cur = c.execute(
            "UPDATE api_keys SET status='revoked', revoked_at=? WHERE id=? AND owner_id=?",
            (_now(), key_id, owner_id),
        )
        return cur.rowcount > 0


def touch_api_key(key_id: str) -> None:
    with _connect() as c:
        c.execute("UPDATE api_keys SET last_used_at=? WHERE id=?", (_now(), key_id))


# ── model_providers（用户自带大模型密钥，加密存储；支持 text/multimodal 双槽）──
def create_model_provider(owner_id: str, name: str, provider: str, api_key_enc: str,
                          base_url: str | None, model: str | None,
                          slot: str = "text") -> str:
    if slot not in ("text", "multimodal"):
        slot = "text"
    pid = os.urandom(16).hex()
    now = _now()
    with _connect() as c:
        c.execute(
            "INSERT INTO model_providers "
            "(id,owner_id,name,provider,api_key_enc,base_url,model,slot,status,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (pid, owner_id, name, provider, api_key_enc, base_url, model, slot,
             "unverified", now, now),
        )
    return pid


def list_model_providers(owner_id: str) -> list[dict]:
    with _connect() as c:
        rows = c.execute(
            "SELECT id,name,provider,base_url,model,slot,status,last_error,last_tested_at,created_at "
            "FROM model_providers WHERE owner_id=? ORDER BY slot, created_at DESC",
            (owner_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_model_provider(pid: str, owner_id: str) -> dict | None:
    with _connect() as c:
        r = c.execute(
            "SELECT * FROM model_providers WHERE id=? AND owner_id=?", (pid, owner_id)
        ).fetchone()
    return dict(r) if r else None


def get_active_provider(owner_id: str, slot: str = "text") -> dict | None:
    """返回该 owner 在某槽位的 active provider（解密 api_key）。无则返回 None。

    返回结构：{api_base, api_key, model, provider, name, id}。
    """
    if slot not in ("text", "multimodal"):
        slot = "text"
    from app import crypto  # 仅此处按需导入，避免模块级循环

    with _connect() as c:
        r = c.execute(
            "SELECT * FROM model_providers WHERE owner_id=? AND slot=? AND status='active' "
            "ORDER BY updated_at DESC LIMIT 1",
            (owner_id, slot),
        ).fetchone()
    if not r:
        return None
    row = dict(r)
    api_base = row.get("base_url") or _preset_base(row.get("provider", ""))
    try:
        api_key = crypto.decrypt(row["api_key_enc"])
    except Exception:  # noqa: BLE001
        return None
    return {
        "id": row["id"],
        "name": row.get("name"),
        "provider": row.get("provider"),
        "api_base": api_base,
        "api_key": api_key,
        "model": row.get("model"),
    }


def get_active_model_provider(owner_id: str) -> dict | None:
    """兼容别名：默认取 text 槽。"""
    return get_active_provider(owner_id, "text")


def _preset_base(provider: str) -> str | None:
    from app import crypto

    for pr in crypto.PROVIDER_PRESETS:
        if pr["provider"] == provider:
            return pr["baseUrl"]
    return None


def get_model_provider_by_owner(pid: str, owner_id: str) -> dict | None:
    return get_model_provider(pid, owner_id)


def update_model_provider_status(pid: str, owner_id: str, status: str,
                                 last_error: str | None, last_tested_at: str) -> None:
    with _connect() as c:
        c.execute(
            "UPDATE model_providers SET status=?, last_error=?, last_tested_at=?, updated_at=? "
            "WHERE id=? AND owner_id=?",
            (status, last_error, last_tested_at, _now(), pid, owner_id),
        )


def delete_model_provider(pid: str, owner_id: str) -> bool:
    with _connect() as c:
        cur = c.execute("DELETE FROM model_providers WHERE id=? AND owner_id=?", (pid, owner_id))
        return cur.rowcount > 0
