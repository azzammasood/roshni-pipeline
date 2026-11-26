import { describe, expect, it } from "vitest";
import { type StatsDay, addHist, quantileBucket, totals } from "./stats";

const day = (over: Partial<StatsDay>): StatsDay => ({
  date: "2026-11-30",
  questions: 0,
  visitors: 0,
  capped: {},
  blocked: 0,
  planned: 0,
  refused: 0,
  failed: 0,
  replans: { error: 0, empty: 0, guard: 0 },
  narrated: 0,
  template: 0,
  tokens: 0,
  plan_latency: [0, 0, 0, 0, 0, 0, 0],
  narrate_latency: [0, 0, 0, 0, 0, 0, 0],
  ...over,
});

describe("usage stats", () => {
  it("finds the bucket of a quantile", () => {
    expect(quantileBucket([0, 0, 0, 0, 0, 0, 0], 0.5)).toBeNull();
    expect(quantileBucket([1, 3, 0, 0, 0, 0, 0], 0.5)).toBe(1);
    expect(quantileBucket([0, 0, 0, 0, 0, 0, 2], 0.5)).toBe(6); // overflow bucket
  });

  it("adds histograms and totals days", () => {
    expect(addHist([[1, 2], [3, 4]])).toEqual([4, 6]);
    const t = totals([
      day({ questions: 3, visitors: 2, capped: { visitor_minute: 1 }, replans: { error: 1, empty: 0, guard: 1 }, plan_latency: [2, 0, 0, 0, 0, 0, 0] }),
      day({ date: "2026-12-01", questions: 1, visitors: 1, blocked: 1, refused: 1, plan_latency: [0, 0, 1, 0, 0, 0, 0] }),
    ]);
    expect(t).toMatchObject({ questions: 4, visitors: 3, blocked: 1, refused: 1, capped: 1, corrected: 2, medianBucket: 0 });
  });
});
