// "Scheduled dark now", computed in the browser from the static export. Port of
// src/roshni/live/dark_now.py: same window semantics, kinds, labels and ordering, and the gate
// test (darkNow.oracle.test.ts) checks it row for row against the Python function.
// Everything here is SCHEDULE data (including IESCO's announced maintenance), never measured outages.
import type { DarkProfile, Feeder, MaintenanceWindow, PlannedShutdown } from "@/types/v1";
import { hhmm, karachiDate, karachiMinuteOfDay } from "./time";

export const IESCO_LEVELS = [2, 4, 6, 8, 10, 12] as const;
export type IescoLevel = (typeof IESCO_LEVELS)[number];

export type DarkKind = "daily_cycle" | "maintenance" | `scenario_level_${IescoLevel}` | "planned_shutdown";

export interface DarkRow {
  feederId: string | null;
  feederName: string;
  source: "iesco" | "kelectric";
  kind: DarkKind;
  /** K-Electric IBC or IESCO circle (as printed for planned shutdowns); for maintenance, the
   *  schedule file's listing row (a circle id, gso or construction). */
  area: string | null;
  /** Local window, e.g. "22:35-02:05" (Asia/Karachi). */
  windowLocal: string;
  /** Schedule effective date, or the outage date for a planned shutdown or maintenance. */
  effectiveFrom: string;
  matchState?: PlannedShutdown["feeder_match_state"];
}

export type DarkNote =
  | { kind: "not_yet_effective"; source: string; effectiveFrom: string }
  | { kind: "iesco_level_not_chosen" }
  | { kind: "unmatched_shutdowns"; count: number }
  | { kind: "unlinked_maintenance"; count: number };

export interface DarkNowResult {
  minuteOfDay: number;
  localDate: string;
  level: IescoLevel | null;
  rows: DarkRow[];
  notes: DarkNote[];
}

export interface DarkNowData {
  feeders: Feeder[];
  profiles: DarkProfile[];
  shutdowns: PlannedShutdown[];
  /** Announced maintenance windows (export 1.6.0); omitted while that document loads. */
  maintenance?: MaintenanceWindow[];
}

/** Is `minute` (0..1439) inside [start, end)? end <= start wraps midnight. */
export function windowActive(startMin: number, endMin: number, minute: number): boolean {
  if (endMin > startMin) return startMin <= minute && minute < endMin;
  return minute >= startMin || minute < endMin;
}

const area = (f: Feeder | undefined) => f?.ibc ?? f?.circle ?? (f?.grid ? `grid ${f.grid}` : null);
const cmp = (a: string, b: string) => (a < b ? -1 : a > b ? 1 : 0);

