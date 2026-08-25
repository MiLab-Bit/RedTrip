import { useState, useRef } from "react";
import type { NarrativeRole } from "@redtrip/contracts";
import type { StoryViewChapter } from "./storyView";

export const ROLE_COLOR: Record<NarrativeRole, string> = {
  Hook: "#A8322A",
  Anchor: "#3B6E5A",
  Contrast: "#C9962E",
  Reveal: "#2F5E8C",
  Afterimage: "#6B5B95",
  Bridge: "#7C8A8D",
};

export const ROLE_LABEL: Record<NarrativeRole, string> = {
  Hook: "钩子",
  Anchor: "锚点",
  Contrast: "对照",
  Reveal: "揭显",
  Afterimage: "余像",
  Bridge: "过渡",
};

type Props = {
  chapters: StoryViewChapter[];
  /** 当前章序（阅读器里有值；序章页不传 → 全节点保持预览态、可点） */
  currentIndex?: number;
  onOpenChapter?: (index: number) => void;
  /** 是否浮出悬停富信息卡（阅读器顶部窄条会被裁切且左侧已有章节轨，故关掉） */
  showPopover?: boolean;
};

const STEP = 116;
const PAD_X = 56;
const HEIGHT = 168;
const BASE_Y = 92;
const AMP = 26;

/**
 * 叙事地图：章节节点按行走次序排布，以关系连线相衔，节点按叙事角色着色。
 * 交互打磨：
 *  - 悬停 / 键盘聚焦 → 富信息卡（角色、钩子句、衔接语、步行时长、出场人物）
 *  - 关系连线变为「可揭示的脉络」：定位到的章，其与上章连线高亮并浮出衔接语标签
 *  - 行走进度态：已抵达 / 当前 / 未至（仅 currentIndex 存在时生效）
 *  - 更大命中区 + 当前章脉冲环 + 键盘可达（Enter / Space 跳章）
 */
