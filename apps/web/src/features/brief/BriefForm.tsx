import { useEffect, useRef, useState } from "react";
import type { IntentSlots } from "@redtrip/contracts";
import {
  suggestPlaces,
  type PlaceSuggestItem,
} from "../../shared/lib/places";
import {
  fetchCities,
  cityName,
  DEFAULT_CITY,
  STATIC_CITIES,
  type CityInfo,
} from "../../shared/lib/cities";
import { useCityStore } from "../../shared/lib/cityStore";
import { useAuthStore } from "../auth/authStore";
import { listModelProviders } from "../../shared/lib/authClient";

const defaults: IntentSlots = {
  audience: "成人",
  scene: "武康路一带",
  duration_min: 90,
  tone: "轻社交",
  delivery: "路线",
  companions: "2人",
  daypart: "day",
  city: DEFAULT_CITY,
};

const streetDurations = [30, 60, 90] as const;   // 街区漫游
const cityDurations = [240, 480, 1440] as const; // 城市漫游
const durationLabel = (d: number) =>
  d >= 240 ? `${d / 60}小时` : `${d}分`;
const dayparts = [
  { id: "day", label: "白天", hint: "常规开放" },
  { id: "night", label: "夜晚", hint: "夜景·夜生活" },
  { id: "full", label: "全天", hint: "昼夜混合" },
  { id: "suburb", label: "郊区", hint: "自然景点" },
] as const;
const tones = ["文艺", "轻社交", "硬核"] as const;
const companions = ["独自", "2人", "3–4人"] as const;

type Props = {
  onSubmit: (slots: IntentSlots) => void;
  /** 竞赛一键：加载冻结武康演示线（不等待 LLM） */
  onDemoWukang?: () => void;
  /** 竞赛一键：加载冻结一大—外滩演示线 */
  onDemoYida?: () => void;
};

