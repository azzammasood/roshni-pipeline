import { num } from "@/lib/format";
import type { DarkProfile, National } from "@/types/v1";

const LEVELS = ["2", "4", "6", "8", "10", "12"];
const mean = (xs: number[]) => xs.reduce((a, b) => a + b, 0) / Math.max(xs.length, 1);
const round1 = (v: number) => Math.round(v * 10) / 10;

/** Hours a day each company's own published schedule plans per feeder, as display text.
 *  IESCO: the average over its feeders at each interruption level, as a range (it never says
 *  which level is in force). K-Electric: the average of the schedule in force at the latest month.
 *  Plans, not measurements; companies without a published schedule are absent. */
export function schedulePlans(profiles: DarkProfile[], national: National, locale: string): Record<string, string> {
  const out: Record<string, string> = {};
  const iesco = profiles.filter((p) => p.source === "iesco" && p.scenario_levels);
  const byLevel = LEVELS.map((l) =>
    mean(
      iesco
        .map((p) => p.scenario_levels?.[l])
        .filter((m): m is number[] => Array.isArray(m))
        .map((m) => m.reduce((a, b) => a + b, 0) / 60),
    ),
  ).filter((h) => h > 0);
  if (byLevel.length) {
    const [lo, hi] = [round1(Math.min(...byLevel)), round1(Math.max(...byLevel))];
    out.IESCO = lo === hi ? num(lo, locale) : `${num(lo, locale)}–${num(hi, locale)}`;
  }
  const ke = national.monthly_ke?.at(-1);
  if (ke) out["K-Electric"] = num(round1(ke.avg_scheduled_hours), locale);
  return out;
}
