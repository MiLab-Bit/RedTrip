import { useEffect, useState } from "react";
import { shuffledTips } from "./tips";

type Props = {
  progress: number;
  phase: string;
};

export function LoadingStage({ progress, phase }: Props) {
  const [tips] = useState(() => shuffledTips());
  const [idx, setIdx] = useState(0);
  const [fade, setFade] = useState(true);

  useEffect(() => {
    const id = window.setInterval(() => {
      setFade(false);
      window.setTimeout(() => {
        setIdx((i) => (i + 1) % tips.length);
        setFade(true);
      }, 220);
    }, 3200);
    return () => window.clearInterval(id);
  }, [tips.length]);

  const tip = tips[idx] ?? tips[0] ?? "";
  const pct = Math.max(0, Math.min(100, Math.round(progress)));

  return (
    <div className="panel loading loading-stage book-page-flat">
      <div className="pulse" aria-hidden />
      <h2>正在装订城市书页</h2>
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
