import { describe, expect, it } from "vitest";
import { monthLabel } from "./time";

describe("monthLabel", () => {
  it("names the month in the page's language", () => {
    expect(monthLabel("2026-09", "en")).toBe("Sep 2026");
    expect(monthLabel("2026-01", "ur")).toBe("جنوری 2026");
    expect(monthLabel("2025-12", "xx")).toBe("Dec 2025");
  });
  it("leaves anything else alone", () => {
    expect(monthLabel("2026-13", "en")).toBe("2026-13");
    expect(monthLabel("10/2026", "en")).toBe("10/2026");
  });
});
