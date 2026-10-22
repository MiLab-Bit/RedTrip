from __future__ import annotations

import hashlib
import json
import os
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[3]  # RedTrip/
sys.path.insert(0, str(ROOT / "packages" / "library-client"))
sys.path.insert(0, str(ROOT / "packages" / "curator"))
sys.path.insert(0, str(ROOT / "packages" / "gate"))
load_dotenv(ROOT / ".env")
os.environ.setdefault("PYTHONUTF8", "1")

from redtrip_curator import curate as run_curator  # noqa: E402
from redtrip_curator.llm import (  # noqa: E402
    clear_thread_provider,
    set_thread_provider,
)
from redtrip_library import SlcClient, SlcResponse, bbox_from_points  # noqa: E402

# 鉴权层（与 auth_router 同包，但 main.py 只读不解耦）
from app import auth_lib as _auth_lib  # noqa: E402
from app import auth_store as _auth_store  # noqa: E402

# FIXTURE_PATH 已彻底拆除——demo-route.json 不再作为降级产物使用。
WHITELIST_PATH = ROOT / "content" / "whitelist" / "points.json"
HOTWORDS_PATH = ROOT / "content" / "hotwords" / "latest.json"
DEMO_WUKANG_PATH = ROOT / "content" / "fixtures" / "demo-route.json"
DEMO_YIDA_PATH = ROOT / "content" / "fixtures" / "demo-route-yida.json"


def _hotwords_health() -> dict[str, Any]:
    """L3 热词新鲜度：竞赛演示期超过 14 天标 stale。"""
    from datetime import date, datetime

    if not HOTWORDS_PATH.exists():
        return {"ok": False, "present": False, "stale": True, "week": None}
    try:
        data = json.loads(HOTWORDS_PATH.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "present": True, "stale": True, "error": str(exc)}
    week = data.get("week")
    updated = str(data.get("updated_at") or "")
    stale = True
    age_days: int | None = None
    try:
        d = datetime.strptime(updated[:10], "%Y-%m-%d").date()
        age_days = (date.today() - d).days
        stale = age_days > 14
    except ValueError:
        stale = True
    entries = data.get("entries") if isinstance(data.get("entries"), list) else []
    return {
        "ok": not stale and len(entries) >= 8,
        "present": True,
        "stale": stale,
        "week": week,
        "updated_at": updated,
        "age_days": age_days,
        "entries": len(entries),
    }


class IntentSlots(BaseModel):
    audience: str | None = None
    scene: str | None = None
    duration_min: int | None = None
    tone: str | None = None
    delivery: str | None = None
    companions: str | None = None
    daypart: str | None = None  # day | night | full | suburb
    city: str | None = None     # 策展城市 key（见 redtrip_curator.cities.CITY_REGISTRY）


class CurateRequest(BaseModel):
    message: str | None = None
    slots: IntentSlots | None = None
    retry_count: int = Field(default=0, ge=0)


class GateMeta(BaseModel):
    passed: bool
    warnings: list[str] = Field(default_factory=list)


class HongyuanSlot(BaseModel):
    category: str
    id: str
    label: str
    hint: str


class HongyuanHotword(BaseModel):
    id: str
    term: str
    places: list[str] = Field(default_factory=list)
    hint: str = ""
    heat: float | None = None
    week: str | None = None
    score: float | None = None


class HongyuanMeta(BaseModel):
    agent: str = "红鸢"
    seed: int | None = None
    summary: str | None = None
    emotion: HongyuanSlot | None = None
    voice_style: HongyuanSlot | None = None
    narrative: HongyuanSlot | None = None
    knowledge_angle: HongyuanSlot | None = None
    pacing: HongyuanSlot | None = None
    lexicon_size: dict[str, int] | None = None
    layer3_week: str | None = None
    layer3_summary: str | None = None
    layer3: list[HongyuanHotword] = Field(default_factory=list)
    rag_layers: list[str] = Field(default_factory=list)


class CurateMeta(BaseModel):
    latency_ms: int | None = None
    assumptions: list[str] = Field(default_factory=list)
    mode: Literal["snapshot", "indexed", "mcp"] = "snapshot"
    evidence_count: int | None = None
    narrative: Literal["template", "llm_polish"] | None = None
    hongyuan: HongyuanMeta | None = None
    gate: GateMeta | None = None


