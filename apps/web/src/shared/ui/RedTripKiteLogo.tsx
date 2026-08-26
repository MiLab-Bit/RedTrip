import { useId } from "react";

/** 红鸢纸鸢标：内联 SVG，子路径部署无 404；轻量飘曳 + 尾线抽丝动画。 */
type Props = {
  size?: number;
  className?: string;
  title?: string;
};

export function RedTripKiteLogo({
  size = 28,
  className = "brand-kite",
  title = "红鸢",
}: Props) {
  const uid = useId().replace(/:/g, "");
  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 64 64"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      role="img"
      aria-label={title}
    >
      <title>{title}</title>
      <defs>
        <linearGradient
          id={`${uid}-fill`}
          x1="32"
          y1="8"
          x2="32"
          y2="52"
          gradientUnits="userSpaceOnUse"
        >
          <stop offset="0%" stopColor="#A8322A" stopOpacity="0.18" />
          <stop offset="100%" stopColor="#A8322A" stopOpacity="0.04" />
        </linearGradient>
      </defs>
      <g className="kite-logo-body">
        <path
          d="M32 8 L52 30 L32 52 L12 30 Z"
          fill={`url(#${uid}-fill)`}
          stroke="#A8322A"
          strokeWidth="2.1"
          strokeLinejoin="round"
        />
        <path
          d="M32 8 L32 52"
          stroke="#A8322A"
          strokeWidth="1.35"
          strokeLinecap="round"
          opacity="0.9"
        />
        <path
          d="M12 30 L52 30"
          stroke="#A8322A"
          strokeWidth="1.35"
          strokeLinecap="round"
          opacity="0.9"
        />
        <path d="M32 8 L22 30 L32 52" fill="#A8322A" fillOpacity="0.06" />
        <g className="kite-logo-tails">
          <path
            d="M22 48 L18 58 M26 50 L24 58"
            stroke="#A8322A"
            strokeWidth="1.2"
            strokeLinecap="round"
            opacity="0.75"
          />
          <path
            d="M42 48 L46 58 M38 50 L40 58"
            stroke="#A8322A"
            strokeWidth="1.2"
            strokeLinecap="round"
            opacity="0.75"
          />
        </g>
      </g>
      <path
        className="kite-logo-string"
        d="M32 52 C36 56 42 58 48 56 C52 55 55 52 56 48"
        stroke="#A8322A"
        strokeWidth="1.45"
        strokeLinecap="round"
        fill="none"
        pathLength={1}
      />
      <circle className="kite-logo-bead" cx="56" cy="48" r="2.4" fill="#A8322A" />
    </svg>
  );
}