export function darkNow(
  data: DarkNowData,
  instant: Date,
  level: IescoLevel | null = null,
): DarkNowResult {
  if (level !== null && !IESCO_LEVELS.includes(level)) {
    throw new Error(`IESCO level must be one of ${IESCO_LEVELS.join(", ")}`);
  }
  const minute = karachiMinuteOfDay(instant);
  const today = karachiDate(instant);
  const hour = Math.floor(minute / 60);
  const byId = new Map(data.feeders.map((f) => [f.feeder_id, f]));
  const rows: DarkRow[] = [];
  const notYet = new Map<string, DarkNote>();

  for (const p of data.profiles) {
    const feeder = byId.get(p.feeder_id);
    const base = {
      feederId: p.feeder_id,
      feederName: feeder?.name ?? p.feeder_id,
      source: p.source,
      area: area(feeder),
      effectiveFrom: p.effective_from,
    };
    const hasWindows = (p.daily_windows?.length ?? 0) > 0;
    const levelHours = level !== null ? p.scenario_levels?.[String(level)] : undefined;
    if (!hasWindows && !levelHours) continue;
    // ISO dates compare correctly as strings.
    if (p.effective_from > today) {
      notYet.set(`${p.source} ${p.effective_from}`, {
        kind: "not_yet_effective",
        source: p.source,
        effectiveFrom: p.effective_from,
      });
      continue;
    }
    for (const w of p.daily_windows ?? []) {
      if (windowActive(w.start_min, w.end_min, minute)) {
        rows.push({ ...base, kind: "daily_cycle", windowLocal: `${hhmm(w.start_min)}-${hhmm(w.end_min)}` });
      }
    }
    // IESCO slots are whole local hours (checked at export), so 60 means the whole hour is dark.
    if (levelHours && levelHours[hour] === 60) {
      rows.push({
        ...base,
        kind: `scenario_level_${level!}`,
        windowLocal: `${hhmm(hour * 60)}-${hhmm(hour * 60 + 60)}`,
      });
    }
  }

  const notes: DarkNote[] = [...notYet.entries()]
    .sort(([a], [b]) => cmp(a, b))
    .map(([, note]) => note);
  if (level === null) notes.push({ kind: "iesco_level_not_chosen" });

  const at = instant.getTime();
  let unmatched = 0;
  for (const s of data.shutdowns) {
    if (!(Date.parse(s.start_utc) <= at && at < Date.parse(s.end_utc))) continue;
    const feeder = s.feeder_id ? byId.get(s.feeder_id) : undefined;
    rows.push({
      feederId: s.feeder_id,
      feederName: feeder?.name ?? s.feeder_name_as_printed,
      source: "iesco",
      kind: "planned_shutdown",
      area: s.circle_as_printed,
      windowLocal: `${s.start_local}-${s.end_local}`,
      effectiveFrom: s.outage_date,
      matchState: s.feeder_match_state,
    });
    if (s.feeder_match_state !== "matched") unmatched += 1;
  }
  if (unmatched) notes.push({ kind: "unmatched_shutdowns", count: unmatched });

  // Announced maintenance: a GSO row repeating a circle file's window counts once (the circle's).
  let unlinked = 0;
  for (const m of data.maintenance ?? []) {
    if (m.repeats_circle_window) continue;
    if (!(Date.parse(m.start_utc) <= at && at < Date.parse(m.end_utc))) continue;
    const feeder = m.feeder_id ? byId.get(m.feeder_id) : undefined;
    rows.push({
      feederId: m.feeder_id,
      feederName: feeder?.name ?? m.feeder_name_as_printed ?? m.feeder_code ?? "",
      source: "iesco",
      kind: "maintenance",
      area: m.item,
      windowLocal: `${m.start_local}-${m.end_local}`,
      effectiveFrom: m.outage_date,
    });
    if (!m.feeder_id) unlinked += 1;
  }
  if (unlinked) notes.push({ kind: "unlinked_maintenance", count: unlinked });

  rows.sort(
    (a, b) =>
      cmp(a.kind, b.kind) ||
      cmp(a.source, b.source) ||
      cmp(a.area ?? "", b.area ?? "") ||
      cmp(a.feederName, b.feederName) ||
      cmp(a.feederId ?? "", b.feederId ?? "") ||
      cmp(a.windowLocal, b.windowLocal),
  );
  return { minuteOfDay: minute, localDate: today, level, rows, notes };
}

export interface WindowStatus {
  /** True when `minute` is inside a window; then start/end are that window. */
  active: boolean;
  start: number;
  end: number;
  /** Minutes to the window's end if active, else to its start (wrapping to the next day). */
  minutesUntil: number;
}

/** The scheduled window covering `minute`, else the next one to start (same [start, end) and
 *  midnight-wrap semantics as `windowActive`; an end of 1440 means midnight). Null if none. */
export function windowStatus(windows: { start: number; end: number }[], minute: number): WindowStatus | null {
  const until = (m: number) => (((m - minute) % 1440) + 1440) % 1440;
  const current = windows.find((w) => windowActive(w.start, w.end % 1440, minute));
  if (current) return { active: true, ...current, minutesUntil: until(current.end) || 1440 };
  const next = [...windows].sort((a, b) => until(a.start) - until(b.start))[0];
  return next ? { active: false, ...next, minutesUntil: until(next.start) } : null;
}
