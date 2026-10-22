from __future__ import annotations

import asyncio
import os
import threading
import time
import uuid

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from redtrip_curator.book import (
    render_book,
    render_book_epub_bytes,
    render_book_markdown,
    render_book_pdf,
)

from app.main import (
    CurateRequest,
    CurateResponse,
    CurateStartResponse,
    _active_llm_provider_from_request,
    _cache_get,
    _cache_stats,
    _curate_fp_index,
    _curate_tasks,
    _curate_tasks_lock,
    _CurateTask,
    _error_response,
    _evict_tasks,
    _fingerprint,
    _run_curate_bg,
    _run_curate_sync,
    _sse,
)

router = APIRouter()


@router.post("/v1/curate", response_model=CurateResponse, response_model_exclude_none=True)
def curate(req: CurateRequest, request: Request) -> CurateResponse:
    """真实策展。失败 → envelope=None 的 error 响应，绝不返回 demo / fixture 兜底。"""
    provider = _active_llm_provider_from_request(request)
    return _run_curate_sync(req, provider=provider)


@router.post("/v1/book")
def book(req: CurateRequest, request: Request):
    """策展并直接渲染为书籍 HTML。失败返回 JSON 错误（与 /v1/curate 同语义）。"""
    provider = _active_llm_provider_from_request(request)
    resp = _run_curate_sync(req, provider=provider)
    if resp.status == "ok" and resp.envelope:
        html = render_book(resp.envelope)
        return Response(content=html, media_type="text/html; charset=utf-8")
    return resp.model_dump(exclude_none=True)


@router.post("/v1/book/mdx")
def book_mdx(req: CurateRequest, request: Request):
    """策展并渲染为 MDX 兼容 Markdown。失败返回 JSON 错误。"""
    provider = _active_llm_provider_from_request(request)
    resp = _run_curate_sync(req, provider=provider)
    if resp.status == "ok" and resp.envelope:
        md = render_book_markdown(resp.envelope)
        return Response(content=md, media_type="text/markdown; charset=utf-8")
    return resp.model_dump(exclude_none=True)


@router.post("/v1/book/epub")
def book_epub(req: CurateRequest, request: Request):
    """策展并渲染为 EPUB（ZIP 字节）。失败返回 JSON 错误。"""
    provider = _active_llm_provider_from_request(request)
    resp = _run_curate_sync(req, provider=provider)
    if resp.status == "ok" and resp.envelope:
        data = render_book_epub_bytes(resp.envelope)
        return Response(content=data, media_type="application/epub+zip")
    return resp.model_dump(exclude_none=True)


@router.post("/v1/book/pdf")
def book_pdf(req: CurateRequest, request: Request):
    """策展并渲染为 PDF（best-effort：经 wkhtmltopdf；无则回退指南）。

    成功返回 application/pdf 字节；环境中无 wkhtmltopdf 时返回 JSON 错误，
    提示改用浏览器打开 /v1/book 的 HTML 后「打印 → 另存为 PDF」。
    """
    provider = _active_llm_provider_from_request(request)
    resp = _run_curate_sync(req, provider=provider)
    if resp.status != "ok" or not resp.envelope:
        return resp.model_dump(exclude_none=True)
    try:
        pdf = render_book_pdf(resp.envelope)
    except RuntimeError as exc:  # noqa: BLE001
        return _error_response(
            req, time.perf_counter(),
            reasons=[str(exc)],
            exception_msg=str(exc),
        )
    if pdf is None:
        return _error_response(
            req, time.perf_counter(),
            reasons=[
                "环境中无 wkhtmltopdf，无法服务端生成 PDF。"
                "请改用浏览器打开 /v1/book 返回的 HTML，使用「打印 → 另存为 PDF」"
                "（render_book 已含 @page A4 样式）。"
            ],
            exception_msg="wkhtmltopdf 未安装",
        )
    return Response(content=pdf, media_type="application/pdf")


