import { useEffect, useState } from "react";
import { useAuthStore } from "./authStore";
import { listModelProviders } from "../../shared/lib/authClient";
import { useProgressStore } from "../progress/progressStore";
import "./auth.css";

export function UserMenu({
  onOpenAuth,
  onOpenModelConfig,
}: {
  onOpenAuth: () => void;
  onOpenModelConfig: () => void;
}) {
  const user = useAuthStore((s) => s.user);
  const status = useAuthStore((s) => s.status);
  const logout = useAuthStore((s) => s.logout);
  const userId = user?.publicId ?? null;
  const progress = useProgressStore((s) => s.byUser[userId ?? "anon"]);
  const [open, setOpen] = useState(false);
  const [byokActive, setByokActive] = useState(false);

  useEffect(() => {
    if (status !== "authenticated") {
      setByokActive(false);
      return;
    }
    let cancelled = false;
    void listModelProviders()
      .then((list) => {
        if (cancelled) return;
        setByokActive(list.some((p) => p.status === "active" && p.slot === "text"));
      })
      .catch(() => {
        if (!cancelled) setByokActive(false);
      });
    return () => {
      cancelled = true;
    };
  }, [status, user?.publicId]);

  if (status !== "authenticated" || !user) {
    return (
      <button className="auth-trigger" onClick={onOpenAuth}>
        登录 / 注册
      </button>
    );
  }

  const name = user.nickname || "读者";

  return (
    <div className="usermenu">
      <button
        className="usermenu-trigger"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="true"
        aria-expanded={open}
      >
        <span className="usermenu-name">{name}</span>
        {byokActive && (
          <span className="usermenu-byok" title="已配置自带大模型密钥">
            BYOK
          </span>
        )}
        <span className="usermenu-caret">▾</span>
      </button>
      {open && (
        <div className="usermenu-pop" role="menu">
          <div className="usermenu-row usermenu-id">
            {user.emailVerified ? "邮箱已验证" : "邮箱未验证 · 验证后可保存模型配置"}
          </div>
          {byokActive && (
            <div className="usermenu-row usermenu-byok-line">
              文本模型 BYOK 已启用 · 策展走你的密钥
            </div>
          )}
          {progress && (
            <div className="usermenu-row">
              上次《{progress.theme}》第 {progress.currentChapter}/
              {progress.totalChapters} 章
              {progress.finished ? " · 已读完" : ""}
            </div>
          )}
          <button
            className="usermenu-action"
            onClick={() => {
              setOpen(false);
              onOpenModelConfig();
            }}
          >
            模型配置{byokActive ? "" : "（BYOK）"}
          </button>
          <button
            className="usermenu-action"
            onClick={() => {
              setOpen(false);
              void logout();
            }}
          >
            退出登录
          </button>
        </div>
      )}
    </div>
  );
}
