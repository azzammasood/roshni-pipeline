import { describe, expect, it } from "vitest";
import { hourWindows } from "./windows";

const hours = (...on: number[]) => Array.from({ length: 24 }, (_, h) => (on.includes(h) ? 60 : 0));

describe("hourWindows", () => {
  it("joins adjacent hours", () => {
    expect(hourWindows(hours(12, 13, 17))).toEqual([
      { start: 720, end: 840 },
      { start: 1020, end: 1080 },
    ]);
  });
  it("joins a run across midnight", () => {
    expect(hourWindows(hours(0, 5, 23))).toEqual([
      { start: 300, end: 360 },
      { start: 1380, end: 60 },
    ]);
  });
  it("keeps a lone last hour ending at 24:00", () => {
    expect(hourWindows(hours(23))).toEqual([{ start: 1380, end: 1440 }]);
  });
});
