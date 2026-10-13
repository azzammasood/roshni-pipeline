import { describe, expect, it } from "vitest";
import {
  clockText,
  formatKarachi,
  hhmm,
  isoMonth,
  isoWeekMonday,
  karachiDate,
  karachiMinuteOfDay,
  parseHhmm,
} from "./time";

describe("Karachi time", () => {
  it("adds five hours to UTC and wraps midnight", () => {
    expect(karachiMinuteOfDay(new Date("2026-10-10T18:30:00Z"))).toBe(23 * 60 + 30);
    expect(karachiMinuteOfDay(new Date("2026-10-10T19:05:00Z"))).toBe(5);
    expect(karachiDate(new Date("2026-10-10T19:05:00Z"))).toBe("2026-10-11");
  });
  it("formats minutes and timestamps", () => {
    expect(hhmm(0)).toBe("00:00");
    expect(hhmm(1440)).toBe("24:00");
    expect(formatKarachi("2026-10-11T15:43:58Z")).toBe("2026-10-11 20:43");
    expect(formatKarachi("2026-10-11T19:05:00Z")).toBe("2026-10-12 00:05");
  });
  it("switches between 24- and 12-hour clocks", () => {
    const halves = { am: "AM", pm: "PM" };
    expect(clockText(parseHhmm("17:35"), "24", halves)).toBe("17:35");
    expect(clockText(parseHhmm("17:35"), "12", halves)).toBe("5:35 PM");
    expect(clockText(0, "12", halves)).toBe("12:00 AM");
    expect(clockText(12 * 60, "12", halves)).toBe("12:00 PM");
    expect(clockText(1440, "12", halves)).toBe("12:00 AM");
    expect(clockText(1440, "24", halves)).toBe("24:00");
  });
  it("formats weeks and months as ISO dates", () => {
    expect(isoWeekMonday("2026-W42")).toBe("2026-10-12");
    expect(isoWeekMonday("2026-W01")).toBe("2025-12-29");
    expect(isoMonth("10/2026")).toBe("2026-10");
    expect(isoMonth("7/2026")).toBe("2026-07");
  });
});
