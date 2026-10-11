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

/** Format a UTC ISO timestamp in Karachi time, e.g. "11 Oct 2026, 20:43". */
export function formatKarachi(isoUtc: string, locale = "en-GB"): string {
  return new Intl.DateTimeFormat(locale, {
    timeZone: TIME_ZONE,
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).format(new Date(isoUtc));
}