class CurateResponse(BaseModel):
    # status 语义：
    #   ok       真策展成功（含 Gate 通过的完整 envelope）；
    #   degraded 真策展完成但 Gate 拦下部分内容（envelope 仍可用，前端按降级态提示）；
    #   error    任何后端异常（envelope=None，绝不返回 fixture / demo 兜底）。
    status: Literal["ok", "degraded", "error"]
    phase: Literal["skeleton", "full"] | None = None
    envelope: dict[str, Any] | None = None
    # G2: 四个一等公民中间产物（Theme / EvidenceGraph / NarrativeArc / Provenance）
    artifacts: dict[str, Any] | None = None
    # Always emit [] — Zod optional() rejects JSON null from Pydantic None.
    reasons: list[str] = Field(default_factory=list)
    meta: CurateMeta | None = None


# ---------------------------------------------------------------------------
# 方案 B：场景指纹缓存（文件级、带 TTL、线程安全、零依赖）
# 仅缓存「indexed 成功」路径的整份策展结果；重复/相似查询 <2s，并直接对冲
# LLM 网关 60–100s 的延迟波动。逻辑变更时把 CACHE_SCHEMA 抬高即可全量失效。
# ---------------------------------------------------------------------------
CACHE_FILE = ROOT / ".curate_cache.json"
CACHE_TTL_S = int(os.getenv("REDTRIP_CACHE_TTL_S", "86400"))  # 默认 24h
CACHE_MAX = int(os.getenv("REDTRIP_CACHE_MAX", "200"))
CACHE_SCHEMA = "v2"


def _compute_code_version() -> str:
    """按核心代码/语料内容哈希，缓存随部署自动失效（替代手动 bump CACHE_SCHEMA）。

    任一核心模块或语料文件变更都会改变哈希，旧缓存指纹自然失效；
    不再需要部署后手动 bump 常量或删除 .curate_cache.json。
    """
    files = [
        ROOT / "packages" / "curator" / "redtrip_curator" / "pipeline.py",
        ROOT / "packages" / "curator" / "redtrip_curator" / "evidence.py",
        ROOT / "packages" / "curator" / "redtrip_curator" / "storycraft.py",
        ROOT / "packages" / "curator" / "redtrip_curator" / "polish.py",
        ROOT / "packages" / "curator" / "redtrip_curator" / "proposition.py",
        ROOT / "packages" / "curator" / "redtrip_curator" / "artifacts.py",
        ROOT / "packages" / "curator" / "redtrip_curator" / "corpus" / "geonames.json",
        ROOT / "packages" / "curator" / "redtrip_curator" / "corpus" / "literary.json",
        ROOT / "packages" / "library-client" / "redtrip_library" / "amap.py",
        ROOT / "content" / "whitelist" / "points.json",
        ROOT / "packages" / "gate" / "redtrip_gate" / "engine.py",
    ]
    h = hashlib.sha256()
    for f in files:
        try:
            h.update(f.read_bytes())
        except FileNotFoundError:
            h.update(b"missing")
    return h.hexdigest()[:16]


CODE_VERSION = _compute_code_version()

_cache_lock = threading.Lock()
_cache_mem: dict[str, dict] = {}
_cache_stats: dict[str, int] = {"hits": 0, "misses": 0}


def _cache_load() -> None:
    global _cache_mem
    try:
        with CACHE_FILE.open(encoding="utf-8") as f:
            _cache_mem = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        _cache_mem = {}


def _cache_save() -> None:
    tmp = CACHE_FILE.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(_cache_mem, f, ensure_ascii=False)
    tmp.replace(CACHE_FILE)  # 原子替换，避免并发/崩溃损坏


