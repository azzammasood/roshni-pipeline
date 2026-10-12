import { describe, expect, it } from "vitest";
import { fill } from "./fill";

describe("fill", () => {
  it("leaves English text plain and groups numbers", () => {
    expect(fill("{n} feeders at {time}", { n: 1719, time: "12:27" }, "en")).toBe("1,719 feeders at 12:27");
  });
  it("isolates inserted values in Urdu and keeps Western digits", () => {
    const out = fill("{date} کو {time} بجے", { date: "2026-10-12", time: "12:27" }, "ur");
    expect(out).toBe("⁨2026-10-12⁩ کو ⁨12:27⁩ بجے");
    expect(fill("{n}", { n: 1719 }, "ur")).toBe("⁨1,719⁩");
  });
  it("fails loudly on a missing value", () => {
    expect(() => fill("{x}", {}, "en")).toThrow(/missing value/);
  });
});
