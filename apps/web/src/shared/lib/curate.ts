import {
  CurateResponseSchema,
  type HongyuanMeta,
  type IntentSlots,
  type RouteEnvelope,
} from "@redtrip/contracts";

import { API_BASE } from "./apiBase";
import { authHeaders } from "./authClient";

/**
 * 策展结果。
 *
 * `degraded` 表示后端走了兜底路径（快照样例、Gate 未过的样例、
 * 或策展过程中被降级），此时 envelope 依然可用、依然可读，
 * 只是不该被当成「完整策展成品」——UI 应当如实提示，而不是
 * 要么当成功、要么直接报错。
 */
export type CurateOutcome = {
  envelope: RouteEnvelope;
  assumptions: string[];
  hongyuan: HongyuanMeta | null;
  degraded: boolean;
  notices: string[];
  gatePassed: boolean | null;
};

/** B4：章节级流式——单张故事卡就绪的载荷（对应 blocks 中 story_card 的字段）。 */
export type StreamChapter = {
  stop_order: number;
  card: { title?: string; body?: string; age_parallel?: string };
  provenance: unknown;
};

/** B4：模板 envelope 先行交付（narrate 完成后、润色开始前）。 */
export type StreamStory = {
  envelope: RouteEnvelope;
  assumptions: string[];
  hongyuan: HongyuanMeta | null;
};

/**
 * 统一解析策展响应。
 *
 * 关键判定原则：**只有拿不到 envelope 才算失败**。
 * 后端的 `status="degraded"` 语义是「内容可用但质量有保留」，
 * 原实现把它一并 throw，等于让后端所有兜底逻辑（快照样例、
 * 异常降级）在前端全部失效，用户看到的是报错而不是内容。
 */
function toOutcome(raw: unknown): CurateOutcome {
  const parsed = CurateResponseSchema.safeParse(raw);
  if (!parsed.success) {
    throw new Error("策展响应未通过契约校验：" + parsed.error.message);
  }

  if (!parsed.data.envelope) {
    const reasons =
      (parsed.data.reasons ?? []).filter(Boolean).join("；") || "未知原因";
    throw new Error("策展未放行：" + reasons);
  }

  // 直接复用 CurateResponseSchema 已校验产出的 envelope。
  // 不再 RouteEnvelopeSchema.parse() 二次校验：envelope 实测约 45KB~700KB，
  // zod 深度遍历一遍就要占主线程，跑两遍纯属白烧一倍首屏时间。
  const envelope: RouteEnvelope = parsed.data.envelope;
  const degraded = parsed.data.status !== "ok";
  const gate = parsed.data.meta?.gate;
  const notices = degraded
    ? [
        ...(parsed.data.reasons ?? []),
        ...(gate?.warnings ?? []),
        ...(gate?.passed === false ? ["Gate 闸门未放行（见上方原因）"] : []),
      ].filter(Boolean)
    : [];

  return {
    envelope,
    assumptions: parsed.data.meta?.assumptions ?? [],
    hongyuan: parsed.data.meta?.hongyuan ?? null,
    degraded,
    notices,
    gatePassed: gate?.passed ?? null,
  };
}

export async function curateRoute(slots: IntentSlots): Promise<CurateOutcome> {
  const res = await fetch(`${API_BASE}/v1/curate`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({
      message: undefined,
      slots,
      retry_count: 0,
    }),
  });

  if (!res.ok) {
    throw new Error(`策展接口 HTTP ${res.status}`);
  }

  const json: unknown = await res.json();
  return toOutcome(json);
}

/** 竞赛冻结演示线：一键武康，不等待 LLM。 */
export async function fetchDemoWukang(
  signal?: AbortSignal,
): Promise<CurateOutcome> {
  const res = await fetch(`${API_BASE}/v1/demo/wukang`, { signal });
  if (!res.ok) {
    throw new Error(`演示线接口 HTTP ${res.status}`);
  }
  const json: unknown = await res.json();
  return toOutcome(json);
}