def _provider_cache_key(provider: dict[str, str] | None) -> str:
    """BYOK 与默认环境模型必须分桶，避免串缓存。"""
    if not provider:
        return "env-default"
    base = (provider.get("api_base") or "").strip().lower()
    model = (provider.get("model") or "").strip().lower()
    pid = (provider.get("id") or provider.get("name") or "").strip().lower()
    raw = f"{pid}|{base}|{model}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _fingerprint(
    req: CurateRequest,
    mode: str,
    provider: dict[str, str] | None = None,
) -> str:
    norm = {
        "schema": CACHE_SCHEMA,
        "code": CODE_VERSION,
        "mode": mode,
        "message": (req.message or "").strip().lower(),
        "slots": req.slots.model_dump() if req.slots else None,
        "retry": req.retry_count,
        "llm": _provider_cache_key(provider),
    }
    s = json.dumps(norm, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _cache_get(fp: str) -> dict | None:
    with _cache_lock:
        entry = _cache_mem.get(fp)
        if not entry:
            return None
        if time.time() - entry.get("ts", 0) > CACHE_TTL_S:
            _cache_mem.pop(fp, None)
            return None
        return entry.get("payload")


def _cache_put(fp: str, payload: dict) -> None:
    with _cache_lock:
        _cache_mem[fp] = {"ts": time.time(), "payload": payload}
        if len(_cache_mem) > CACHE_MAX:
            oldest = sorted(_cache_mem.items(), key=lambda kv: kv[1]["ts"])
            for k, _ in oldest[: len(_cache_mem) - CACHE_MAX]:
                _cache_mem.pop(k, None)
        _cache_save()


_cache_load()

app = FastAPI(title="RedTrip API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _assumptions_from_slots(slots: IntentSlots | None) -> list[str]:
    # 完全本地推导：不读任何 fixture / demo 兜底。
    assumptions: list[str] = []
    if not slots:
        assumptions.append("未提供槽位 → 全量默认假设")
        return assumptions
    if not slots.audience:
        assumptions.append("出题未填人群 → 沿用成人")
    if not slots.tone:
        assumptions.append("出题未填调性 → 沿用轻社交")
    return assumptions


def _active_llm_provider_from_request(request: Request) -> dict[str, str] | None:
    """从请求的 Bearer token 解析用户，并返回 DB 中 active 的 LLM provider。

    优先 text 槽；若无则回落 multimodal（同为 OpenAI 兼容 chat）。
    无 token / 无 active provider / 解密失败 → 返回 None，回落到环境变量。
    """
    auth_header = request.headers.get("Authorization") or ""
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header[7:]
    secret = (
        os.getenv("REDTRIP_AUTH_SECRET", "").strip()
        or os.getenv("AUTH_JWT_SECRET", "").strip()
    )
    if not secret:
        return None
    payload = _auth_lib.decode_token(token, secret, expect_typ="access")
    if not payload:
        return None
    uid = payload.get("sub")
    if not uid:
        return None
    # 旧 JWT 无 typ/ver 时仍可能 decode；再核对 token_version
    try:
        ver = int(payload.get("ver", 0) or 0)
        if ver != _auth_store.get_token_version(uid):
            return None
    except Exception:
        return None
    return (
        _auth_store.get_active_provider(uid, "text")
        or _auth_store.get_active_provider(uid, "multimodal")
    )

def _probe_live_providers(client: SlcClient) -> tuple[dict[str, bool], dict[str, Any]]:
    """实际访问 live provider；只有本次成功才可标记 ready。"""
    slc = client.health_probe()
    souyun = client.poem("上海")
    results = {
        "slc": bool(slc.get("ok")),
        "souyun": bool(souyun.ok and souyun.data is not None),
    }
    details = {
        "slc": slc,
        "souyun": souyun.summary(),
    }
    return results, details


def _load_demo_fixture(
    path: Path,
    *,
    label: str,
    theme_check: str,
) -> CurateResponse:
    if not path.exists():
        return CurateResponse(
            status="error",
            reasons=[f"演示线 fixture 缺失：{path.relative_to(ROOT)}"],
        )
    raw = json.loads(path.read_text(encoding="utf-8"))
    hongyuan_raw = raw.pop("_demo_hongyuan", None)
    hongyuan = None
    if isinstance(hongyuan_raw, dict):
        try:
            hongyuan = HongyuanMeta.model_validate(hongyuan_raw)
        except Exception:  # noqa: BLE001
            hongyuan = HongyuanMeta(
                agent="红鸢",
                summary=str(hongyuan_raw.get("summary") or "红鸢演示读法"),
            )
    assumptions = list(raw.get("assumptions") or [])
    assumptions = list(dict.fromkeys([*assumptions, f"演示线={label}", "模式=冻结包"]))
    if theme_check and theme_check not in str(raw.get("theme") or ""):
        return CurateResponse(
            status="error",
            reasons=[f"演示线主题校验失败：期望含「{theme_check}」"],
        )
    return CurateResponse(
        status="ok",
        phase="full",
        envelope=raw,
        reasons=[],
        meta=CurateMeta(
            latency_ms=0,
            assumptions=assumptions,
            mode="snapshot",
            evidence_count=len((raw.get("route") or {}).get("stops") or []),
            narrative="template",
            hongyuan=hongyuan,
            gate=GateMeta(passed=True, warnings=[]),
        ),
    )


def _slc_payload(resp: SlcResponse) -> dict[str, Any]:
    return {
        "ok": resp.ok,
        "status": resp.status,
        "endpoint": resp.endpoint,
        "error": resp.error,
        "data": resp.data,
    }


class FootprintRequest(BaseModel):
    points: list[dict[str, float]] = Field(default_factory=list)


def _load_osm_fixture() -> dict[str, Any] | None:
    fixture = ROOT / "content" / "fixtures" / "osm-wukang.json"
    if not fixture.exists():
        return None
    with fixture.open(encoding="utf-8") as f:
        cached = json.load(f)
    if not cached.get("features"):
        return None
    return cached


def _clip_features_to_bbox(
    features: list[dict[str, Any]],
    *,
    south: float,
    west: float,
    north: float,
    east: float,
) -> list[dict[str, Any]]:
    """Keep polygons whose centroid falls inside the corridor bbox."""
    kept: list[dict[str, Any]] = []
    for f in features:
        geom = f.get("geometry") or {}
        ring = (geom.get("coordinates") or [[]])[0]
        if not ring:
            continue
        lats: list[float] = []
        lngs: list[float] = []
        for c in ring:
            if not isinstance(c, (list, tuple)) or len(c) < 2:
                continue
            lngs.append(float(c[0]))
            lats.append(float(c[1]))
        if not lats:
            continue
        clat = sum(lats) / len(lats)
        clng = sum(lngs) / len(lngs)
        if south <= clat <= north and west <= clng <= east:
            kept.append(f)
    return kept


def _fixture_for_bbox(
    *,
    south: float,
    west: float,
    north: float,
    east: float,
) -> dict[str, Any] | None:
    cached = _load_osm_fixture()
    if not cached:
        return None
    feats = _clip_features_to_bbox(
        list(cached.get("features") or []),
        south=south,
        west=west,
        north=north,
        east=east,
    )
    # If clip too aggressive (route slightly off), widen pad once.
    if len(feats) < 12:
        pad_s, pad_w, pad_n, pad_e = bbox_from_points(
            [
                (south, west),
                (north, east),
            ],
            pad=0.0035,
        )
        feats = _clip_features_to_bbox(
            list(cached.get("features") or []),
            south=pad_s,
            west=pad_w,
            north=pad_n,
            east=pad_e,
        )
    if not feats:
        return None
    return {
        "type": "FeatureCollection",
        "features": feats,
        "source": "fixture:osm-wukang",
        "live": False,
        "count": len(feats),
    }


# _snapshot_response 已彻底删除——任何路径不再返回 demo fixture。


def _run_curate_sync(req: CurateRequest, *, provider: dict[str, str] | None) -> CurateResponse:
    """同步策展核心：被 /v1/curate 与 /v1/book 共用。"""
    started = time.perf_counter()
    mode = os.getenv("REDTRIP_MODE", "indexed")
    if mode == "snapshot":
        return _error_response(
            req, started,
            reasons=["REDTRIP_MODE=snapshot 已被禁用：请改为 indexed"],
        )

    try:
        fp = _fingerprint(req, mode, provider)
        hit = _cache_get(fp)
        if hit is not None:
            _cache_stats["hits"] += 1
            latency = int((time.perf_counter() - started) * 1000)
            resp = CurateResponse.model_validate(hit)
            resp.meta.latency_ms = latency
            resp.reasons = ["缓存命中（场景指纹命中，跳过 LLM/SLC 取证）"]
            return resp
        _cache_stats["misses"] += 1

        slots = req.slots.model_dump() if req.slots else None
        set_thread_provider(provider)
        try:
            result = run_curator(
                slots=slots,
                message=req.message,
                client=SlcClient(),
                retry_count=req.retry_count,
            )
            latency = int((time.perf_counter() - started) * 1000)
            if result.ok and result.envelope:
                degraded = bool(getattr(result, "degraded", False)) or (
                    not bool(getattr(result, "gate_passed", True))
                )
                resp = CurateResponse(
                    status="degraded" if degraded else "ok",
                    phase="full",
                    envelope=result.envelope,
                    artifacts=(
                        result.artifacts.to_dict() if result.artifacts else None
                    ),
                    meta=CurateMeta(
                        latency_ms=latency,
                        assumptions=result.assumptions,
                        mode="indexed",
                        evidence_count=result.evidence_count,
                        narrative=result.narrative,
                        hongyuan=(
                            HongyuanMeta.model_validate(result.hongyuan)
                            if result.hongyuan
                            else None
                        ),
                        gate=GateMeta(
                            passed=not degraded,
                            warnings=result.warnings,
                        ),
                    ),
                )
                # 仅缓存 Gate 通过的完整结果；降级不入缓存，避免把失败态当成功复用
                if not degraded:
                    _cache_put(fp, resp.model_dump(exclude_none=True))
                return resp

            return _error_response(
                req, started,
                reasons=[
                    "策展未通过：未生成可用 envelope",
                    *result.reasons,
                    *result.warnings,
                ],
            )
        finally:
            clear_thread_provider()
    except Exception as exc:  # noqa: BLE001
        return _error_response(
            req, started,
            reasons=[f"curator 异常（不再降级为 demo）: {exc}"],
            exception_msg=str(exc),
        )


def _error_response(
    req: CurateRequest,
    started: float,
    *,
    reasons: list[str],
    exception_msg: str | None = None,
) -> CurateResponse:
    """统一失败响应：envelope=None、status=error，绝不装载 demo / fixture。"""
    return CurateResponse(
        status="error",
        envelope=None,
        reasons=reasons,
        meta=CurateMeta(
            latency_ms=int((time.perf_counter() - started) * 1000),
            assumptions=_assumptions_from_slots(req.slots),
            mode="indexed",
            gate=GateMeta(
                passed=False,
                warnings=[exception_msg] if exception_msg else ["curate error"],
            ),
        ),
    )


# ─────────────────────────────────────────────────────────────────────────────
# P0：/v1/curate 异步化 + SSE 实时进度
#   POST /v1/curate/start       → 提交任务，立即返回 {task_id}
#   GET  /v1/curate/stream/{id} → SSE 推送真实进度（替代前端假进度）
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class _CurateTask:
    task_id: str
    status: str = "pending"            # pending | running | done | error
    progress: float = 0.0
    stage: str = ""
    message: str = ""
    ok: bool | None = None
    result: dict | None = None
    error: str | None = None
    created_at: float = 0.0
    updated_at: float = 0.0
    # B4 章节级流式：模板 envelope 先交付（story_ready），逐卡润色完成
    # 追加进 chapters（chapter_ready）。stream 端用游标增量推送，done 仍带全量。
    story_ready: dict | None = None
    chapters: list = field(default_factory=list)


_curate_tasks: dict[str, _CurateTask] = {}
_curate_tasks_lock = threading.Lock()
_curate_fp_index: dict[str, str] = {}  # 场景指纹 → task_id，用于请求去重（Bug #4）


def _evict_tasks() -> None:
    """淘汰已完成/出错且超过 1h 的任务并限制总数，防止内存泄漏（Bug #5）。"""
    now = time.time()
    expired = [
        tid
        for tid, t in _curate_tasks.items()
        if t.status in ("done", "error") and t.updated_at and now - t.updated_at > 3600
    ]
    for tid in expired:
        _curate_tasks.pop(tid, None)
        for fp, ref in list(_curate_fp_index.items()):
            if ref == tid:
                _curate_fp_index.pop(fp, None)
    if len(_curate_tasks) > CACHE_MAX:
        oldest = sorted(_curate_tasks.items(), key=lambda kv: kv[1].updated_at)
        for tid, _ in oldest[: len(_curate_tasks) - CACHE_MAX]:
            _curate_tasks.pop(tid, None)


def _make_progress_cb(task: _CurateTask):
    def _cb(stage: str, progress: float, message: str = "") -> None:
        with _curate_tasks_lock:
            task.stage = stage
            task.message = message
            task.progress = progress
            if task.status == "pending":
                task.status = "running"
            task.updated_at = time.time()
    return _cb


def _run_curate_bg(
    task: _CurateTask, req: CurateRequest, fp: str,
    provider: dict[str, str] | None = None,
) -> None:
    started = time.perf_counter()
    set_thread_provider(provider)

    def _on_event(name: str, data: dict) -> None:
        """B4：story_ready / chapter_ready 事件写入 task，供 SSE 增量推送。"""
        with _curate_tasks_lock:
            if name == "story_ready":
                task.story_ready = data
            elif name == "chapter_ready":
                task.chapters.append(data)
            task.updated_at = time.time()

    try:
        slots = req.slots.model_dump() if req.slots else None
        result = run_curator(
            slots=slots,
            message=req.message,
            client=SlcClient(),
            retry_count=req.retry_count,
            on_progress=_make_progress_cb(task),
            on_event=_on_event,
        )
        latency = int((time.perf_counter() - started) * 1000)
        if result.ok and result.envelope:
            degraded = bool(getattr(result, "degraded", False)) or (
                not bool(getattr(result, "gate_passed", True))
            )
            resp = CurateResponse(
                status="degraded" if degraded else "ok",
                phase="full",
                envelope=result.envelope,
                artifacts=(
                    result.artifacts.to_dict() if result.artifacts else None
                ),
                meta=CurateMeta(
                    latency_ms=latency,
                    assumptions=result.assumptions,
                    mode="indexed",
                    evidence_count=result.evidence_count,
                    narrative=result.narrative,
                    hongyuan=(
                        HongyuanMeta.model_validate(result.hongyuan)
                        if result.hongyuan
                        else None
                    ),
                    gate=GateMeta(
                        passed=not degraded,
                        warnings=result.warnings,
                    ),
                ),
            )
            # 异步路径：仅缓存 Gate 通过结果，降级不伪装成功入缓存
            if not degraded:
                _cache_put(fp, resp.model_dump(exclude_none=True))
        else:
            # Indexed 失败 → envelope=None 的 error 响应写入 task.result
            # （彻底拆除 demo fixture 兜底，前端不再可能看到「巴金故居 demo」）
            resp = _error_response(
                req,
                started,
                reasons=[
                    "策展未通过：未生成可用 envelope",
                    *result.reasons,
                    *result.warnings,
                ],
            )
        with _curate_tasks_lock:
            task.status = "done"
            task.ok = result.ok
            task.result = resp.model_dump(exclude_none=True)
            task.progress = 100.0
            task.stage = "done"
            task.message = "策展完成"
            task.updated_at = time.time()
            _curate_fp_index.pop(fp, None)  # 完成后解除去重占用（Bug #4）
    except Exception as exc:  # noqa: BLE001
        with _curate_tasks_lock:
            task.status = "error"
            task.error = str(exc)
            task.progress = 100.0
            task.stage = "error"
            task.message = f"策展异常：{exc}"
            task.updated_at = time.time()
            _curate_fp_index.pop(fp, None)
    finally:
        clear_thread_provider()


class CurateStartResponse(BaseModel):
    task_id: str
    status: str = "pending"


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# ── 路由拆分（2026-10）：按域挂载，处理器见 app/routers/ ──
from app.routers import (  # noqa: E402
    curate,
    demo,
    gate,
    health,
    llm,
    map,
    slc,
    sources,
)

app.include_router(health.router)
app.include_router(demo.router)
app.include_router(slc.router)
app.include_router(llm.router)
app.include_router(map.router)
app.include_router(sources.router)
app.include_router(gate.router)
app.include_router(curate.router)
# ── RedTrip 通用登录系统（接替 auth-core，#27）──
# auth_router 挂载前缀 /v1：/v1/auth/* 公开，/v1/me、/v1/model-providers/* 需 Bearer。
# try/except 包裹：依赖（httpx / cryptography）缺失或密钥目录不可写时，应用照常启动，
# 仅打印警告——与服务器备份版 main.py 的挂载写法保持一致。
try:
    from app.auth_router import router as _auth_router
    if os.getenv("REDTRIP_AUTH_ENABLED", "true").lower() == "false":
        print("[auth] login system DISABLED via REDTRIP_AUTH_ENABLED=false (code retained)")
    else:
        app.include_router(_auth_router)
        print("[auth] unified login router mounted")
except Exception as _auth_err:  # noqa: BLE001
    print(f"[auth] WARNING: failed to mount auth router: {_auth_err}")
