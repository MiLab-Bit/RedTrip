import { describe, it, expect } from "vitest";
import { lerp, projectStops, type Vec2 } from "./geo";

describe("lerp", () => {
  it("计算中点", () => {
    expect(lerp(0, 10, 0.5)).toBe(5);
  });
  it("端点 t=0 / t=1 返回起止值", () => {
    expect(lerp(2, 8, 0)).toBe(2);
    expect(lerp(2, 8, 1)).toBe(8);
  });
  it("t 越界时线性外推", () => {
    expect(lerp(0, 10, 2)).toBe(20);
    expect(lerp(0, 10, -1)).toBe(-10);
  });
});

// projectStops 仅读取 route.stops[].geo.{lat,lng} 与 stops.length，
// 这里用最小结构 + 类型断言绕过完整 RouteStop 形状。
function makeEnvelope(stops: Array<{ lat: number; lng: number }>) {
  return {
    route: {
      duration_min: 60,
      walk_meters_est: 1000,
      stops: stops.map((g, i) => ({
        order: i + 1,
        name: `stop-${i}`,
        geo: g,
      })),
    },
  } as unknown as Parameters<typeof projectStops>[0];
}

describe("projectStops", () => {
  const envelope = makeEnvelope([
    { lat: 31.23, lng: 121.47 },
    { lat: 31.24, lng: 121.48 },
    { lat: 31.22, lng: 121.46 },
  ]);

  it("以 stops 的经纬度均值作为局部原点", () => {
    const p = projectStops(envelope);
    expect(p.lat0).toBeCloseTo((31.23 + 31.24 + 31.22) / 3, 5);
    expect(p.lng0).toBeCloseTo((121.47 + 121.48 + 121.46) / 3, 5);
  });

  it("局部原点投影到 (0,0)", () => {
    const p = projectStops(envelope);
    const origin: Vec2 = p.project(p.lat0, p.lng0);
    expect(origin.x).toBeCloseTo(0, 6);
    expect(origin.z).toBeCloseTo(0, 6);
  });

  it("每个 stop 生成一个投影点且携带 x/z", () => {
    const p = projectStops(envelope);
    expect(p.points).toHaveLength(3);
    for (const pt of p.points) {
      expect(typeof pt.x).toBe("number");
      expect(typeof pt.z).toBe("number");
    }
  });

  it("span 为正且不小于基础半径", () => {
    const p = projectStops(envelope);
    expect(p.span).toBeGreaterThan(0);
    // span = maxR * 2.4，而 maxR 至少为 40（代码里的下限）
    expect(p.span).toBeGreaterThanOrEqual(40 * 2.4);
  });

  it("空 stops 不崩溃（length 用 max(1,...) 兜底）", () => {
    const p = projectStops(makeEnvelope([]));
    expect(p.points).toHaveLength(0);
    // 0 / max(1,0) = 0，不会得到 NaN
    expect(p.lat0).toBe(0);
    expect(p.lng0).toBe(0);
    expect(Number.isFinite(p.span)).toBe(true);
    expect(p.span).toBeGreaterThan(0);
  });
});
