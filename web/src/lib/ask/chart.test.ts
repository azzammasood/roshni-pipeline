import { describe, expect, it } from "vitest";
import { chartOf } from "./chart";

describe("chartOf", () => {
  it("charts a label and a number", () => {
    const c = chartOf(["ibc", "feeders"], [["A", "10"], ["B", "4"]]);
    expect(c).toMatchObject({ label: "ibc", value: "feeders", bars: [{ label: "A", value: 10 }, { label: "B", value: 4 }] });
  });
  it("finds the number in either column", () => {
    expect(chartOf(["hours", "fy"], [["7.5", "FY2023-24"], ["6", "FY2024-25"]])?.label).toBe("fy");
  });
  it("keeps single rows, equal values, wide or long results as a table", () => {
    expect(chartOf(["a", "n"], [["x", "1"]])).toBeNull();
    expect(chartOf(["a", "n"], [["x", "1"], ["y", "1"]])).toBeNull();
    expect(chartOf(["a", "b", "n"], [["x", "y", "1"], ["z", "w", "2"]])).toBeNull();
    expect(chartOf(["a", "n"], Array.from({ length: 25 }, (_, i) => [`r${i}`, String(i)]))).toBeNull();
    expect(chartOf(["a", "b"], [["x", "y"], ["z", "w"]])).toBeNull();
  });
});