@router.post("/v1/curate/start", response_model=CurateStartResponse)
def curate_start(req: CurateRequest, request: Request) -> CurateStartResponse:
    mode = os.getenv("REDTRIP_MODE", "indexed")
    provider = _active_llm_provider_from_request(request)
    fp = _fingerprint(req, mode, provider)

    # ① 缓存命中：直接构造已完成任务返回，SSE 立即推 done（Bug #4）
    hit = _cache_get(fp)
    if hit is not None:
        _cache_stats["hits"] += 1
        task_id = uuid.uuid4().hex
        task = _CurateTask(
            task_id=task_id,
            status="done",
            progress=100.0,
            stage="done",
            message="缓存命中（场景指纹命中，跳过 LLM/SLC 取证）",
            ok=True,
            result=hit,
            created_at=time.time(),
            updated_at=time.time(),
        )
        with _curate_tasks_lock:
            _curate_tasks[task_id] = task
            _evict_tasks()
        return CurateStartResponse(task_id=task_id)

    with _curate_tasks_lock:
        _cache_stats["misses"] += 1
        # ② 请求去重：相同指纹且有在途任务时复用，避免惊群打满网关（Bug #4）
        existing = _curate_fp_index.get(fp)
        if existing and existing in _curate_tasks:
            t = _curate_tasks[existing]
            if t.status in ("pending", "running"):
                return CurateStartResponse(task_id=existing)
        task_id = uuid.uuid4().hex
        task = _CurateTask(task_id=task_id, created_at=time.time(), updated_at=time.time())
        _curate_tasks[task_id] = task
        _curate_fp_index[fp] = task_id
        _evict_tasks()
    threading.Thread(target=_run_curate_bg, args=(task, req, fp, provider), daemon=True).start()
    return CurateStartResponse(task_id=task_id)


@router.get("/v1/curate/status/{task_id}")
def curate_status(task_id: str) -> dict:
    """轮询策展任务状态（微信小程序等无 EventSource 的客户端）。"""
    with _curate_tasks_lock:
        task = _curate_tasks.get(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="task not found")
        return {
            "task_id": task.task_id,
            "status": task.status,
            "progress": round(task.progress, 2),
            "stage": task.stage,
            "message": task.message,
            "ok": task.ok,
            "result": task.result if task.status == "done" else None,
            "error": task.error,
            "story_ready": task.story_ready,
            "chapters_ready": list(task.chapters),
        }


@router.get("/v1/curate/stream/{task_id}")
async def curate_stream(task_id: str):
    async def _gen():
        begin = time.time()
        sent_story = False
        sent_chapters = 0
        while True:
            story_pending: dict | None = None
            chapter_batch: list = []
            with _curate_tasks_lock:
                task = _curate_tasks.get(task_id)
                if task is None:
                    yield _sse("error", {"message": "task not found"})
                    return
                if not sent_story and task.story_ready is not None:
                    story_pending = task.story_ready
                if len(task.chapters) > sent_chapters:
                    chapter_batch = task.chapters[sent_chapters:]
                snap = {
                    "task_id": task.task_id,
                    "status": task.status,
                    "progress": round(task.progress, 2),
                    "stage": task.stage,
                    "message": task.message,
                    "ok": task.ok,
                }
                status = task.status
                error = task.error
                result = task.result
                ok = task.ok
            # B4：先补发模板 envelope，再补发已就绪章节，最后推进度快照
            if story_pending is not None:
                yield _sse("story_ready", story_pending)
                sent_story = True
            for ch in chapter_batch:
                yield _sse("chapter_ready", ch)
                sent_chapters += 1
            yield _sse("progress", snap)
            if status in ("done", "error") or error is not None:
                if status == "done":
                    yield _sse("done", {"task_id": task_id, "ok": ok, "result": result})
                else:
                    yield _sse("error", {"task_id": task_id, "message": error or "unknown error"})
                return
            # LLM 慢就多等：SSE 上限放宽到 15 分钟（原 580s），
            # 逐卡并行润色 + 慢网关时不被掐断（用户要求「多给时间，不要直接降级」）。
            if time.time() - begin > 900:
                yield _sse("error", {"task_id": task_id, "message": "curate stream timeout"})
                return
            await asyncio.sleep(0.3)

    return StreamingResponse(
        _gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
