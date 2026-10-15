// Build-time aggregates for the city pages (server only; the pages pass the small results to the
// client charts). Counts and shares are computed from the exported schedules as published.
import type { ClockData } from "@/components/city/ScheduleClock";
import { circleName, ibcName } from "@/lib/names";
import type { DarkProfile, Feeder } from "@/types/v1";

export const IESCO_LEVELS = [2, 4, 6, 8, 10, 12] as const;
export const IESCO_CIRCLES = ["islamabad", "rawalpindi", "attock", "jhelum", "chakwal", "ajk"] as const;

const mean = (xs: number[]) => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : 0);
const round = (v: number, d = 2) => Math.round(v * 10 ** d) / 10 ** d;

/** Minutes dark per hour (24 values) for each feeder -> the clock's numbers. */
function aggregate(items: { group: string; minutes: number[] }[]): ClockData {
  const n = items.length;
  const dark = Array.from({ length: 24 }, (_, h) => items.filter((f) => f.minutes[h] > 0).length);
  const groups = new Map<string, number[][]>();
  for (const f of items) groups.set(f.group, [...(groups.get(f.group) ?? []), f.minutes]);
  return {
    feeders: n,
    avgHours: round(mean(items.map((f) => f.minutes.reduce((a, b) => a + b, 0))) / 60, 1),
    share: dark.map((k) => (n ? round(k / n, 3) : 0)),
    dark,
    rows: [...groups.entries()]
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([name, ms]) => ({
        name,
        feeders: ms.length,
        share: Array.from({ length: 24 }, (_, h) => round(ms.filter((m) => m[h] > 0).length / ms.length, 3)),
      })),
  };
}

/** IESCO: per circle and interruption level, by grid. Keys "circle|level". */
export function iescoClocks(feeders: Feeder[], profiles: DarkProfile[]) {
  const byId = new Map(profiles.map((p) => [p.feeder_id, p]));
  const data: Record<string, ClockData> = {};
  for (const circle of IESCO_CIRCLES) {
    const fs = feeders.filter((f) => f.source === "iesco" && f.has_schedule && f.circle === circle);
    for (const level of IESCO_LEVELS) {
      const items = fs.flatMap((f) => {
        const minutes = byId.get(f.feeder_id)?.scenario_levels?.[String(level)];
        return minutes ? [{ group: f.grid ?? "–", minutes }] : [];
      });
      if (items.length) data[`${circle}|${level}`] = aggregate(items);
    }
  }
  const circles = IESCO_CIRCLES.filter((c) => IESCO_LEVELS.some((l) => data[`${c}|${l}`])).map((c) => ({
    key: c,
    label: circleName(c) ?? c,
  }));
  const effective = profiles.find((p) => p.source === "iesco")?.effective_from ?? null;
  return { data, circles, effective };
}

/** K-Electric: its one published daily schedule, by IBC. Key "|". */
export function keClock(feeders: Feeder[], profiles: DarkProfile[]) {
  const byId = new Map(feeders.map((f) => [f.feeder_id, f]));
  const items = profiles.flatMap((p) =>
    p.source === "kelectric" && p.daily ? [{ group: ibcName(byId.get(p.feeder_id)?.ibc ?? "–"), minutes: p.daily }] : [],
  );
  const effective = profiles.find((p) => p.source === "kelectric")?.effective_from ?? null;
  const data: Record<string, ClockData> = items.length ? { "|": aggregate(items) } : {};
  return { data, effective };
}

/** Press-release circles that belong to a schedule circle ("Rawalpindi" -> Cantt and City). */
export const pressCircles = (circle: string) => (name: string) =>
  name.toLowerCase().startsWith((circleName(circle) ?? circle).toLowerCase());
