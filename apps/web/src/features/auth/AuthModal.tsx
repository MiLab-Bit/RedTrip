import { useEffect, useState, type FormEvent } from "react";
import { useAuthStore } from "./authStore";
import "./auth.css";

type Mode = "login" | "register" | "forgot" | "reset";

interface Props {
  open: boolean;
  onClose: () => void;
  initialMode?: Mode;
}

export function AuthModal({ open, onClose, initialMode = "login" }: Props) {
  const [mode, setMode] = useState<Mode>(initialMode);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [nickname, setNickname] = useState("");
  const [resetToken, setResetToken] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  const login = useAuthStore((s) => s.login);
  const register = useAuthStore((s) => s.register);
  const requestPasswordReset = useAuthStore((s) => s.requestPasswordReset);
  const resetPassword = useAuthStore((s) => s.resetPassword);

  // 邮件链接回跳：/reset-password?token=xxx → 自动打开重置面板并预填 token
  useEffect(() => {
    const q = new URLSearchParams(window.location.search);
    const t = q.get("token") || q.get("reset_token");
    if (window.location.pathname.endsWith("/reset-password") && t) {
      setResetToken(t);
      setMode("reset");
      window.history.replaceState(null, "", window.location.pathname);
    }
  }, []);

  if (!open) return null;

  function switchMode(m: Mode, keepInfo = false) {
    setMode(m);
    setErr(null);
    if (!keepInfo) setInfo(null);
  }

  async function handleLogin(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      await login(email.trim(), password);
      setInfo(null);
      onClose();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "登录失败");
    } finally {
      setBusy(false);
    }
  }

  async function handleRegister(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      await register({
        email: email.trim(),
        password,
        nickname: nickname.trim() || undefined,
      });
      setInfo(
        "注册成功。请查收验证邮件并点击链接完成邮箱验证，之后即可登录并配置你的大模型。",
      );
      switchMode("login", true);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "注册失败");
    } finally {
      setBusy(false);
    }
  }

  async function handleForgot(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      await requestPasswordReset(email.trim());
      setInfo("若邮箱存在，重置链接已发送。请打开邮件中的链接完成重置。");
      switchMode("reset", true);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "请求失败");
    } finally {
      setBusy(false);
    }
  }

  async function handleReset(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      await resetPassword(resetToken.trim(), newPassword);
      setInfo("密码已重置，请用新密码登录。");
      switchMode("login", true);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "重置失败");
    } finally {
      setBusy(false);
    }
  }

  const isLogin = mode === "login";
  const isRegister = mode === "register";

  return (
    <div className="auth-overlay" role="dialog" aria-modal="true" onClick={onClose}>
      <div className="auth-card" onClick={(e) => e.stopPropagation()}>
        <button className="auth-close" onClick={onClose} aria-label="关闭">
          ×
        </button>

        <div className="auth-tabs">
          <button
            className={`auth-tab${isLogin || mode === "forgot" || mode === "reset" ? " is-active" : ""}`}
            onClick={() => switchMode("login")}
          >
            登录
          </button>
          <button
            className={`auth-tab${isRegister ? " is-active" : ""}`}
            onClick={() => switchMode("register")}
          >
            注册
          </button>
        </div>

        {isLogin && (
          <>
            <h2 className="auth-title">登录 RedTrip</h2>
            <p className="auth-sub">用邮箱与密码进入你的城市记忆书架。</p>
            <form onSubmit={handleLogin}>
              <label className="auth-field">
                <span>邮箱</span>
                <input
                  className="auth-input"
                  type="email"
                  autoComplete="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                />
              </label>
              <label className="auth-field">
                <span>密码</span>
                <input
                  className="auth-input"
                  type="password"
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
              </label>
              {err && <p className="auth-error">{err}</p>}
              {info && <p className="auth-info">{info}</p>}
              <button className="auth-submit" type="submit" disabled={busy}>
                {busy ? "登录中…" : "登录"}
              </button>
            </form>
            <div className="auth-foot">
              <span />
              <button className="auth-link" onClick={() => switchMode("forgot")}>
                忘记密码？
              </button>
            </div>
          </>
        )}

        {isRegister && (
          <>
            <h2 className="auth-title">创建账号</h2>
            <p className="auth-sub">邮箱即你的身份，密码至少 8 位。</p>
            <form onSubmit={handleRegister}>
              <label className="auth-field">
                <span>邮箱</span>
                <input
                  className="auth-input"
                  type="email"
                  autoComplete="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                />
              </label>
              <label className="auth-field">
                <span>昵称（可选）</span>
                <input
                  className="auth-input"
                  type="text"
                  value={nickname}
                  onChange={(e) => setNickname(e.target.value)}
                  placeholder="留空则显示为「读者」"
                />
              </label>
              <label className="auth-field">
                <span>密码</span>
                <input
                  className="auth-input"
                  type="password"
                  autoComplete="new-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
              </label>
              {err && <p className="auth-error">{err}</p>}
              {info && <p className="auth-info">{info}</p>}
              <button className="auth-submit" type="submit" disabled={busy}>
                {busy ? "注册中…" : "注册"}
              </button>
            </form>
          </>
        )}

        {mode === "forgot" && (
          <>
            <h2 className="auth-title">找回密码</h2>
            <p className="auth-sub">输入注册邮箱，我们将发送重置链接。</p>
            <form onSubmit={handleForgot}>
              <label className="auth-field">
                <span>邮箱</span>
                <input
                  className="auth-input"
                  type="email"
                  autoComplete="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                />
              </label>
              {err && <p className="auth-error">{err}</p>}
              {info && <p className="auth-info">{info}</p>}
              <button className="auth-submit" type="submit" disabled={busy}>
                {busy ? "发送中…" : "发送重置链接"}
              </button>
            </form>
          </>
        )}

        {mode === "reset" && (
          <>
            <h2 className="auth-title">重置密码</h2>
            <p className="auth-sub">粘贴邮件链接中的 token，并设置新密码。</p>
            <form onSubmit={handleReset}>
              <label className="auth-field">
                <span>重置 token</span>
                <input
                  className="auth-input"
                  type="text"
                  value={resetToken}
                  onChange={(e) => setResetToken(e.target.value)}
                  required
                />
              </label>
              <label className="auth-field">
                <span>新密码</span>
                <input
                  className="auth-input"
                  type="password"
                  autoComplete="new-password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  required
                />
              </label>
              {err && <p className="auth-error">{err}</p>}
              {info && <p className="auth-info">{info}</p>}
              <button className="auth-submit" type="submit" disabled={busy}>
                {busy ? "重置中…" : "重置密码"}
              </button>
            </form>
          </>
        )}
      </div>
    </div>
  );
}
