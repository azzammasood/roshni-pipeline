import { describe, expect, it } from "vitest";
import { companyOfSlug, joinList, medianOf, rankIn } from "./cities";

const rows = [
  { company: "A", fiscal_year: "2024-25", reported_hours_per_day: 5 },
  { company: "B", fiscal_year: "2024-25", reported_hours_per_day: 0 },
  { company: "C", fiscal_year: "2024-25", reported_hours_per_day: 0 },
  { company: "D", fiscal_year: "2024-25", reported_hours_per_day: 8 },
];

describe("cities", () => {
  it("ranks by hours, ties share a rank", () => {
    expect(rankIn(rows, "D", "2024-25")).toEqual({ rank: 1, of: 4 });
    expect(rankIn(rows, "B", "2024-25")).toEqual({ rank: 3, of: 4 });
    expect(rankIn(rows, "C", "2024-25")).toEqual({ rank: 3, of: 4 });
    expect(rankIn(rows, "X", "2024-25")).toBeNull();
  });
  it("takes the median", () => {
    expect(medianOf([5, 0, 0, 8])).toBe(2.5);
    expect(medianOf([3, 1, 2])).toBe(2);
    expect(medianOf([])).toBeNull();
  });
  it("joins lists", () => {
    expect(joinList(["IESCO"], "and")).toBe("IESCO");
    expect(joinList(["IESCO", "GEPCO"], "and")).toBe("IESCO and GEPCO");
    expect(joinList(["A", "B", "C"], "اور", "، ")).toBe("A، B اور C");
  });
  it("maps slugs back to companies", () => {
    expect(companyOfSlug("islamabad")).toBe("IESCO");
    expect(companyOfSlug("karachi")).toBe("K-Electric");
    expect(companyOfSlug("nowhere")).toBeNull();
  });
});