export function NarrativeMap({
  chapters,
  currentIndex,
  onOpenChapter,
  showPopover = true,
}: Props) {
  const [hover, setHover] = useState<number | null>(null);
  const wrapRef = useRef<HTMLDivElement>(null);

  const n = Math.max(chapters.length, 1);
  const width = PAD_X * 2 + STEP * (n - 1);

  const xAt = (i: number) => PAD_X + i * STEP;
  const yAt = (i: number) => BASE_Y - (i % 2 === 0 ? AMP : -AMP) * 0.55;

  const hasWalk = typeof currentIndex === "number";

  const stateOf = (idx: number): "visited" | "current" | "upcoming" | "preview" => {
    if (!hasWalk) return "preview";
    if (idx === currentIndex) return "current";
    return idx < (currentIndex as number) ? "visited" : "upcoming";
  };

  const hovered = hover != null ? chapters.find((c) => c.index === hover) : null;
  const hoveredX = hover != null ? xAt(chapters.findIndex((c) => c.index === hover)) : 0;
  const hoveredY = hover != null ? yAt(chapters.findIndex((c) => c.index === hover)) : 0;

  return (
    <div className="narrative-map-wrap" ref={wrapRef}>
      <div className="narrative-map-scroll">
      <svg
        className="narrative-map"
        viewBox={`0 0 ${width} ${HEIGHT}`}
        role="group"
        aria-label="章节叙事脉络"
      >
        {chapters.map((c, i) => {
          const x = xAt(i);
          const y = yAt(i);
          const st = stateOf(c.index);
          const isActive = st === "current";
          const isVisited = st === "visited";
          const color = ROLE_COLOR[c.narrativeRole];
          const prev = i > 0 ? xAt(i - 1) : null;
          const prevY = i > 0 ? yAt(i - 1) : null;
          const segLit = hover === c.index || currentIndex === c.index;

          return (
            <g
              key={c.id}
              className={`nm-node nm-${st}${isActive ? " is-active" : ""}`}
              tabIndex={onOpenChapter ? 0 : -1}
              role={onOpenChapter ? "button" : undefined}
              aria-label={`第 ${c.index} 章 ${ROLE_LABEL[c.narrativeRole]} ${c.title}`}
              onMouseEnter={() => setHover(c.index)}
              onMouseLeave={() => setHover(null)}
              onFocus={() => setHover(c.index)}
              onBlur={() => setHover(null)}
              onClick={onOpenChapter ? () => onOpenChapter(c.index) : undefined}
              onKeyDown={
                onOpenChapter
                  ? (e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        onOpenChapter(c.index);
                      }
                    }
                  : undefined
              }
            >
              {prev !== null && prevY !== null && (
                <>
                  <line
                    className={`nm-link${segLit ? " is-strong" : ""}`}
                    x1={prev}
                    y1={prevY}
                    x2={x}
                    y2={y}
                    stroke={segLit ? color : "#C9B79C"}
                    strokeWidth={segLit ? 3 : 1.4}
                    strokeDasharray={st === "upcoming" ? "4 4" : undefined}
                  />
                  {segLit && c.relationToPrevious && (
                    <RelationTag
                      x1={prev}
                      y1={prevY}
                      x2={x}
                      y2={y}
                      text={c.relationToPrevious}
                      color={color}
                    />
                  )}
                </>
              )}

              {isActive && (
                <circle className="nm-ring" cx={x} cy={y} r={26} fill="none" stroke={color} strokeWidth={2} />
              )}

              {/* 透明大命中区，便于点击 / 触摸 */}
              <circle cx={x} cy={y} r={30} fill="transparent" />

              <circle
                cx={x}
                cy={y}
                r={isActive ? 22 : isVisited ? 18 : 18}
                fill={color}
                fillOpacity={st === "upcoming" ? 0.4 : isVisited ? 0.82 : 0.96}
                stroke={isActive ? "#2A2118" : "#EDE4D3"}
                strokeWidth={isActive ? 2.6 : 1.2}
                strokeDasharray={st === "upcoming" ? "3 3" : undefined}
              />
              <text x={x} y={y + 5} textAnchor="middle" className="nm-num" fill="#F4ECDD">
                {String(c.index).padStart(2, "0")}
              </text>
              <text x={x} y={y + 40} textAnchor="middle" className="nm-title" fill="#2A2118">
                {c.title.length > 8 ? c.title.slice(0, 7) + "…" : c.title}
              </text>
            </g>
          );
        })}
      </svg>
      </div>

      {showPopover && hovered && (
        <div
          className="nm-popover"
          style={{ left: `${(hoveredX / width) * 100}%`, top: `${(hoveredY / HEIGHT) * 100}%` }}
          role="status"
        >
          <span className="nm-pop-role" style={{ background: ROLE_COLOR[hovered.narrativeRole] }}>
            {ROLE_LABEL[hovered.narrativeRole]}
          </span>
          <p className="nm-pop-title">{hovered.title}</p>
          {hovered.hook && <p className="nm-pop-hook">{hovered.hook}</p>}
          {hovered.relationToPrevious && (
            <p className="nm-pop-meta">
              <span className="nm-pop-key">衔接</span>
              {hovered.relationToPrevious}
            </p>
          )}
          <p className="nm-pop-meta">
            <span className="nm-pop-key">步行</span>
            约 {hovered.walkingMinutes} 分钟
          </p>
          {hovered.castRefs.length > 0 && (
            <p className="nm-pop-meta">
              <span className="nm-pop-key">出场</span>
              {hovered.castRefs.join("、")}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function RelationTag({
  x1,
  y1,
  x2,
  y2,
  text,
  color,
}: {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  text: string;
  color: string;
}) {
  const mx = (x1 + x2) / 2;
  const my = (y1 + y2) / 2;
  const label = text.length > 11 ? text.slice(0, 10) + "…" : text;
  const w = label.length * 11 + 16;
  return (
    <g className="nm-tag" pointerEvents="none">
      <rect
        x={mx - w / 2}
        y={my - 11}
        width={w}
        height={22}
        rx={11}
        fill="#FBF6EC"
        stroke={color}
        strokeWidth={1}
      />
      <text x={mx} y={my + 4} textAnchor="middle" className="nm-tag-text" fill="#3A2E20">
        {label}
      </text>
    </g>
  );
}
