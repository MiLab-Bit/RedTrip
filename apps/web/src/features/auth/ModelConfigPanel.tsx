import { useEffect, useState } from "react";
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

  const [busy, setBusy] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<
    { ok: boolean; kind: "success" | "timeout" | "fail"; msg: string } | null
  >(null);

  async function load() {
    try {
      const [ps, list] = await Promise.all([listProviderPresets(), listModelProviders()]);
      setPresets(ps);
      setProviders(list);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "加载失败");
    }
  }

  useEffect(() => {
    if (!open) return;
    setErr(null);
    setTestResult(null);
    setBusy(false);
    setTesting(false);
    void (async () => {
      try {
        const [ps, list] = await Promise.all([listProviderPresets(), listModelProviders()]);
        setPresets(ps);
        setProviders(list);
        // 打开时：把当前槽位已保存配置回填到上方填写栏（密钥不回显）
        const existing = list.find((x) => x.slot === "text") ?? list[0];
        if (existing) {
          const match = ps.find((x) => x.provider === existing.provider) ?? null;
          setPreset(match);
          setName(existing.name);
          setSlot(existing.slot === "multimodal" ? "multimodal" : "text");
          setBaseUrl(existing.base_url ?? match?.baseUrl ?? "");
          setModel(existing.model ?? match?.defaultModel ?? "");
          setApiKey("");
        }
      } catch (e) {
        setErr(e instanceof Error ? e.message : "加载失败");
      }
    })();
  }, [open]);

  if (!open) return null;

  function applyPreset(p: ProviderPreset) {
    setPreset(p);
    setBaseUrl(p.baseUrl);
    setModel(p.defaultModel);
    if (!name) setName(p.label);
  }

  async function handleTest() {
    if (!apiKey.trim()) {
      setErr("请先填写 API Key");
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
          : (r.error ?? "").includes("超时")
            ? { ok: false, kind: "timeout", msg: r.error ?? "未知错误" }
            : { ok: false, kind: "fail", msg: r.error ?? "未知错误" },
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
      setName("");
      setApiKey("");
      setBaseUrl(preset.baseUrl);
      setModel(preset.defaultModel);
      setTestResult(null);
      await load();
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
      await load();
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
      await load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "重测失败");
    } finally {
      setBusy(false);
    }
  }

  /** 点选已保存配置 → 回填上方填写栏（密钥不可回显，需重填才可覆盖保存） */
  function loadIntoForm(p: ModelProvider) {
    const match = presets.find((x) => x.provider === p.provider) ?? null;
    setPreset(match);
    setName(p.name);
    setSlot(p.slot === "multimodal" ? "multimodal" : "text");
    setBaseUrl(p.base_url ?? match?.baseUrl ?? "");
    setModel(p.model ?? match?.defaultModel ?? "");
    setApiKey("");
    setShowKey(false);
    setTestResult(null);
    setErr(null);
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

  return (
    <div className="auth-overlay" role="dialog" aria-modal="true" onClick={onClose}>
      <div className="auth-card" onClick={(e) => e.stopPropagation()}>
        <button className="auth-close" onClick={onClose} aria-label="关闭">
          ×
        </button>
        <h2 className="auth-title">模型配置</h2>
        <p className="auth-sub">
          配置你自己的大模型供应商密钥，RedTrip 会用它来生成行程。密钥加密存储，仅你可见。
          可分别配置「文本模型」与「多模态模型」两个槽位。
        </p>

        <label className="auth-field">
          <span>槽位</span>
          <div style={{ display: "flex", gap: 8 }}>
            <button
              type="button"
              className="auth-input"
              onClick={() => {
                setSlot("text");
                const existing = providers.find((x) => x.slot === "text");
                if (existing) loadIntoForm(existing);
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
                setSlot("multimodal");
                const existing = providers.find((x) => x.slot === "multimodal");
                if (existing) loadIntoForm(existing);
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
            className="auth-input"
            value={preset?.provider ?? ""}
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
            className="auth-input"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="例如：我的模型配置"
            autoComplete="off"
          />
        </label>

        <label className="auth-field">
          <span>API Key</span>
          <div style={{ position: "relative" }}>
            <input
              className="auth-input"
              type={showKey ? "text" : "password"}
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="sk-... / 你的供应商密钥"
              autoComplete="off"
              style={{ paddingRight: 56 }}
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
            className="auth-input"
            value={baseUrl}
            onChange={(e) => setBaseUrl(e.target.value)}
            placeholder="留空则使用供应商默认地址"
            autoComplete="off"
          />
        </label>

        <label className="auth-field">
          <span>模型</span>
          <input
            className="auth-input"
            value={model}
            onChange={(e) => setModel(e.target.value)}
            placeholder={preset?.defaultModel || "例如：gpt-4o-mini"}
            autoComplete="off"
          />
        </label>
        {providers.some((p) => p.slot === slot) && !apiKey && (
          <p className="auth-sub" style={{ marginTop: -4 }}>
            已回填该槽位配置；密钥不回显。若仅查看可直接关闭；若要覆盖保存请重新填写 API Key。
          </p>
        )}

        <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
          <button className="auth-link" onClick={() => void handleTest()} disabled={testing}>
            {testing ? "测试中…" : "测试连通性"}
          </button>
          {testResult && (
            <span
              style={{
                alignSelf: "center",
                color: testResult.kind === "success" ? "#1a7f37" : testResult.kind === "timeout" ? "#b7791f" : "#c0392b",
                fontSize: 13,
              }}
            >
              {testResult.kind === "timeout" ? `连接超时：${testResult.msg}（请检查网络或 Base URL 后重试）` : testResult.msg}
            </span>
          )}
        </div>

        <button className="auth-submit" onClick={() => void handleSave()} disabled={busy || !preset}>
          {busy ? "保存中…" : "保存配置"}
        </button>

        {err && <p className="auth-error">{err}</p>}

        <div style={{ marginTop: 16 }}>
          {providers.length === 0 && (
            <p className="auth-sub">尚无模型配置，添加一个开始使用你自己的大模型吧。</p>
          )}
          {providers.map((p) => (
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
                padding: "10px 0",
                borderTop: "1px solid rgba(0,0,0,0.08)",
                cursor: "pointer",
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
              <div style={{ display: "flex", gap: 10, flexShrink: 0 }} onClick={(e) => e.stopPropagation()}>
                <button className="auth-link" disabled={busy} onClick={() => loadIntoForm(p)}>
                  填入
                </button>
                <button className="auth-link" disabled={busy} onClick={() => void handleRetest(p.id)}>
                  重测
                </button>
                <button className="auth-link" disabled={busy} onClick={() => void handleDelete(p.id)}>
                  删除
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
