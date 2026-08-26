import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { CurateResponseSchema, RouteEnvelopeSchema } from "@redtrip/contracts";

const yidaPath = resolve(__dirname, "../../../../../../content/fixtures/demo-route-yida.json");

describe("demo-route-yida fixture", () => {
  it("passes RouteEnvelopeSchema and CurateResponse wrap", () => {
    const yida = JSON.parse(readFileSync(yidaPath, "utf8"));
    const env = RouteEnvelopeSchema.safeParse(yida);
    expect(env.success, JSON.stringify(env.success ? null : env.error.issues.slice(0, 8))).toBe(true);
    const wrap = CurateResponseSchema.safeParse({ status: "ok", envelope: yida });
    expect(wrap.success, JSON.stringify(wrap.success ? null : wrap.error.issues.slice(0, 8))).toBe(true);
  });
});