/** 竞赛冻结演示线 B：一大—外滩。 */
export async function fetchDemoYida(
  signal?: AbortSignal,
): Promise<CurateOutcome> {
  const res = await fetch(`${API_BASE}/v1/demo/yida`, { signal });
  if (!res.ok) {
    throw new Error(`演示线接口 HTTP ${res.status}`);
  }
  const json: unknown = await res.json();
  return toOutcome(json);
}

/**
 * P0：异步策展 + SSE 实时进度。
 * 先 POST /v1/curate/start 拿到 task_id，再经 EventSource 订阅
 * /v1/curate/stream/{task_id} 的真实进度，根治原前端 38% 假进度。
 */
export async function curateRouteStream(
  slots: IntentSlots,
  onProgress: (progress: number, stage: string, message: string) => void,
  signal?: AbortSignal,
  onStory?: (payload: StreamStory) => void,
  onChapter?: (payload: StreamChapter) => void,
): Promise<CurateOutcome> {
  const startRes = await fetch(`${API_BASE}/v1/curate/start`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ message: undefined, slots, retry_count: 0 }),
    signal,
  });
  if (!startRes.ok) {
    throw new Error(`策展提交 HTTP ${startRes.status}`);
  }
  const startJson = (await startRes.json()) as { task_id?: string };
  const taskId = startJson.task_id;
  if (!taskId) {
    throw new Error("策展任务未返回 task_id");
  }

  return await new Promise((resolve, reject) => {
    const es = new EventSource(`${API_BASE}/v1/curate/stream/${taskId}`);
    let settled = false;

    function onAbort() {
      if (settled) return;
      settled = true;
      teardown();
      reject(new DOMException("策展已取消", "AbortError"));
    }

    /** 关流 + 摘掉 abort 监听，避免 EventSource 与闭包被 signal 长期持有 */
    function teardown() {
      if (signal) signal.removeEventListener("abort", onAbort);
      if (es.readyState !== EventSource.CLOSED) es.close();
    }

    if (signal) signal.addEventListener("abort", onAbort);

    es.addEventListener("progress", (ev) => {
      try {
        const data = JSON.parse((ev as MessageEvent).data);
        onProgress(
          typeof data.progress === "number" ? data.progress : 0,
          typeof data.stage === "string" ? data.stage : "",
          typeof data.message === "string" ? data.message : "",
        );
      } catch {
        /* 忽略坏帧 */
      }
    });

    // B4：模板 envelope 先行（进序章可读）；逐卡就绪增量替换正文
    es.addEventListener("story_ready", (ev) => {
      try {
        const data = JSON.parse((ev as MessageEvent).data);
        if (onStory && data?.envelope) {
          onStory({
            envelope: data.envelope as RouteEnvelope,
            assumptions: Array.isArray(data.assumptions)
              ? data.assumptions
              : [],
            hongyuan: (data.hongyuan as HongyuanMeta | null) ?? null,
          });
        }
      } catch {
        /* 忽略坏帧 */
      }
    });

    es.addEventListener("chapter_ready", (ev) => {
      try {
        const data = JSON.parse((ev as MessageEvent).data);
        if (onChapter && data && typeof data.stop_order === "number") {
          onChapter(data as StreamChapter);
        }
      } catch {
        /* 忽略坏帧 */
      }
    });

    es.addEventListener("done", (ev) => {
      if (settled) return;
      settled = true;
      try {
        const data = JSON.parse((ev as MessageEvent).data);
        const outcome = toOutcome(data.result);
        teardown();
        resolve(outcome);
      } catch (e) {
        teardown();
        reject(e instanceof Error ? e : new Error("策展结果解析失败"));
      }
    });

    es.addEventListener("error", (ev) => {
      if (settled) return;
      settled = true;
      let msg = "策展进度流中断";
      try {
        const data = JSON.parse((ev as MessageEvent).data);
        if (typeof data?.message === "string") msg = data.message;
      } catch {
        /* 连接层错误，保留默认文案 */
      }
      teardown();
      reject(new Error(msg));
    });
  });
}
