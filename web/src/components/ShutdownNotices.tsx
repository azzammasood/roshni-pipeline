"use client";
// Press-release planned shutdowns for today and the next days, as dated notice columns above the
// full table. "Today" comes from the browser clock in Karachi time, read after mount only.
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import type { Dictionary } from "@/i18n/dictionaries";
import { fill } from "@/i18n/fill";
import { karachiDate } from "@/lib/time";
import { feederHref } from "@/lib/urls";
import { useExport } from "@/lib/useExport";
import { ClockRange } from "@/components/Clock";

const DAYS = 3;
const PER_DAY = 6;

export function ShutdownNotices({
  locale,
  maintDays,
  t,
}: {
  locale: string;
  /** Announced maintenance windows and feeders per date (IESCO's maintenance schedules). */
  maintDays: Record<string, { windows: number; feeders: number }>;
  t: Pick<Dictionary, "shutdowns" | "matchState">;
}) {
  const state = useExport(["feeders", "planned_shutdowns"] as const);
  const [today, setToday] = useState<string | null>(null);
  // eslint-disable-next-line react-hooks/set-state-in-effect -- the clock is read in the browser only
  useEffect(() => setToday(karachiDate(new Date())), []);

  const days = useMemo(() => {
    if (state.status !== "ready" || !today) return null;
    const byDate = new Map<string, typeof state.data.planned_shutdowns.data>();
    for (const s of state.data.planned_shutdowns.data) {
      if (s.outage_date < today) continue;
      byDate.set(s.outage_date, [...(byDate.get(s.outage_date) ?? []), s]);
    }
    return [...byDate.entries()]
      .sort(([a], [b]) => (a < b ? -1 : 1))
      .slice(0, DAYS)
      .map(([date, rows]) => [date, rows.sort((a, b) => a.start_utc.localeCompare(b.start_utc))] as const);
  }, [state, today]);
  const names = useMemo(
    () => new Map(state.status === "ready" ? state.data.feeders.data.map((f) => [f.feeder_id, f.name]) : []),
    [state],
  );

  if (!days) return null;
  const s = t.shutdowns;
  return (
    <section aria-labelledby="notices" className="space-y-3">
      <p className="kicker">{s.noticesKicker}</p>
      <h2 id="notices" className="headline text-3xl">
        {s.noticesTitle}
      </h2>
      {today && maintDays[today] && (
        <p className="max-w-prose">
          {fill(s.maintToday, { windows: maintDays[today].windows, feeders: maintDays[today].feeders }, locale)}{" "}
          <a href="#maintenance" className="link">
            {s.maintTodayLink}
          </a>
        </p>
      )}
      {days.length === 0 ? (
        <p>{s.noticesNone}</p>
      ) : (
        <div className="rule grid gap-x-6 sm:grid-cols-3">
          {days.map(([date, rows]) => (
            <article key={date} className="py-3 border-b border-line sm:border-b-0 sm:border-e sm:last:border-e-0 sm:pe-6 min-w-0">
              <h3 className="font-mono text-sm">
                <time dateTime={date} dir="ltr">
                  {date}
                </time>
                {date === today && <span className="mark ms-2 font-semibold">{s.today}</span>}
              </h3>
              <p className="headline text-4xl tabular-nums">{rows.length.toLocaleString(locale, { numberingSystem: "latn" })}</p>
              <p className="text-sm text-muted mb-2">{s.dayCount}</p>
              <ul className="space-y-1.5 text-sm">
                {rows.slice(0, PER_DAY).map((r) => {
                  const name = r.feeder_id ? names.get(r.feeder_id) : undefined;
                  return (
                    <li key={r.shutdown_id} className="flex gap-2">
                      <span className="shrink-0 font-mono text-xs pt-0.5">
                        <ClockRange start={r.start_local} end={r.end_local} />
                      </span>
                      <span className="min-w-0">
                        {r.feeder_id && name && r.feeder_match_state === "matched" ? (
                          <Link prefetch={false} href={feederHref(locale, r.feeder_id)} className="link">
                            <bdi>{name}</bdi>
                          </Link>
                        ) : (
                          <>
                            <bdi>{r.feeder_name_as_printed}</bdi>{" "}
                            <span className="text-xs text-muted">({t.matchState[r.feeder_match_state]})</span>
                          </>
                        )}
                        <span className="block text-xs text-muted">
                          <bdi>{r.circle_as_printed}</bdi>
                        </span>
                      </span>
                    </li>
                  );
                })}
              </ul>
              {rows.length > PER_DAY && (
                <p className="text-sm pt-2">
                  <a href="#all-shutdowns" className="link">
                    {fill(s.moreBelow, { n: rows.length - PER_DAY }, locale)}
                  </a>
                </p>
              )}
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
