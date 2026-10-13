// Display is always Asia/Karachi: UTC+5, fixed, no DST (CLAUDE.md). Data stays UTC.
export const KARACHI_OFFSET_MIN = 5 * 60;
export const TIME_ZONE = "Asia/Karachi";

/** Minutes since local (Karachi) midnight for an instant, independent of the browser's zone. */
export function karachiMinuteOfDay(instant: Date): number {
  const minutes = Math.floor(instant.getTime() / 60000) + KARACHI_OFFSET_MIN;
  return ((minutes % 1440) + 1440) % 1440;
}

/** Karachi calendar date (YYYY-MM-DD) for an instant. */
export function karachiDate(instant: Date): string {
  return new Date(instant.getTime() + KARACHI_OFFSET_MIN * 60000).toISOString().slice(0, 10);
}

/** "HH:MM" for minutes since midnight; 1440 prints as 24:00 (end of an IESCO 23-24 slot). */
export function hhmm(minuteOfDay: number): string {
  const h = Math.floor(minuteOfDay / 60);
  const m = minuteOfDay % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

/** Minutes since midnight from "HH:MM" (as exported). */
export function parseHhmm(value: string): number {
  const [h, m] = value.split(":").map(Number);
  return h * 60 + m;
}

export type ClockMode = "24" | "12";
export type DayHalves = { am: string; pm: string };

/** A time of day in the chosen clock. 12-hour: "3:35 PM"; minute 1440 (end of day) is 12:00 AM. */
export function clockText(minuteOfDay: number, mode: ClockMode, halves: DayHalves): string {
  if (mode === "24") return hhmm(minuteOfDay);
  const m = minuteOfDay % 1440;
  const h = Math.floor(m / 60);
  return `${h % 12 || 12}:${String(m % 60).padStart(2, "0")} ${h < 12 ? halves.am : halves.pm}`;
}

/** One date format everywhere: ISO "YYYY-MM-DD" (Karachi calendar date for an instant). */
export function karachiStamp(isoUtc: string): { date: string; minute: number } {
  const d = new Date(isoUtc);
  return { date: karachiDate(d), minute: karachiMinuteOfDay(d) };
}

/** "2026-10-12 17:21" (24-hour) for a UTC timestamp; the clock toggle re-renders it on the page. */
export function formatKarachi(isoUtc: string): string {
  const { date, minute } = karachiStamp(isoUtc);
  return `${date} ${hhmm(minute)}`;
}

/** Monday (YYYY-MM-DD) of an ISO week such as "2026-W42". */
export function isoWeekMonday(isoWeek: string): string {
  const [, y, w] = /^(\d{4})-W(\d{2})$/.exec(isoWeek) ?? [];
  if (!y) return isoWeek;
  const jan4 = new Date(Date.UTC(Number(y), 0, 4));
  const monday = new Date(jan4.getTime() - ((jan4.getUTCDay() + 6) % 7) * 86400000);
  return new Date(monday.getTime() + (Number(w) - 1) * 7 * 86400000).toISOString().slice(0, 10);
}

/** "10/2026" (press-release month as printed) -> "2026-10". */
export function isoMonth(period: string): string {
  const m = /^(\d{1,2})\/(\d{4})$/.exec(period.trim());
  return m ? `${m[2]}-${m[1].padStart(2, "0")}` : period;
}
