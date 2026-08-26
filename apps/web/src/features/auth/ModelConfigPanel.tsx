import { useEffect, useId, useRef, useState, type CSSProperties } from "react";
import {
  listProviderPresets,
  listModelProviders,
  testProvider,
  createModelProvider,
  deleteModelProvider,
  retestModelProvider,
  type ModelProvider,
  type ProviderPreset,
} from "../../shared/lib/authClient";
import "./auth.css";

type FormSnapshot = {
  preset: ProviderPreset | null;
  name: string;
  baseUrl: string;
  model: string;
  slot: "text" | "multimodal";
};

export function ModelConfigPanel({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [presets, setPresets] = useState<ProviderPreset[]>([]);
  const [providers, setProviders] = useState<ModelProvider[]>([]);
  const [err, setErr] = useState<string | null>(null);

  const [preset, setPreset] = useState<ProviderPreset | null>(null);
  const [name, setName] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [model, setModel] = useState("");
  const [showKey, setShowKey] = useState(false);
  const [slot, setSlot] = useState<"text" | "multimodal">("text");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  /** 每次回填后递增，强制重挂载输入框，甩掉浏览器自动填充 */
  const [fieldEpoch, setFieldEpoch] = useState(0);
  const [fieldsLocked, setFieldsLocked] = useState(true);

  const [busy, setBusy] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<
    { ok: boolean; kind: "success" | "timeout" | "fail"; msg: string } | null
  >(null);

  const intendedRef = useRef<FormSnapshot | null>(null);
  const uid = useId().replace(/:/g, "");

  function resolvePreset(ps: ProviderPreset[], provider: string, fallback?: ModelProvider): ProviderPreset | null {
    const hit = ps.find((x) => x.provider === provider);
    if (hit) return hit;
    if (!fallback) return null;
    return {
      provider: fallback.provider || "custom",
      label: fallback.provider || "自定义",
      baseUrl: fallback.base_url ?? "",
      defaultModel: fallback.model ?? "",
    };
  }

  function applySnapshot(snap: FormSnapshot, providerId: string | null) {
    intendedRef.current = snap;
    setPreset(snap.preset);
    setName(snap.name);
    setBaseUrl(snap.baseUrl);
    setModel(snap.model);
    setSlot(snap.slot);
    setApiKey("");
    setShowKey(false);
    setSelectedId(providerId);
    setTestResult(null);
    setErr(null);
    setFieldsLocked(true);
    setFieldEpoch((n) => n + 1);
  }

  function loadIntoForm(p: ModelProvider, ps: ProviderPreset[] = presets) {
    const match = resolvePreset(ps, p.provider, p);
    applySnapshot(
      {
        preset: match,
        name: p.name,
        baseUrl: p.base_url ?? match?.baseUrl ?? "",
        model: p.model ?? match?.defaultModel ?? "",
        slot: p.slot === "multimodal" ? "multimodal" : "text",
      },
      p.id,
    );
  }

  async function refreshList() {
    const [ps, list] = await Promise.all([listProviderPresets(), listModelProviders()]);
    setPresets(ps);
    setProviders(list);
    return { ps, list };
  }

  useEffect(() => {
    if (!open) return;
    setErr(null);
    setTestResult(null);
    setBusy(false);
    setTesting(false);
    setApiKey("");
    setShowKey(false);
    setFieldsLocked(true);
    void (async () => {
      try {
        const { ps, list } = await refreshList();
        const existing = list.find((x) => x.slot === "text") ?? list[0] ?? null;
        if (existing) {
          loadIntoForm(existing, ps);
        } else {
          applySnapshot(
            { preset: null, name: "", baseUrl: "", model: "", slot: "text" },
            null,
          );
        }
      } catch (e) {
        setErr(e instanceof Error ? e.message : "加载失败");
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  // 浏览器常在首屏渲染后异步注入账号密码：用 intentional 快照反复纠正
  useEffect(() => {
    if (!open) return;
    const timers = [50, 200, 600, 1200].map((ms) =>
      window.setTimeout(() => {
        const snap = intendedRef.current;
        if (!snap) return;
        setName(snap.name);
        setBaseUrl(snap.baseUrl);
        setModel(snap.model);
        setPreset(snap.preset);
        setSlot(snap.slot);
        setApiKey("");
      }, ms),
    );
    return () => timers.forEach((t) => window.clearTimeout(t));
  }, [open, fieldEpoch]);

  if (!open) return null;

  function applyPreset(p: ProviderPreset) {
    const snap: FormSnapshot = {
      preset: p,
      name: name.trim() || p.label,
      baseUrl: p.baseUrl,
      model: p.defaultModel,
      slot,
    };
    applySnapshot(snap, selectedId);
  }

  async function handleTest() {
    if (!apiKey.trim()) {
      setErr("请先填写 API Key（供应商密钥，不是登录密码）");
      return;
    }
    setTesting(true);
    setErr(null);
    setTestResult(null);
    try {
      const r = await testProvider({
        provider: preset?.provider ?? "custom",
        apiKey: apiKey.trim(),
        baseUrl: baseUrl.trim() || undefined,
        model: model.trim() || undefined,
      });
      setTestResult(
        r.ok
          ? { ok: true, kind: "success", msg: `连通成功（${r.latency_ms ?? "?"}ms）` }
          : (() => {
              const err = r.error ?? "未知错误";
              if (err.includes("超时")) {
                return {
                  ok: false,
                  kind: "timeout" as const,
                  msg: `${err} · 请检查网络或 Base URL 后重试`,
                };
              }
              if (/401|无权|unauthorized|invalid.*key|api.?key/i.test(err)) {
                return {
                  ok: false,
                  kind: "fail" as const,
                  msg: `${err} · 请核对 API Key 是否正确、未过期`,
                };
              }
              if (/model|模型|not found|404/i.test(err)) {
                return {
                  ok: false,
                  kind: "fail" as const,
                  msg: `${err} · 请核对模型名是否与供应商一致`,
                };
              }
              return { ok: false, kind: "fail" as const, msg: err };
            })(),
      );
    } catch (e) {
      setTestResult({ ok: false, kind: "fail", msg: e instanceof Error ? e.message : "测试失败" });
    } finally {
      setTesting(false);
    }
  }

  async function handleSave() {
    if (!name.trim() || !apiKey.trim() || !preset) {
      setErr("请填写名称、选择供应商并填写 API Key");
      return;
    }
    // 粗拦：明显是邮箱被当成名称、或把登录密码当 key 的误操作
    if (name.includes("@") && name.includes(".")) {
      setErr("「名称」看起来像邮箱。请改成配置备注（例如 abc-ai.cn (text)），不要填登录邮箱。");
      return;
    }
    setBusy(true);
    setErr(null);
    try {
      await createModelProvider({
        name: name.trim(),
        provider: preset.provider,
        apiKey: apiKey.trim(),
        baseUrl: baseUrl.trim() || undefined,
        model: model.trim() || undefined,
        slot,
      });
      const { ps, list } = await refreshList();
      const saved =
        list.find((x) => x.slot === slot && x.name === name.trim()) ??
        list.find((x) => x.slot === slot) ??
        null;
      if (saved) loadIntoForm(saved, ps);
      else {
        applySnapshot(
          {
            preset,
            name: name.trim(),
            baseUrl: baseUrl.trim(),
            model: model.trim(),
            slot,
          },
          null,
        );
      }
    } catch (e) {
      setErr(e instanceof Error ? e.message : "保存失败");
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete(id: string) {
    if (!window.confirm("确定删除该模型配置？")) return;
    setBusy(true);
    setErr(null);
    try {
      await deleteModelProvider(id);
      const { ps, list } = await refreshList();
      const next = list.find((x) => x.slot === slot) ?? list[0] ?? null;
      if (next) loadIntoForm(next, ps);
      else {
        applySnapshot({ preset: null, name: "", baseUrl: "", model: "", slot }, null);
      }
    } catch (e) {
      setErr(e instanceof Error ? e.message : "删除失败");
    } finally {
      setBusy(false);
    }
  }

  async function handleRetest(id: string) {
    setBusy(true);
    setErr(null);
    try {
      const r = await retestModelProvider(id);
      if (!r.test.ok) {
        setErr(r.test.error || "重测失败，已标记为无效");
      }
      const { ps, list } = await refreshList();
      const cur = list.find((x) => x.id === id);
      if (cur) loadIntoForm(cur, ps);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "重测失败");
    } finally {
      setBusy(false);
    }
  }

  const statusLabel: Record<string, string> = {
    active: "有效",
    unverified: "未验证",
    error: "验证失败",
  };

  const slotLabel: Record<string, string> = {
    text: "文本",
    multimodal: "多模态",
  };

  const unlock = () => setFieldsLocked(false);

  const keyMaskStyle = {
    paddingRight: 56,
    WebkitTextSecurity: showKey ? "none" : "disc",
  } as CSSProperties;

  return (
    <div className="auth-overlay" role="dialog" aria-modal="true" onClick={onClose}>
      <div className="auth-card" onClick={(e) => e.stopPropagation()}>
        <button className="auth-close" onClick={onClose} aria-label="关闭">
          ×
        </button>
        <h2 className="auth-title">模型配置</h2>
        <p className="auth-sub">
          配置你自己的大模型供应商密钥，RedTrip 会用它来生成行程。密钥加密存储，仅你可见。
          可分别配置「文本模型」与「多模态模型」两个槽位。点击下方已保存项即可回填到填写栏。
        </p>

        {/* 不用 <form>，减少被当成登录表单自动填充的概率 */}
        <div className="auth-model-form" data-form-type="other">
          <label className="auth-field">
            <span>槽位</span>
            <div style={{ display: "flex", gap: 8 }}>
              <button
                type="button"
                className="auth-input"
                onClick={() => {
                  const existing = providers.find((x) => x.slot === "text");
                  if (existing) loadIntoForm(existing);
                  else {
                    applySnapshot(
                      { preset: null, name: "", baseUrl: "", model: "", slot: "text" },
                      null,
                    );
                  }
                }}
                style={{
                  flex: 1,
                  cursor: "pointer",
                  background: slot === "text" ? "#1a7f37" : undefined,
                  color: slot === "text" ? "#fff" : undefined,
                  borderColor: slot === "text" ? "#1a7f37" : undefined,
                }}
              >
                文本模型
              </button>
              <button
                type="button"
                className="auth-input"
                onClick={() => {
                  const existing = providers.find((x) => x.slot === "multimodal");
                  if (existing) loadIntoForm(existing);
                  else {
                    applySnapshot(
                      { preset: null, name: "", baseUrl: "", model: "", slot: "multimodal" },
                      null,
                    );
                  }
                }}
                style={{
                  flex: 1,
                  cursor: "pointer",
                  background: slot === "multimodal" ? "#1a7f37" : undefined,
                  color: slot === "multimodal" ? "#fff" : undefined,
                  borderColor: slot === "multimodal" ? "#1a7f37" : undefined,
                }}
              >
                多模态模型
              </button>
            </div>
          </label>

          <label className="auth-field">
            <span>供应商</span>
            <select
              key={`provider-${fieldEpoch}`}
              className="auth-input"
              name={`${uid}-provider`}
              value={preset?.provider ?? ""}
              autoComplete="off"
              onChange={(e) => {
                const p = presets.find((x) => x.provider === e.target.value) ?? null;
                if (p) applyPreset(p);
              }}
            >
              <option value="" disabled>
                请选择供应商…
              </option>
              {presets.map((p) => (
                <option key={p.provider} value={p.provider}>
                  {p.label}
                </option>
              ))}
            </select>
          </label>

          <label className="auth-field">
            <span>名称（便于识别）</span>
            <input
              key={`name-${fieldEpoch}`}
              className="auth-input"
              name={`${uid}-label`}
              value={name}
              readOnly={fieldsLocked}
              onFocus={unlock}
              onChange={(e) => {
                const v = e.target.value;
                setName(v);
                if (intendedRef.current) intendedRef.current = { ...intendedRef.current, name: v };
              }}
              placeholder="例如：我的 Qwen 文本配置"
              autoComplete="off"
              data-1p-ignore
              data-lpignore="true"
              data-bwignore="true"
              data-form-type="other"
            />
          </label>

          <label className="auth-field">
            <span>API Key（供应商密钥，不是登录密码）</span>
            <div style={{ position: "relative" }}>
              <input
                key={`key-${fieldEpoch}`}
                className="auth-input"
                name={`${uid}-secret`}
                type="text"
                inputMode="text"
                value={apiKey}
                readOnly={fieldsLocked}
                onFocus={unlock}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="粘贴 sk-… / 供应商 API Key"
                autoComplete="new-password"
                autoCapitalize="off"
                autoCorrect="off"
                spellCheck={false}
                data-1p-ignore
                data-lpignore="true"
                data-bwignore="true"
                data-form-type="other"
                style={keyMaskStyle}
              />
              <button
                type="button"
                className="auth-link"
                onClick={() => setShowKey((s) => !s)}
                style={{ position: "absolute", right: 8, top: 8 }}
              >
                {showKey ? "隐藏" : "显示"}
              </button>
            </div>
          </label>

          <label className="auth-field">
            <span>Base URL（自定义 API 网关）</span>
            <input
              key={`base-${fieldEpoch}`}
              className="auth-input"
              name={`${uid}-base`}
              value={baseUrl}
              readOnly={fieldsLocked}
              onFocus={unlock}
              onChange={(e) => {
                const v = e.target.value;
                setBaseUrl(v);
                if (intendedRef.current) intendedRef.current = { ...intendedRef.current, baseUrl: v };
              }}
              placeholder="留空则使用供应商默认地址"
              autoComplete="off"
              data-1p-ignore
              data-lpignore="true"
              data-form-type="other"
            />
          </label>

          <label className="auth-field">
            <span>模型</span>
            <input
              key={`model-${fieldEpoch}`}
              className="auth-input"
              name={`${uid}-model`}
              value={model}
              readOnly={fieldsLocked}
              onFocus={unlock}
              onChange={(e) => {
                const v = e.target.value;
                setModel(v);
                if (intendedRef.current) intendedRef.current = { ...intendedRef.current, model: v };
              }}
              placeholder={preset?.defaultModel || "例如：Qwen-flash"}
              autoComplete="off"
              data-1p-ignore
              data-lpignore="true"
              data-form-type="other"
            />
          </label>

          {selectedId && !apiKey && (
            <p className="auth-sub" style={{ marginTop: -4 }}>
              已把下方配置回填到填写栏（模型名、Base URL 等）。密钥不会回显；仅查看可直接关闭，覆盖保存时请重新粘贴 API Key。
            </p>
          )}

          <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
            <button type="button" className="auth-link" onClick={() => void handleTest()} disabled={testing}>
              {testing ? "测试中…" : "测试连通性"}
            </button>
            {testResult && (
              <span
                style={{
                  alignSelf: "center",
                  color:
                    testResult.kind === "success"
                      ? "#1a7f37"
                      : testResult.kind === "timeout"
                        ? "#b7791f"
                        : "#c0392b",
                  fontSize: 13,
                }}
              >
                {testResult.kind === "timeout"
                  ? `连接超时：${testResult.msg}（请检查网络或 Base URL 后重试）`
                  : testResult.msg}
              </span>
            )}
          </div>

          <button
            type="button"
            className="auth-submit"
            disabled={busy || !preset}
            onClick={() => void handleSave()}
          >
            {busy ? "保存中…" : "保存配置"}
          </button>
        </div>

        {err && <p className="auth-error">{err}</p>}

        <div style={{ marginTop: 16 }}>
          <p className="auth-sub" style={{ marginBottom: 4 }}>
            已保存配置（点击一行即可写入上方填写栏）
          </p>
          {providers.length === 0 && (
            <p className="auth-sub">尚无模型配置，添加一个开始使用你自己的大模型吧。</p>
          )}
          {providers.map((p) => {
            const active = selectedId === p.id;
            return (
              <div
                key={p.id}
                role="button"
                tabIndex={0}
                onClick={() => loadIntoForm(p)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    loadIntoForm(p);
                  }
                }}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  gap: 12,
                  padding: "10px 8px",
                  margin: "0 -8px",
                  borderTop: "1px solid rgba(0,0,0,0.08)",
                  cursor: "pointer",
                  borderRadius: 8,
                  background: active ? "rgba(168,50,42,0.06)" : undefined,
                  outline: active ? "1px solid rgba(168,50,42,0.25)" : undefined,
                }}
                title="点击回填到上方填写栏"
              >
                <div>
                  <div style={{ fontWeight: 600 }}>
                    {p.name}
                    <span
                      style={{
                        marginLeft: 8,
                        fontSize: 12,
                        padding: "1px 6px",
                        borderRadius: 10,
                        background: p.slot === "multimodal" ? "#e8f0fe" : "#e9f5ee",
                        color: p.slot === "multimodal" ? "#1a56c4" : "#1a7f37",
                      }}
                    >
                      {slotLabel[p.slot] ?? p.slot}
                    </span>
                  </div>
                  <div className="auth-sub" style={{ marginTop: 2 }}>
                    {p.provider} · {p.model ?? "—"} · {statusLabel[p.status] ?? p.status}
                    {p.status === "error" && p.last_error ? ` · ${p.last_error.slice(0, 60)}` : ""}
                  </div>
                </div>
                <div
                  style={{ display: "flex", gap: 10, flexShrink: 0 }}
                  onClick={(e) => e.stopPropagation()}
                >
                  <button type="button" className="auth-link" disabled={busy} onClick={() => loadIntoForm(p)}>
                    填入
                  </button>
                  <button
                    type="button"
                    className="auth-link"
                    disabled={busy}
                    onClick={() => void handleRetest(p.id)}
                  >
                    重测
                  </button>
                  <button
                    type="button"
                    className="auth-link"
                    disabled={busy}
                    onClick={() => void handleDelete(p.id)}
                  >
                    删除
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
