import { describe, expect, it } from "vitest";
import { windowStatus } from "./darkNow";

// ABIDABAD (Ex-MUSHTAQ 1), K-Electric, effective 2026-08-05.
const ke = [
  { start: 425, end: 575 },
  { start: 665, end: 875 },
  { start: 965, end: 1145 },
  { start: 1205, end: 1385 },
];

describe("windowStatus", () => {
  it("finds the next window later today", () => {
    expect(windowStatus(ke, 910)).toEqual({ active: false, start: 965, end: 1145, minutesUntil: 55 });
  });
  it("reports the window in progress and the minutes to its end", () => {
    expect(windowStatus(ke, 1000)).toEqual({ active: true, start: 965, end: 1145, minutesUntil: 145 });
  });
  it("is half-open: the end minute is not dark", () => {
    expect(windowStatus(ke, 575)?.active).toBe(false);
    expect(windowStatus(ke, 425)?.active).toBe(true);
  });
  it("wraps to tomorrow's first window after the last one", () => {
    expect(windowStatus(ke, 1400)).toEqual({ active: false, start: 425, end: 575, minutesUntil: 465 });
  });
  it("handles windows across midnight", () => {
    const w = [{ start: 1380, end: 60 }];
    expect(windowStatus(w, 1430)).toEqual({ active: true, start: 1380, end: 60, minutesUntil: 70 });
    expect(windowStatus(w, 30)?.minutesUntil).toBe(30);
    expect(windowStatus(w, 60)).toEqual({ active: false, start: 1380, end: 60, minutesUntil: 1320 });
  });
  it("treats an end of 1440 as midnight", () => {
    expect(windowStatus([{ start: 1380, end: 1440 }], 1439)).toMatchObject({ active: true, minutesUntil: 1 });
  });
  it("returns null without windows", () => {
    expect(windowStatus([], 100)).toBeNull();
  });
});