export function BriefForm({ onSubmit, onDemoWukang, onDemoYida }: Props) {
  const [slots, setSlots] = useState<IntentSlots>({ ...defaults });
  const [cities, setCities] = useState<CityInfo[]>([]);
  const [showMore, setShowMore] = useState(false);
  const setCityStore = useCityStore((s) => s.setCity);
  const activeCity = useCityStore((s) => s.city);
  const authStatus = useAuthStore((s) => s.status);
  const [byokReady, setByokReady] = useState(false);
  const [suggestions, setSuggestions] = useState<PlaceSuggestItem[]>([]);
  const [suggestOpen, setSuggestOpen] = useState(false);
  const [suggestMeta, setSuggestMeta] = useState("馆藏 · 走廊 · 热词");
  const blurTimer = useRef<number | undefined>(undefined);
  const reqSeq = useRef(0);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const list = await fetchCities();
        if (cancelled) return;
        setCities(list);
        // 若当前选中城市不在列表（如旧缓存），回退默认上海
        const keys = new Set(list.map((c) => c.key));
        if (!keys.has(slots.city ?? DEFAULT_CITY)) {
          setSlots((prev) => ({ ...prev, city: DEFAULT_CITY }));
          setCityStore(DEFAULT_CITY);
        }
      } catch {
        setCities([]);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [slots.city, setCityStore]);

  useEffect(() => {
    if (authStatus !== "authenticated") {
      setByokReady(false);
      return;
    }
    let cancelled = false;
    void listModelProviders()
      .then((list) => {
        if (cancelled) return;
        setByokReady(list.some((p) => p.status === "active" && p.slot === "text"));
      })
      .catch(() => {
        if (!cancelled) setByokReady(false);
      });
    return () => {
      cancelled = true;
    };
  }, [authStatus]);

  const selectedScene = slots.scene ?? "";

  useEffect(() => {
    // Warm browse list once
    let cancelled = false;
    (async () => {
      try {
        const data = await suggestPlaces("", 8);
        if (cancelled) return;
        setSuggestions(data.items);
        setSuggestMeta(metaFromSources(data.sources, data.mode));
        const top = data.items[0];
        if (top) {
          setSlots((prev) => {
            const cur = prev.scene ?? "";
            if (
              !cur ||
              cur === defaults.scene ||
              cur === "武康路—华山路一带"
            ) {
              return { ...prev, scene: top.scene };
            }
            return prev;
          });
        }
      } catch {
        /* input still works alone */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!suggestOpen) return;

    const q = selectedScene.trim();
    const seq = ++reqSeq.current;
    const handle = window.setTimeout(async () => {
      try {
        const data = await suggestPlaces(q.length >= 1 ? q : "", 8);
        if (seq !== reqSeq.current) return;
        setSuggestions(data.items);
        setSuggestMeta(metaFromSources(data.sources, data.mode));
      } catch {
        /* keep previous */
      }
    }, 160);

    return () => window.clearTimeout(handle);
  }, [selectedScene, suggestOpen]);

  const pick = (item: PlaceSuggestItem) => {
    setSlots({ ...slots, scene: item.scene });
    setSuggestOpen(false);
  };

  return (
    <section className="brief-stage">
      <div className="brief-visual" aria-hidden>
        <div className="brief-ink-wash" />
        <svg
          className="brief-skyline"
          viewBox="0 0 1200 720"
          preserveAspectRatio="xMidYMid slice"
        >
          <defs>
            <linearGradient id="briefFog" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#33333A" stopOpacity="0" />
              <stop offset="40%" stopColor="#7C8A8D" stopOpacity="0.18" />
              <stop offset="78%" stopColor="#EDE4D3" stopOpacity="0.08" />
              <stop offset="100%" stopColor="#33333A" stopOpacity="0.55" />
            </linearGradient>
            <linearGradient id="briefInkFar" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#7C8A8D" stopOpacity="0.35" />
              <stop offset="100%" stopColor="#33333A" stopOpacity="0.55" />
            </linearGradient>
            <linearGradient id="briefInkNear" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#33333A" stopOpacity="0.72" />
              <stop offset="100%" stopColor="#12141A" stopOpacity="0.92" />
            </linearGradient>
            <radialGradient id="briefBloom" cx="30%" cy="28%" r="55%">
              <stop offset="0%" stopColor="#7C8A8D" stopOpacity="0.35" />
              <stop offset="55%" stopColor="#33333A" stopOpacity="0.12" />
              <stop offset="100%" stopColor="#12141A" stopOpacity="0" />
            </radialGradient>
          </defs>
          <rect width="1200" height="720" fill="url(#briefFog)" />
          <ellipse cx="320" cy="220" rx="280" ry="160" fill="url(#briefBloom)" />
          <ellipse
            cx="860"
            cy="180"
            rx="220"
            ry="120"
            fill="#33333A"
            opacity="0.18"
          />
          <path
            d="M0 420 C180 380 320 400 480 370 C640 340 780 390 960 360 C1080 340 1160 380 1200 370 V520 H0 Z"
            fill="url(#briefInkFar)"
            opacity="0.55"
          />
          <path d="M0 500 H1200 V720 H0 Z" fill="#12141A" opacity="0.45" />
          <path
            className="brief-road"
            d="M0 560 Q300 548 600 562 T1200 555"
            fill="none"
            stroke="#A8322A"
            strokeWidth="1.4"
            opacity="0.65"
          />
          <g fill="url(#briefInkNear)" className="brief-buildings">
            <path d="M40 520 V300 H150 V520 Z" />
            <path d="M165 520 V240 H295 V520 Z" />
            <path d="M310 520 V320 H420 V520 Z" />
            <path d="M440 520 V200 H600 V520 Z" />
            <path d="M620 520 V270 H750 V520 Z" />
            <path d="M770 520 V220 H920 V520 Z" />
            <path d="M940 520 V300 H1160 V520 Z" />
          </g>
          <g
            className="brief-balcony"
            stroke="#A8322A"
            strokeWidth="1.6"
            fill="none"
            opacity="0.9"
          >
            <path d="M490 270 H565" />
            <path d="M495 270 V298 H560 V270" />
            <path d="M505 298 V312 M525 298 V312 M545 298 V312" />
          </g>
          <g fill="none" stroke="#EDE4D3" strokeWidth="1" opacity="0.16">
            <path d="M185 300 H275 M185 330 H275 M185 360 H275" />
            <path d="M795 270 H900 M795 300 H900 M795 330 H900" />
            <path d="M70 350 H135 M70 380 H135" />
          </g>
          <rect
            x="980"
            y="88"
            width="52"
            height="52"
            rx="3"
            fill="none"
            stroke="#A8322A"
            strokeWidth="2.2"
            opacity="0.55"
          />
          <text
            x="1006"
            y="122"
            textAnchor="middle"
            fill="#A8322A"
            fontSize="26"
            fontFamily="Noto Serif SC, serif"
            opacity="0.7"
          >
            忆
          </text>
        </svg>
        <div className="brief-visual-veil" />
      </div>

      <div className="brief-copy">
        <div className="brief-wash-stain" aria-hidden />
        <p className="brief-brand brand-mark">
          <img
            className="brand-kite"
            src="/redtrip-kite.svg"
            alt=""
            aria-hidden
            width={36}
            height={36}
          />
          <span className="brand-word">红鸢</span>
          <span className="brand-tag">RedTrip · 城市记忆策展人</span>
          <span className="brand-seal" aria-hidden>
            鸢
          </span>
        </p>
        <h1 className="brief-title">用馆藏，策一场九十分钟的步行展览</h1>
        <p className="brief-lead">
          不报名、不集合。选定城市、一带与同行——证据先于叙事，站站可溯源。
        </p>

        <div className="brief-intent">
          <div className="field brief-city">
            <label htmlFor="brief-city">在哪个城市走</label>
            <select
              id="brief-city"
              value={slots.city ?? DEFAULT_CITY}
              onChange={(e) => {
                const c = e.target.value;
                setSlots({ ...slots, city: c });
                setCityStore(c);
              }}
            >
              {(cities.length ? cities : STATIC_CITIES).map((c) => {
                // 竞赛主城上海永远可选；其它城未 ready 仅标注，不把上海 disabled
                const selectable = c.key === "shanghai" || c.ready;
                return (
                  <option key={c.key} value={c.key} disabled={!selectable}>
                    {c.name_zh}
                    {c.featured
                      ? "（竞赛优先）"
                      : selectable
                        ? ""
                        : "（数据准备中）"}
                  </option>
                );
              })}
            </select>
          </div>

          <div className="field brief-scene">
            <div className="brief-scene-head">
              <label htmlFor="brief-scene">从哪里走起</label>
              <span className="brief-scene-meta">{suggestMeta}</span>
            </div>

            <div className="brief-scene-combo">
              <input
                id="brief-scene"
                value={selectedScene}
                onChange={(e) => {
                  setSlots({ ...slots, scene: e.target.value });
                  setSuggestOpen(true);
                }}
                onFocus={() => {
                  if (blurTimer.current) window.clearTimeout(blurTimer.current);
                  setSuggestOpen(true);
                }}
                onBlur={() => {
                  blurTimer.current = window.setTimeout(() => {
                    setSuggestOpen(false);
                  }, 160);
                }}
                placeholder="输入地名，随字联想"
                autoComplete="off"
                role="combobox"
                aria-expanded={suggestOpen}
                aria-controls="brief-scene-suggest"
                aria-autocomplete="list"
              />

              {suggestOpen && suggestions.length > 0 && (
                <ul
                  id="brief-scene-suggest"
                  className="brief-suggest-list"
                  role="listbox"
                  aria-label="地点联想"
                >
                  {suggestions.map((item, idx) => {
                    const sub = item.hint || item.district || "";
                    return (
                      <li key={item.id}>
                        <button
                          type="button"
                          role="option"
                          aria-selected={selectedScene === item.scene}
                          className={`brief-suggest-item${
                            selectedScene === item.scene ? " is-on" : ""
                          }`}
                          onMouseDown={(e) => e.preventDefault()}
                          onClick={() => pick(item)}
                        >
                          <span className="brief-suggest-num" aria-hidden>
                            {String(idx + 1).padStart(2, "0")}
                          </span>
                          <span className="brief-suggest-body">
                            <span className="brief-suggest-main">
                              <span className="brief-suggest-label">
                                {item.label}
                              </span>
                              <span
                                className={`brief-suggest-src is-${item.source}`}
                              >
                                {shortSource(item.source)}
                              </span>
                            </span>
                            {sub ? (
                              <span className="brief-suggest-hint">{sub}</span>
                            ) : null}
                          </span>
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>

            {!suggestOpen && (
              <p className="brief-scene-tip">点选联想，或直接填写任意起点</p>
            )}
          </div>

          <div className="brief-chips-block">
            <span className="brief-chip-label">多久</span>
            <div className="brief-chips" role="group" aria-label="步行时长">
              {[...streetDurations, ...cityDurations].map((d) => (
                <button
                  key={d}
                  type="button"
                  className={`brief-chip${slots.duration_min === d ? " is-on" : ""}`}
                  onClick={() => setSlots({ ...slots, duration_min: d })}
                >
                  {durationLabel(d)}
                </button>
              ))}
            </div>
          </div>

          <div className="brief-chips-block">
            <span className="brief-chip-label">调性</span>
            <div className="brief-chips" role="group" aria-label="调性">
              {tones.map((t) => (
                <button
                  key={t}
                  type="button"
                  className={`brief-chip${slots.tone === t ? " is-on" : ""}`}
                  onClick={() => setSlots({ ...slots, tone: t })}
                >
                  {t}
                </button>
              ))}
            </div>
          </div>

          <div className="brief-chips-block">
            <span className="brief-chip-label">和谁</span>
            <div className="brief-chips" role="group" aria-label="同行">
              {companions.map((c) => (
                <button
                  key={c}
                  type="button"
                  className={`brief-chip${slots.companions === c ? " is-on" : ""}`}
                  onClick={() => setSlots({ ...slots, companions: c })}
                >
                  {c}
                </button>
              ))}
            </div>
          </div>

          <button
            type="button"
            className="brief-more-toggle"
            onClick={() => setShowMore((v) => !v)}
          >
            {showMore ? "收起时段与对象" : "更多：时段与对象"}
          </button>

          {showMore && (
            <>
              <div className="brief-chips-block">
                <span className="brief-chip-label">时段</span>
                <div className="brief-chips" role="group" aria-label="时段">
                  {dayparts.map((dp) => (
                    <button
                      key={dp.id}
                      type="button"
                      title={dp.hint}
                      className={`brief-chip${(slots.daypart ?? "day") === dp.id ? " is-on" : ""}`}
                      onClick={() => setSlots({ ...slots, daypart: dp.id })}
                    >
                      {dp.label}
                    </button>
                  ))}
                </div>
              </div>

              <div className="field brief-audience">
                <label htmlFor="brief-audience">对象</label>
                <select
                  id="brief-audience"
                  value={slots.audience ?? "成人"}
                  onChange={(e) => setSlots({ ...slots, audience: e.target.value })}
                >
                  <option value="成人">成人</option>
                  <option value="青年">青年</option>
                  <option value="亲子">亲子</option>
                </select>
              </div>
            </>
          )}
        </div>

        <div className="brief-actions">
          {authStatus !== "authenticated" && (
            <p className="brief-byok-hint">
              登录并配置模型密钥后，策展将优先使用你的 BYOK 大模型；未登录则走服务端默认模型。
            </p>
          )}
          {authStatus === "authenticated" && !byokReady && (
            <p className="brief-byok-hint is-soft">
              已登录。在右上角「模型配置」保存并验证 API Key 后，策展将走 BYOK。
            </p>
          )}
          {byokReady && (
            <p className="brief-byok-hint is-on">
              BYOK 已就绪 · 本次策展将使用你配置的文本模型
            </p>
          )}
          <button
            type="button"
            className="btn brief-cta"
            onClick={() => onSubmit(slots)}
          >
            开始策展
          </button>
          {onDemoWukang ? (
            <button
              type="button"
              className="btn brief-demo"
              data-testid="demo-wukang"
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                onDemoWukang();
              }}
            >
              演示武康 · 六站可溯源
            </button>
          ) : null}
          {onDemoYida ? (
            <button
              type="button"
              className="btn brief-demo brief-demo-alt"
              data-testid="demo-yida"
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                onDemoYida();
              }}
            >
              演示一大·外滩 · 通道诚实
            </button>
          ) : null}
        </div>
        <p className="brief-footnote">
          {cityName(activeCity)}开放数据 · 证据先于叙事 · 高度缺省处标「示意」
        </p>
      </div>
    </section>
  );
}

function shortSource(source: string): string {
  if (source === "whitelist") return "馆藏";
  if (source === "corridor") return "走廊";
  if (source === "hotwords") return "热词";
  return source;
}

function metaFromSources(sources: string[], mode: string): string {
  const parts = sources.map(shortSource).filter(Boolean);
  const joined = parts.length ? parts.join(" · ") : "多源";
  return mode === "search" ? `随字 · ${joined}` : `荐读 · ${joined}`;
}
