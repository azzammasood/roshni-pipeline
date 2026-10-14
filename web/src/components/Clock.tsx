"use client";
// Site-wide 24/12-hour preference. Static HTML is always 24-hour (the server has no preference);
// the browser re-renders times in the chosen clock after hydration. Stored per viewer only.
import { createContext, useCallback, useContext, useEffect, useState, useSyncExternalStore, type ReactNode } from "react";
import {
  clockText,
  hhmm,
  karachiDate,
  karachiMinuteOfDay,
  karachiStamp,
  parseHhmm,
  type ClockMode,
  type DayHalves,
} from "@/lib/time";

const KEY = "roshni:clock";
const EVENT = "roshni:clock";

function readMode(): ClockMode {
  try {
    return localStorage.getItem(KEY) === "12" ? "12" : "24";
  } catch {
    return "24";
  }
}

function subscribe(onChange: () => void) {
  window.addEventListener(EVENT, onChange);
  window.addEventListener("storage", onChange);
  return () => {
    window.removeEventListener(EVENT, onChange);
    window.removeEventListener("storage", onChange);
  };
}

export function setClockMode(mode: ClockMode) {
  try {
    localStorage.setItem(KEY, mode);
  } catch {
    // Private mode or blocked storage: the choice lasts for this page only.
  }
  window.dispatchEvent(new Event(EVENT));
}

export const useClockMode = () => useSyncExternalStore(subscribe, readMode, () => "24" as ClockMode);

const Halves = createContext<DayHalves>({ am: "AM", pm: "PM" });

export function ClockProvider({ halves, children }: { halves: DayHalves; children: ReactNode }) {
  return <Halves.Provider value={halves}>{children}</Halves.Provider>;
}

/** Formatter for minutes since midnight in the viewer's clock. */
export function useClock() {
  const mode = useClockMode();
  const halves = useContext(Halves);
  return useCallback((minute: number) => clockText(minute, mode, halves), [mode, halves]);
}

/** "15:35–18:35" or "3:35 PM–6:35 PM". Accepts minutes or exported "HH:MM" strings. */
export function ClockRange({ start, end }: { start: number | string; end: number | string }) {
  const clock = useClock();
  const m = (v: number | string) => (typeof v === "string" ? parseHhmm(v) : v);
  return (
    <span dir="ltr" className="tabular-nums whitespace-nowrap">
      {clock(m(start))}–{clock(m(end))}
    </span>
  );
}

/** A UTC timestamp as "2026-10-13 17:21" (date always ISO, time in the viewer's clock). */
export function Stamp({ iso }: { iso: string }) {
  const clock = useClock();
  const { date, minute } = karachiStamp(iso);
  return (
    <time dateTime={iso} dir="ltr" className="tabular-nums">
      {date} {clock(minute)}
    </time>
  );
}

/** The current Karachi date and time ("2026-10-13 15:10"), ticking each 30 s. Empty in the static
 *  HTML so a build-time "now" is never shown. */
export function NowStamp() {
  const clock = useClock();
  const [now, setNow] = useState<Date | null>(null);
  useEffect(() => {
    const tick = () => setNow(new Date());
    tick();
    const id = setInterval(tick, 30_000);
    return () => clearInterval(id);
  }, []);
  if (!now) return null;
  return (
    <time dateTime={now.toISOString()} dir="ltr" className="tabular-nums">
      {karachiDate(now)} {clock(karachiMinuteOfDay(now))}
    </time>
  );
}

/** Hour-of-day axis label: "06" (24-hour) or "6 AM" (12-hour); 24 is the closing midnight. */
export function HourLabel({ hour, compact }: { hour: number; compact?: boolean }) {
  const mode = useClockMode();
  const halves = useContext(Halves);
  if (mode === "24") return <>{hhmm(hour * 60).slice(0, 2)}</>;
  const h = hour % 12 || 12;
  return <>{compact ? h : `${h} ${hour < 12 || hour === 24 ? halves.am : halves.pm}`}</>;
}

/** Shows `am`/`pm` only in 12-hour mode (e.g. a header row above compact hour labels). */
export function In12h({ children }: { children: ReactNode }) {
  return useClockMode() === "12" ? <>{children}</> : null;
}

export function ClockToggle({ label, h24, h12 }: { label: string; h24: string; h12: string }) {
  const mode = useClockMode();
  return (
    <span role="group" aria-label={label} className="inline-flex rounded border border-line text-xs" dir="ltr">
      {(
        [
          ["24", h24],
          ["12", h12],
        ] as const
      ).map(([value, text]) => (
        <button
          key={value}
          type="button"
          aria-pressed={mode === value}
          onClick={() => setClockMode(value)}
          className={`px-2 py-0.5 ${mode === value ? "bg-dark text-bg" : "text-muted"}`}
        >
          {text}
        </button>
      ))}
    </span>
  );
}
