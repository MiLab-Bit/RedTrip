import {
  Suspense,
  lazy,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";
import { useMachine } from "@xstate/react";
import type { HongyuanMeta, IntentSlots, RouteEnvelope } from "@redtrip/contracts";
import { BriefForm } from "../features/brief/BriefForm";
import { LoadingStage } from "../features/loading/LoadingStage";
import { BookShell } from "../features/shell/BookShell";
import { WalkStage } from "../features/walk/WalkStage";
import { StoryIntro } from "../features/story/StoryIntro";
import { StoryOutro } from "../features/story/StoryOutro";
import { PreviewReader } from "../features/story/PreviewReader";
import { buildStoryView, type StoryView } from "../features/story/storyView";
import { tripMachine } from "../features/trip/machine";
import {
  curateRouteStream,
  fetchDemoWukang,
  fetchDemoYida,
  type StreamChapter,
} from "../shared/lib/curate";
import { fetchFootprints } from "../shared/lib/footprints";
import { useAuthStore } from "../features/auth/authStore";
import { useProgressStore } from "../features/progress/progressStore";
import { useCityStore } from "../shared/lib/cityStore";
import { cityName } from "../shared/lib/cities";
import { UserMenu } from "../features/auth/UserMenu";
import { AuthModal } from "../features/auth/AuthModal";
import { ModelConfigPanel } from "../features/auth/ModelConfigPanel";

/**
 * 地图舞台按需加载。
 *
 * MapStage 依赖 three / @react-three/fiber / @react-three/drei，这三者
 * 打进 vendor chunk 后体积约 1.2MB（gzip 后仍有 300KB+），但它们只在
 * `map` 状态才会被用到——而用户必然先经过 brief → loading → 序章 → 章节
 * 阅读，中间有充足时间在后台把这个 chunk 取回。
 *
 * 静态 import 会让这 1.2MB 压在首屏关键路径上，直接推高首屏时间；
 * 改为 lazy 后首屏只需 react/xstate/zustand（约 150KB），
 * 3D 资源在真正进入地图前才下载，且被浏览器缓存复用。
 */
const MapStage = lazy(() =>
  import("../features/map/MapStage").then((m) => ({ default: m.MapStage })),
);

/** 地图 chunk 下载期间的占位，沿用书页基调，避免布局跳动。 */
function MapLoadingFallback() {
  return (
    <section className="panel book-page-flat" aria-busy="true">
      <p className="note story-kicker">城市记忆策展人 · 舆图</p>
      <p className="lead">正在展开这一程的舆图…</p>
    </section>
  );
}

/** B4：把流式就绪的润色卡合并进 envelope 的 blocks（只碰 title/body/age_parallel）。 */
function mergeStreamCards(
  env: RouteEnvelope,
  cards: Record<number, StreamChapter["card"]>,
): RouteEnvelope {
  const keys = Object.keys(cards);
  if (keys.length === 0) return env;
  const blocks = (env.blocks ?? []).map((b) => {
    if (b.type !== "story_card") return b;
    const c = cards[b.stop_order];
    if (!c) return b;
    return {
      ...b,
      title: c.title ?? b.title,
      body: c.body ?? b.body,
      age_parallel: c.age_parallel ?? b.age_parallel,
    };
  });
  return { ...env, blocks };
}

export function App() {
  const [state, send] = useMachine(tripMachine);
  const [pendingSlots, setPendingSlots] = useState<IntentSlots | null>(null);
  const [loadProgress, setLoadProgress] = useState(0);
  const [loadPhase, setLoadPhase] = useState("翻开馆藏…");
  const [authOpen, setAuthOpen] = useState(false);
  const [modelConfigOpen, setModelConfigOpen] = useState(false);
  /**
   * B4 章节级流式预览：story_ready 到达后即可读模板序章/章节，
   * chapter_ready 逐章替换为润色版；done 后清理并走正式流程。
   */
  const [previewEnv, setPreviewEnv] = useState<RouteEnvelope | null>(null);
  const [previewHongyuan, setPreviewHongyuan] =
    useState<HongyuanMeta | null>(null);
  const [streamCards, setStreamCards] = useState<
    Record<number, StreamChapter["card"]>
  >({});
  const [previewReading, setPreviewReading] = useState(false);
  const [previewChapter, setPreviewChapter] = useState(1);
  /** 邮箱验证 / 密码重置链接回跳的结果提示。 */
  const [verifyMsg, setVerifyMsg] = useState<string | null>(null);
  /**
   * 降级提示。后端在走兜底路径时会返回 status="degraded"（快照样例、
   * Gate 未过的样例、策展过程异常降级）。这类结果依然可读，但不该被
   * 当成完整策展成品静静端给用户——如实标注，才对得起「可溯源」的承诺。
   */
  const [degradeNotices, setDegradeNotices] = useState<string[]>([]);
  const [degradeExpanded, setDegradeExpanded] = useState(false);

  // 启动时用 refresh token 静默恢复登录态（无 token 则直接进入未登录态）。
  useEffect(() => {
    void useAuthStore.getState().bootstrap();

    // 邮箱验证链接回跳：/verify-email?token=xxx → 自动完成验证并提示结果
    const q = new URLSearchParams(window.location.search);
    const vt = q.get("token");
    if (window.location.pathname.endsWith("/verify-email") && vt) {
      void useAuthStore
        .getState()
        .verifyEmail(vt)
        .then(() => setVerifyMsg("邮箱验证成功，现在可以登录了"))
        .catch((e) =>
          setVerifyMsg(
            "验证未生效：" + (e instanceof Error ? e.message : "未知错误"),
          ),
        );
      window.history.replaceState(null, "", window.location.pathname);
    }
    // 密码重置链接回跳：/reset-password?token=xxx → 自动打开登录弹窗（AuthModal 内切到重置面板并预填 token）
    if (window.location.pathname.endsWith("/reset-password") && q.get("token")) {
      setAuthOpen(true);
    }
  }, []);

  /**
   * 地图 chunk 预取：一旦策展成功（进入序章/章节阅读），就在后台把
   * three/drei 的 chunk 取回。用户读序章与前几章通常要几十秒，足够
   * 下载完成，于是点「看舆图」时是零等待——既不压首屏，也不让用户等。
   */
  useEffect(() => {
    if (state.value !== "storyIntro" && state.value !== "storyReader") return;
    // 失败无需处理：真正进入地图时 lazy 会重试，Suspense 兜住等待态。
    void import("../features/map/MapStage").catch(() => undefined);
  }, [state.value]);

  useEffect(() => {
    if (state.value !== "loading") return;
    const mode = state.context.loadMode;
    if (!mode) return;
    let cancelled = false;
    const ac = new AbortController();

    const bump = (to: number, phase: string) => {
      if (cancelled) return;
      setLoadPhase(phase);
      setLoadProgress((p) => Math.max(p, to));
    };

    const isDemoWukang = mode === "demo-wukang";
    const isDemoYida = mode === "demo-yida";
    const isDemo = isDemoWukang || isDemoYida;
    setLoadProgress(0);
    setLoadPhase(
      isDemoWukang
        ? "L1 · 装载武康冻结演示线…"
        : isDemoYida
          ? "L1 · 装载一大—外滩冻结演示线…"
          : "L1 · 提交取证任务…",
    );
    setDegradeNotices([]);

    (async () => {
      try {
        if (isDemo) {
          setLoadProgress(8);
          setLoadPhase(
            isDemoWukang
              ? "L1 · 装载武康冻结演示线…"
              : "L1 · 装载一大—外滩冻结演示线…",
          );
          bump(40, "L2 · 红鸢抽签读法已冻结…");
          const { envelope, assumptions, hongyuan, degraded, notices } =
            isDemoWukang
              ? await fetchDemoWukang(ac.signal)
              : await fetchDemoYida(ac.signal);
          if (cancelled) return;
          bump(72, "L3 · 句级溯源与证据通道已齐…");
          setDegradeNotices(degraded ? notices : []);
          const osm = await fetchFootprints(envelope, ac.signal);
          if (cancelled) return;
          bump(96, "演示线装订完成…");
          await new Promise((r) => setTimeout(r, 120));
          if (cancelled) return;
          const theme = String(envelope.theme || "");
          if (isDemoWukang && !theme.includes("武康")) {
            throw new Error(`演示线主题异常：${envelope.theme}`);
          }
          if (isDemoYida && !theme.includes("外滩")) {
            throw new Error(`演示线主题异常：${envelope.theme}`);
          }
          setLoadProgress(100);
          send({
            type: "LOADED",
            envelope,
            assumptions,
            hongyuan,
            footprints: osm.features,
            osmNote:
              osm.note ||
              (isDemoWukang ? "演示线 · 武康冻结包" : "演示线 · 一大外滩冻结包"),
          });
          return;
        }

        const slots = pendingSlots;
        if (!slots) {
          throw new Error("策展槽位缺失");
        }

        setLoadProgress(2);
        setLoadPhase("L1 · 提交取证任务…");

        let chapterCount = 0;
        const { envelope, assumptions, hongyuan, degraded, notices } =
          await curateRouteStream(
            slots,
            (p, stage, message) => {
              if (cancelled) return;
              setLoadProgress(p);
              if (message) setLoadPhase(message);
              if (stage === "evidence" || stage === "retrieve") {
                setLoadPhase("L1 · 馆藏取证中…");
              } else if (stage === "hongyuan" || stage === "voice") {
                setLoadPhase("L2 · 红鸢抽签定声线…");
              } else if (stage === "hotwords" || stage === "layer3") {
                setLoadPhase("L3 · 对齐当代口吻…");
              } else if (stage === "narrate") {
                setLoadPhase("L2 · 叙事初稿完成，逐章润色中…");
              }
            },
            ac.signal,
            (story) => {
              if (cancelled) return;
              setPreviewEnv(story.envelope);
              setPreviewHongyuan(story.hongyuan);
            },
            (chapter) => {
              if (cancelled) return;
              chapterCount += 1;
              setStreamCards((m) => ({
                ...m,
                [chapter.stop_order]: chapter.card,
              }));
            },
          );
        if (cancelled) return;
        setPreviewEnv(null);
        setPreviewHongyuan(null);
        setStreamCards({});
        setPreviewReading(false);
        setPreviewChapter(1);
        setDegradeNotices(degraded ? notices : []);
        const reading =
          hongyuan?.summary ??
          (hongyuan ? "红鸢已抽签" : "馆藏已齐");
        bump(92, `${reading} · 拉取 OSM 走廊建筑…`);

        const osm = await fetchFootprints(envelope, ac.signal);
        if (cancelled) return;

        bump(96, "烘焙城景网格（简化 · 合并）…");
        await new Promise((r) => setTimeout(r, 160));
        if (cancelled) return;

        bump(99, "装订完成，准备翻开…");
        await new Promise((r) => setTimeout(r, 220));
        if (cancelled) return;
        setLoadProgress(100);

        send({
          type: "LOADED",
          envelope,
          assumptions,
          hongyuan,
          footprints: osm.features,
          osmNote: osm.note,
        });
      } catch (e) {
        if (!cancelled) {
          send({
            type: "FAIL",
            error: e instanceof Error ? e.message : "策展失败",
          });
        }
      }
    })();

    return () => {
      cancelled = true;
      ac.abort();
    };
  }, [state.value, state.context.loadMode, pendingSlots, send]);

  // 进入 loading 时的初始相位在上方 effect 开头设置；勿在此重置，
  // 否则会与 demo/流式 bump 竞态，把 L1/L2/L3 旁白冲掉。

  const restart = useCallback(() => {
    setPendingSlots(null);
    setDegradeNotices([]);
    setPreviewEnv(null);
    setPreviewHongyuan(null);
    setStreamCards({});
    send({ type: "RESTART" });
  }, [send]);

  const storyView = useMemo<StoryView | null>(() => {
    const env = state.context.envelope;
    return env ? buildStoryView(env) : null;
  }, [state.context.envelope]);

  /** B4 预览视图：模板 envelope + 已就绪的润色卡合并，供 loading 期先行阅读。 */
  const previewViewEnv = useMemo<RouteEnvelope | null>(() => {
    return previewEnv ? mergeStreamCards(previewEnv, streamCards) : null;
  }, [previewEnv, streamCards]);
  const previewView = useMemo<StoryView | null>(() => {
    return previewViewEnv ? buildStoryView(previewViewEnv) : null;
  }, [previewViewEnv]);
  const previewStreamed = useMemo<Record<number, boolean>>(() => {
    const m: Record<number, boolean> = {};
    for (const k of Object.keys(streamCards)) m[Number(k)] = true;
    return m;
  }, [streamCards]);

  // 阅读进度按账号隔离（未登录记到 "anon"）；翻章 / 收尾时落盘，供用户菜单回显。
  const recordProgress = useCallback(() => {
    const env = state.context.envelope;
    if (!env || !storyView) return;
    const userId = useAuthStore.getState().user?.publicId ?? null;
    useProgressStore.getState().record(userId, {
      theme: env.theme,
      thesis: storyView.thesis,
      chapterTitles: storyView.chapters.map((c) => c.title),
      currentChapter: state.context.currentChapter,
      totalChapters: storyView.chapters.length,
      finished: state.value === "done",
      updatedAt: Date.now(),
    });
  }, [state.context.envelope, state.context.currentChapter, state.value, storyView]);

  useEffect(() => {
    if (storyView && (state.value === "storyReader" || state.value === "done")) {
      recordProgress();
    }
  }, [recordProgress, state.value, storyView]);

  const isBrief = state.value === "brief";
  const footprints = state.context.footprints;
  const osmNote = state.context.osmNote;
  // 头部标识即时反映主页选中的城市（无需逐层 props 透传）。
  const activeCity = useCityStore((s) => s.city);

  return (
    <div className={`app-shell${isBrief ? " is-brief" : " is-reading"}`}>
      {verifyMsg && (
        <div className="verify-banner" role="status">
          <span className="verify-banner-text">{verifyMsg}</span>
          <button
            type="button"
            className="auth-link"
            onClick={() => setVerifyMsg(null)}
          >
            关闭
          </button>
        </div>
      )}
      {!isBrief && (
        <header className="topbar">
          <div className="brand brand-mark">
            <img
              className="brand-kite"
              src="/redtrip-kite.svg"
              alt=""
              aria-hidden
              width={28}
              height={28}
            />
            <span className="brand-word">红鸢</span>
            <small className="brand-tag">RedTrip · 城市记忆策展人</small>
            <span className="brand-seal" aria-hidden>
              鸢
            </span>
          </div>
          <div className="source-badge">
            {cityName(activeCity)} · 可溯源书页
          </div>
          <UserMenu
            onOpenAuth={() => setAuthOpen(true)}
            onOpenModelConfig={() => setModelConfigOpen(true)}
          />
        </header>
      )}
      {isBrief && (
        <div className="auth-float">
          <UserMenu
            onOpenAuth={() => setAuthOpen(true)}
            onOpenModelConfig={() => setModelConfigOpen(true)}
          />
        </div>
      )}

      <main className={`stage${isBrief ? " stage-brief" : ""}`}>
        {!isBrief && degradeNotices.length > 0 && (
          <div className="degrade-banner" role="status">
            <p className="degrade-title">
              这一程是降级结果：内容可读，但未走完整策展。
            </p>
            <ul className={degradeExpanded ? "degrade-list is-expanded" : "degrade-list"}>
              {(degradeExpanded ? degradeNotices : degradeNotices.slice(0, 3)).map(
                (n, i) => (
                  <li key={i}>{n}</li>
                ),
              )}
            </ul>
            {degradeNotices.length > 3 && (
              <button
                type="button"
                className="degrade-expand"
                onClick={() => setDegradeExpanded((v) => !v)}
              >
                {degradeExpanded
                  ? "收起原因"
                  : `展开全部 ${degradeNotices.length} 条原因`}
              </button>
            )}
            <button
              type="button"
              className="degrade-dismiss"
              onClick={() => setDegradeNotices([])}
              aria-label="收起提示"
            >
              关闭
            </button>
          </div>
        )}

        {isBrief && (
          <BriefForm
            onSubmit={(slots) => {
              setPendingSlots(slots);
              send({ type: "SUBMIT" });
            }}
            onDemoWukang={() => {
              setPendingSlots(null);
              send({ type: "SUBMIT_DEMO_WUKANG" });
            }}
            onDemoYida={() => {
              setPendingSlots(null);
              send({ type: "SUBMIT_DEMO_YIDA" });
            }}
          />
        )}

        {state.value === "loading" && previewViewEnv && previewView && (
          <BookShell
            mode={previewReading ? "spread" : "folio"}
            className="book-scene--preview"
          >
            {previewReading ? (
              <PreviewReader
                envelope={previewViewEnv}
                streamed={previewStreamed}
                currentChapter={previewChapter}
                onOpenChapter={(i) => setPreviewChapter(i)}
                onPrev={() => setPreviewChapter((c) => Math.max(1, c - 1))}
                onNext={() => setPreviewChapter((c) => c + 1)}
                onBack={() => setPreviewReading(false)}
              />
            ) : (
              <>
                <div className="preview-banner" role="status">
                  模板预览已就绪 · 正在逐章润色（已润色{" "}
                  {Object.keys(streamCards).length} 章）
                </div>
                <StoryIntro
                  envelope={previewViewEnv}
                  storyView={previewView}
                  hongyuan={previewHongyuan}
                  onBegin={() => setPreviewReading(true)}
                  onShowMap={() => undefined}
                  onRestart={() => undefined}
                />
              </>
            )}
          </BookShell>
        )}

        {state.value === "loading" && !previewEnv && (
          <BookShell mode="folio">
            <LoadingStage progress={loadProgress} phase={loadPhase} />
          </BookShell>
        )}

        {state.value === "storyIntro" && state.context.envelope && storyView && (
          <BookShell mode="folio">
            <StoryIntro
              envelope={state.context.envelope}
              storyView={storyView}
              hongyuan={state.context.hongyuan}
              onBegin={() => send({ type: "BEGIN_STORY" })}
              onShowMap={() => send({ type: "SHOW_MAP" })}
              onRestart={restart}
            />
          </BookShell>
        )}

        {state.value === "storyReader" && state.context.envelope && storyView && (
          <BookShell mode="spread" className="book-scene--walk">
            <WalkStage
              envelope={state.context.envelope}
              storyView={storyView}
              currentChapter={state.context.currentChapter}
              source={state.context.source}
              onOpenSource={(source) => send({ type: "OPEN_SOURCE", source })}
              onCloseSource={() => send({ type: "CLOSE_SOURCE" })}
              onOpenChapter={(index) => send({ type: "OPEN_CHAPTER", index })}
              onPrevChapter={() => send({ type: "PREV_CHAPTER" })}
              onNextChapter={() => send({ type: "NEXT_CHAPTER" })}
              onShowMap={() => send({ type: "SHOW_MAP" })}
              onBackIntro={() => send({ type: "BACK_INTRO" })}
              onFinish={() => send({ type: "FINISH" })}
            />
          </BookShell>
        )}

        {state.value === "map" && state.context.envelope && (
          <BookShell mode="folio">
            <Suspense fallback={<MapLoadingFallback />}>
              <MapStage
                envelope={state.context.envelope}
                assumptions={state.context.assumptions}
                hongyuan={state.context.hongyuan}
                footprints={footprints}
                osmNote={osmNote}
                activeOrder={
                  storyView
                    ? storyView.chapters[state.context.currentChapter - 1]
                        ?.stopId ?? 1
                    : undefined
                }
                onBack={() => send({ type: "BACK_FROM_MAP" })}
                onOpenStop={(order) => send({ type: "OPEN_STOP", order })}
                onFinish={() => send({ type: "FINISH" })}
                onRestart={restart}
              />
            </Suspense>
          </BookShell>
        )}

        {state.value === "done" && state.context.envelope && storyView && (
          <BookShell mode="folio">
            <StoryOutro
              envelope={state.context.envelope}
              storyView={storyView}
              hongyuan={state.context.hongyuan}
              onRestart={restart}
            />
          </BookShell>
        )}

        {state.value === "degraded" && (
          <BookShell mode="folio">
            <section className="panel degraded-card book-page-flat" role="alert">
              <p className="degraded-kicker">未能完整放行</p>
              <h2>这条线暂时未能展示</h2>
              <p className="lead">
                {state.context.error ||
                  "取证或闸门未通过。未编造内容，故不展示路线。"}
              </p>
              {degradeNotices.length > 0 && (
                <>
                  <p className="degraded-kicker">Gate / 降级原因</p>
                  <ul className="degraded-hints degraded-reasons">
                    {degradeNotices.map((n, i) => (
                      <li key={i}>{n}</li>
                    ))}
                  </ul>
                </>
              )}
              <details className="degraded-tech">
                <summary>技术说明（调试）</summary>
                <ul className="degraded-hints">
                  <li>确认 API 与 Web 均已启动并可访问</li>
                  <li>
                    上游抖动时可改 <code>REDTRIP_MODE=snapshot</code> 后重启 API
                  </li>
                  <li>备援：播放预先录好的演示片（见 Doc/15-demo-script.md）</li>
                </ul>
              </details>
              <div className="btn-row">
                <button
                  className="btn"
                  type="button"
                  onClick={restart}
                >
                  返回出题
                </button>
              </div>
            </section>
          </BookShell>
        )}
      </main>

      <AuthModal open={authOpen} onClose={() => setAuthOpen(false)} />
      <ModelConfigPanel
        open={modelConfigOpen}
        onClose={() => setModelConfigOpen(false)}
      />
    </div>
  );
}
