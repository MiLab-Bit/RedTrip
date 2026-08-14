import { useState } from "react";
import { useAuthStore } from "./authStore";
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
        <span className="usermenu-caret">▾</span>
      </button>
      {open && (
        <div className="usermenu-pop" role="menu">
          <div className="usermenu-row usermenu-id">
            {user.emailVerified ? "邮箱已验证" : "邮箱未验证"}
          </div>
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
            模型配置
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
