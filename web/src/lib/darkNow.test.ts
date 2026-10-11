// Mirrors src/roshni/live/test_dark_now.py on the same synthetic feeders.
import { describe, expect, it } from "vitest";
import type { DarkProfile, Feeder, PlannedShutdown } from "@/types/v1";
import { darkNow, windowActive, type DarkNowData, type IescoLevel } from "./darkNow";

const m = (s: string) => Number(s.slice(0, 2)) * 60 + Number(s.slice(2));
// Naive Karachi wall time -> instant (UTC+5).
const pkt = (iso: string) => new Date(`${iso}+05:00`);

describe("windowActive", () => {
  it.each([
    ["2234", false],
    ["2235", true], // start inclusive
    ["2359", true],
    ["0000", true], // after midnight, still inside the wrapped window
    ["0204", true],
    ["0205", false], // end exclusive
    ["1200", false],
  ])("22:35~02:05 at %s -> %s", (at, expected) => {
    expect(windowActive(m("2235"), m("0205"), m(at))).toBe(expected);
  });

  it("handles a window ending at midnight and plain windows", () => {
    expect(windowActive(23 * 60, 1440, m("2359"))).toBe(true); // IESCO "23--24"
    expect(windowActive(23 * 60, 1440, m("0000"))).toBe(false);
    expect(windowActive(0, 60, m("0000")) && !windowActive(0, 60, m("0100"))).toBe(true);
  });
});

const feeder = (f: Partial<Feeder> & Pick<Feeder, "feeder_id" | "name" | "source">): Feeder => ({
  feeder_code: null, circle: null, grid: null, ibc: null, category: null, atc_loss_pct: null,
  in_feeder_list: null, has_schedule: true, schedule_match_method: null,
  schedule_match_confidence: null, localities: [], ...f,
});
const hours = (dark: number[]) => Array.from({ length: 24 }, (_, h) => (dark.includes(h) ? 60 : 0));
const shutdown = (s: Partial<PlannedShutdown>): PlannedShutdown => ({
  shutdown_id: "x", release_no: null, outage_date: "2026-10-05", start_utc: "", end_utc: "",
  start_local: "", end_local: "", circle_as_printed: "", feeder_name_as_printed: "", feeder_id: null,
  feeder_match_state: "matched", match_confidence: null, flags: "", ...s,
});

const data: DarkNowData = {
  feeders: [
    feeder({ feeder_id: "ke:A", name: "NIGHT FEEDER", source: "kelectric", ibc: "IBC - Orangi - I" }),
    feeder({ feeder_id: "ke:B", name: "NOON FEEDER", source: "kelectric", ibc: "IBC - Clifton" }),
    feeder({ feeder_id: "iesco:islamabad:000001", name: "SCENARIO FEEDER", source: "iesco", circle: "islamabad" }),
  ],
  profiles: [
    { feeder_id: "ke:A", source: "kelectric", effective_from: "2026-08-05", daily_windows: [{ start_min: 1355, end_min: 125 }] },
    { feeder_id: "ke:B", source: "kelectric", effective_from: "2026-08-05", daily_windows: [{ start_min: 720, end_min: 900 }] },
    { feeder_id: "iesco:islamabad:000001", source: "iesco", effective_from: "2026-01-14", scenario_levels: { "2": hours([23]), "12": hours([0]) } },
  ] satisfies DarkProfile[],
  shutdowns: [
    shutdown({ feeder_id: "iesco:islamabad:000001", feeder_name_as_printed: "Scenario Feeder", circle_as_printed: "Islamabad", start_utc: "2026-10-05T03:00:00Z", end_utc: "2026-10-05T09:00:00Z", start_local: "08:00", end_local: "14:00" }),
    shutdown({ feeder_name_as_printed: "KRL", circle_as_printed: "Rawalpindi City", start_utc: "2026-10-05T02:00:00Z", end_utc: "2026-10-05T09:00:00Z", start_local: "07:00", end_local: "14:00", feeder_match_state: "unmatched" }),
  ],
};
const counts = (level: IescoLevel | null, at: string) =>
  darkNow(data, pkt(at), level).rows.reduce<Record<string, number>>(
    (acc, r) => ({ ...acc, [r.kind]: (acc[r.kind] ?? 0) + 1 }),
    {},
  );

describe("darkNow", () => {
  it("finds a wrapped window after midnight", () => {
    const r = darkNow(data, pkt("2026-10-06T01:00"));
    expect(r.rows.map((x) => [x.feederId, x.kind, x.windowLocal])).toEqual([
      ["ke:A", "daily_cycle", "22:35-02:05"],
    ]);
    expect(r.rows[0].effectiveFrom).toBe("2026-08-05");
    expect(r.notes).toContainEqual({ kind: "iesco_level_not_chosen" });
  });

  it("shows IESCO scenarios only when a level is chosen", () => {
    expect(counts(null, "2026-10-06T23:30")).toEqual({ daily_cycle: 1 });
    expect(counts(2, "2026-10-06T23:30")).toEqual({ daily_cycle: 1, scenario_level_2: 1 });
    expect(darkNow(data, pkt("2026-10-06T23:30"), 2).rows[1].windowLocal).toBe("23:00-24:00");
    expect(() => darkNow(data, pkt("2026-10-06T23:30"), 3 as IescoLevel)).toThrow();
  });

  it("uses UTC bounds for planned shutdowns", () => {
    const r = darkNow(data, pkt("2026-10-05T07:30")); // 02:30 UTC: only KRL started
    expect(r.rows.filter((x) => x.kind === "planned_shutdown").map((x) => x.feederName)).toEqual(["KRL"]);
    expect(r.notes).toContainEqual({ kind: "unmatched_shutdowns", count: 1 });
    expect(counts(null, "2026-10-05T13:59").planned_shutdown).toBe(2);
    expect(counts(null, "2026-10-05T14:00").planned_shutdown).toBeUndefined();
  });

  it("does not apply a schedule before its effective date", () => {
    const r = darkNow(data, pkt("2026-07-01T23:00"));
    expect(r.rows.some((x) => x.kind === "daily_cycle")).toBe(false);
    expect(r.notes).toContainEqual({ kind: "not_yet_effective", source: "kelectric", effectiveFrom: "2026-08-05" });
  });
});
