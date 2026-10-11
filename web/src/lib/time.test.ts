import { describe, expect, it } from "vitest";
import { formatKarachi, hhmm, karachiDate, karachiMinuteOfDay } from "./time";

describe("Karachi time", () => {
  it("adds five hours to UTC and wraps midnight", () => {
    expect(karachiMinuteOfDay(new Date("2026-10-10T18:30:00Z"))).toBe(23 * 60 + 30);
    expect(karachiMinuteOfDay(new Date("2026-10-10T19:05:00Z"))).toBe(5);
    expect(karachiDate(new Date("2026-10-10T19:05:00Z"))).toBe("2026-10-11");
  });
  it("formats minutes and timestamps", () => {
    expect(hhmm(0)).toBe("00:00");
    expect(hhmm(1440)).toBe("24:00");
    expect(formatKarachi("2026-10-11T15:43:58Z")).toBe("11 Oct 2026, 20:43");
  });
});
