import { useEffect, useMemo, useState } from "react";
import { tipsForPhase } from "./tips";

type Props = {
  progress: number;
  phase: string;
};

function layerLabel(phase: string): string {
  const p = phase || "";
  if (/取证|检索|馆藏|证据|whitelist|证据链|L1/i.test(p)) return "L1 · 取证";
  if (/抽签|声线|情绪|叙事|润色|装订|红鸢|L2|voice/i.test(p)) return "L2 · 抽签";
  if (/热词|当代|口吻|社交|L3|hotword/i.test(p)) return "L3 · 当代口吻";
  return "红鸢装订中";
}

export function LoadingStage({ progress, phase }: Props) {
  const tips = useMemo(() => tipsForPhase(phase), [phase]);
  const [idx, setIdx] = useState(0);
  const [fade, setFade] = useState(true);

  useEffect(() => {
    setIdx(0);
  }, [tips]);

  useEffect(() => {
    const id = window.setInterval(() => {
      setFade(false);
      window.setTimeout(() => {
        setIdx((i) => (i + 1) % Math.max(tips.length, 1));
        setFade(true);
      }, 220);
    }, 3200);
    return () => window.clearInterval(id);
  }, [tips]);

  const tip = tips[idx] ?? tips[0] ?? "";
  const pct = Math.max(0, Math.min(100, Math.round(progress)));

  return (
    <div className="panel loading loading-stage book-page-flat">
      <div className="hongyuan-mark" aria-hidden>
        <svg viewBox="0 0 64 48" width="56" height="42" className="hongyuan-kite">
          <path
            d="M32 4 L56 24 L32 44 L8 24 Z"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.6"
          />
          <path
            d="M32 4 L32 44 M8 24 L56 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1"
            opacity="0.55"
          />
          <path
            d="M32 44 Q28 52 22 56"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.2"
            strokeLinecap="round"
          />
        </svg>
      </div>
      <p className="loading-layer">{layerLabel(phase)}</p>
      <h2>红鸢正在装订城市书页</h2>
      <p className="lead loading-phase">{phase}</p>

      <div
        className="load-bar"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={pct}
        aria-label="加载进度"
      >
        <div className="load-bar-track">
          <div className="load-bar-fill" style={{ width: `${pct}%` }} />
        </div>
        <span className="load-bar-pct">{pct}%</span>
      </div>

      <p className={`load-tip-line${fade ? " is-on" : ""}`}>{tip}</p>
    </div>
  );
}
