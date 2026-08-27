import { useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { tipsForPhase } from "./tips";

type Props = {
  progress: number;
  phase: string;
};

type Milestone = {
  at: number;
  id: string;
  seal: string;
  label: string;
};

const MILESTONES: Milestone[] = [
  { at: 22, id: "l1", seal: "证", label: "L1" },
  { at: 48, id: "l2", seal: "签", label: "L2" },
  { at: 72, id: "l3", seal: "今", label: "L3" },
  { at: 96, id: "done", seal: "鸢", label: "成" },
];

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
  const [stamped, setStamped] = useState<Set<string>>(() => new Set());
  const prevPct = useRef(0);

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

  const pct = Math.max(0, Math.min(100, Math.round(progress)));
  const lineProgress = Math.max(0, Math.min(1, progress / 100));

  useEffect(() => {
    if (pct < prevPct.current) {
      setStamped(new Set());
    }
    prevPct.current = pct;
    setStamped((prev) => {
      const next = new Set(prev);
      let changed = false;
      for (const m of MILESTONES) {
        if (pct >= m.at && !next.has(m.id)) {
          next.add(m.id);
          changed = true;
        }
      }
      return changed ? next : prev;
    });
  }, [pct]);

  const tip = tips[idx] ?? tips[0] ?? "";

  return (
    <div className="panel loading loading-stage book-page-flat">
      <div
        className="loading-kite-scene"
        style={{ "--line-progress": lineProgress } as CSSProperties}
        aria-hidden
      >
        <svg viewBox="0 0 120 100" width="128" height="106" className="loading-kite-svg">
          {/* string spool → kite: drawn by progress */}
          <path
            className="kite-string-draw"
            d="M60 78 C66 70 74 62 82 54 C88 48 92 42 94 36"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
          />
          <g className="hongyuan-kite loading-kite-body">
            <path
              d="M60 10 L82 34 L60 58 L38 34 Z"
              fill="currentColor"
              fillOpacity="0.08"
              stroke="currentColor"
              strokeWidth="1.7"
              strokeLinejoin="round"
            />
            <path
              d="M60 10 L60 58 M38 34 L82 34"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.2"
              opacity="0.85"
            />
            <path
              d="M48 54 L44 66 M52 56 L50 66 M72 54 L76 66 M68 56 L70 66"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.1"
              strokeLinecap="round"
              opacity="0.7"
            />
          </g>
          <circle className="kite-spool" cx="60" cy="80" r="2.4" fill="currentColor" opacity="0.4" />
        </svg>

        <div className="loading-seal-track">
          {MILESTONES.map((m) => (
            <div
              key={m.id}
              className={`loading-seal-slot${stamped.has(m.id) ? " is-hit" : ""}`}
            >
              <span className="loading-seal-label">{m.label}</span>
              <span
                className={`loading-seal${stamped.has(m.id) ? " is-stamped" : ""}`}
                aria-hidden
              >
                {m.seal}
              </span>
            </div>
          ))}
        </div>
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
