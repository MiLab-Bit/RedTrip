import {
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";

export type FlipDirection = "forward" | "back" | "open" | "close";

type Props = {
  pageKey: string;
  direction?: FlipDirection;
  children: ReactNode;
  className?: string;
  durationMs?: number;
};

type Sheet = {
  key: string;
  node: ReactNode;
};

/**
 * Soft 3D page turn between keyed views.
 * Outgoing sheet curls away; incoming sits underneath.
 */
export function PageFlip({
  pageKey,
  direction = "forward",
  children,
  className = "",
  durationMs = 720,
}: Props) {
  const [current, setCurrent] = useState<Sheet>({ key: pageKey, node: children });
  const [outgoing, setOutgoing] = useState<ReactNode | null>(null);
  const [turning, setTurning] = useState(false);
  const [activeDir, setActiveDir] = useState<FlipDirection>(direction);
  const reduceMotion = useRef(false);
  const directionRef = useRef(direction);
  directionRef.current = direction;

  useEffect(() => {
    reduceMotion.current = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;
  }, []);

  useLayoutEffect(() => {
    if (pageKey === current.key) {
      setCurrent({ key: pageKey, node: children });
      return;
    }

    if (reduceMotion.current) {
      setOutgoing(null);
      setTurning(false);
      setCurrent({ key: pageKey, node: children });
      return;
    }

    setActiveDir(directionRef.current);
    setOutgoing(current.node);
    setCurrent({ key: pageKey, node: children });
    setTurning(true);

    const t = window.setTimeout(() => {
      setOutgoing(null);
      setTurning(false);
    }, durationMs);

    return () => window.clearTimeout(t);
    // Flip only when the key changes; live props update via the effect below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pageKey, durationMs]);

  useEffect(() => {
    if (!turning && pageKey === current.key) {
      setCurrent({ key: pageKey, node: children });
    }
  }, [children, pageKey, turning, current.key]);

  return (
    <div
      className={[
        "page-flip",
        `page-flip--${activeDir}`,
        turning ? "is-turning" : "is-idle",
        className,
      ]
        .filter(Boolean)
        .join(" ")}
      style={{ ["--flip-ms" as string]: `${durationMs}ms` }}
    >
      <div className="page-flip-under">{current.node}</div>
      {outgoing && (
        <div className="page-flip-over" aria-hidden>
          {outgoing}
          <span className="page-flip-shade" />
          <span className="page-flip-edge" />
        </div>
      )}
    </div>
  );
}
