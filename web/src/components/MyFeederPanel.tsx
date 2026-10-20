"use client";
// "My feeder" tab: find and pin a feeder, then everything Roshni knows about that one feeder:
// the lead story (now or next scheduled window), what is coming up (announced maintenance and
// press-release shutdowns from today on), and its hours a day under each schedule. The pin is
// kept in this browser only (lib/pin).
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import type { Dictionary } from "@/i18n/dictionaries";
import { fill } from "@/i18n/fill";
import { IESCO_LEVELS, type IescoLevel } from "@/lib/darkNow";
import { num } from "@/lib/format";
import { usePin } from "@/lib/pin";
import { karachiDate, karachiMinuteOfDay } from "@/lib/time";
import { feederHref } from "@/lib/urls";
import { useExport } from "@/lib/useExport";
import { ClockRange } from "@/components/Clock";
import { FeederFinder, PinnedFeeder, type LeadStrings } from "@/components/PinnedFeeder";
import { ScrollRegion } from "@/components/ScrollRegion";

type Strings = LeadStrings & Pick<Dictionary, "myFeeder" | "maintenance">;
const UPCOMING = 12;

export function MyFeederPanel({ locale, t }: { locale: string; t: Strings }) {
  const state = useExport(["feeders", "dark_profiles", "planned_shutdowns"] as const);
  // About 9 MB: loaded on its own so the lead never waits for it.
  const maint = useExport(["maintenance"] as const);
  const pin = usePin();
  const [now, setNow] = useState<Date | null>(null);
  const [level, setLevel] = useState<IescoLevel | null>(null);

  useEffect(() => {
    // The clock only starts in the browser, so the static HTML never shows a build-time "now".
    const tick = () => setNow(new Date());
    tick();
    const id = setInterval(tick, 30_000);
    return () => clearInterval(id);
  }, []);

  const ready = state.status === "ready" ? state.data : null;
  const scheduled = useMemo(() => ready?.feeders.data.filter((f) => f.has_schedule) ?? [], [ready]);
  const feeder = pin ? scheduled.find((f) => f.feeder_id === pin) : undefined;
  const profile = feeder ? ready?.dark_profiles.data.find((p) => p.feeder_id === feeder.feeder_id) : undefined;
  const today = now ? karachiDate(now) : null;
  const minute = now ? karachiMinuteOfDay(now) : 0;

  const maintenance = useMemo(
    () =>
      feeder && today && maint.status === "ready"
        ? maint.data.maintenance.data
            .filter((w) => w.feeder_id === feeder.feeder_id && !w.repeats_circle_window && w.outage_date >= today)
            .sort((a, b) => (a.outage_date + a.start_local).localeCompare(b.outage_date + b.start_local))
        : undefined,
    [feeder, today, maint],
  );
  const shutdowns = useMemo(
    () =>
      feeder && today && ready
        ? ready.planned_shutdowns.data
            .filter((s) => s.feeder_id === feeder.feeder_id && s.feeder_match_state === "matched" && s.outage_date >= today)
            .sort((a, b) => a.start_utc.localeCompare(b.start_utc))
        : [],
    [feeder, today, ready],
  );

  if (!ready || !today) {
    return (
      <section className="space-y-3">
        <p className="kicker">{t.lead.kicker}</p>
        <h1 id="lead" className="headline text-[2.1rem] sm:text-5xl">
          {t.lead.findTitle}
        </h1>
        <p className="text-muted">{state.status === "error" ? t.common.loadError : t.common.loading}</p>
      </section>
    );
  }
  if (!feeder) return <FeederFinder feeders={scheduled} locale={locale} t={t} />;

  const m = t.myFeeder;
  const upcoming = [
    ...(maintenance ?? []).map((w) => ({
      key: w.window_id,
      date: w.outage_date,
      start: w.start_local,
      end: w.end_local,
      kind: m.kindMaintenance,
      detail: w.purpose ?? "",
    })),
    ...shutdowns.map((s) => ({
      key: s.shutdown_id,
      date: s.outage_date,
      start: s.start_local,
      end: s.end_local,
      kind: m.kindShutdown,
      detail: "",
    })),
  ].sort((a, b) => (a.date + a.start).localeCompare(b.date + b.start));
  const hoursAt = (mins: number[]) => mins.reduce((a, b) => a + b, 0) / 60;
  const levels = feeder.source === "iesco" ? profile?.scenario_levels : null;
  // K-Electric: minutes in its daily windows (end <= start wraps midnight).
  const daily = profile?.daily_windows?.reduce((a, w) => a + ((w.end_min - w.start_min + 1440) % 1440 || 1440), 0);

  return (
    <div className="space-y-10">
      <PinnedFeeder
        feeders={scheduled}
        feeder={feeder}
        profile={profile}
        minute={minute}
        today={today}
        level={level}
        onLevel={setLevel}
        maintenance={maintenance}
        locale={locale}
        t={t}
      />

      <section className="rule pt-4 space-y-3">
        <h2 id="upcoming" className="headline text-3xl">
          {m.upcomingTitle}
        </h2>
        <p className="text-sm text-muted max-w-prose">{m.upcomingNote}</p>
        {maintenance === undefined && maint.status !== "error" ? (
          <p className="text-muted">{t.common.loading}</p>
        ) : upcoming.length === 0 ? (
          <p>{m.upcomingNone}</p>
        ) : (
          <ScrollRegion label={m.upcomingTitle}>
            <table className="data">
              <thead>
                <tr>
                  <th scope="col">{t.common.date}</th>
                  <th scope="col">{t.common.window}</th>
                  <th scope="col">{m.kind}</th>
                  <th scope="col" className="hidden sm:table-cell">
                    {t.maintenance.purpose}
                  </th>
                </tr>
              </thead>
              <tbody>
                {upcoming.slice(0, UPCOMING).map((u) => (
                  <tr key={u.key}>
                    <td className="tabular-nums whitespace-nowrap">
                      {u.date}
                      {u.date === today && <span className="mark ms-2 font-semibold">{m.today}</span>}
                    </td>
                    <td>
                      <ClockRange start={u.start} end={u.end} />
                    </td>
                    <td>{u.kind}</td>
                    <td className="hidden sm:table-cell">
                      <bdi>{u.detail || "–"}</bdi>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </ScrollRegion>
        )}
        {upcoming.length > UPCOMING && (
          <p className="text-sm">{fill(m.upcomingMore, { n: num(upcoming.length - UPCOMING, locale) }, locale)}</p>
        )}
      </section>

      {(levels || daily) && (
        <section aria-labelledby="hours" className="rule pt-4 space-y-3">
          <h2 id="hours" className="headline text-3xl">
            {m.hoursTitle}
          </h2>
          <p className="text-sm text-muted max-w-prose">{levels ? m.hoursNoteIesco : m.hoursNoteKe}</p>
          {levels ? (
            <ul className="grid grid-cols-3 sm:grid-cols-6 gap-x-4">
              {IESCO_LEVELS.filter((n) => levels[String(n)]).map((n) => (
                <li key={n} className="border-b border-line py-2">
                  <button
                    type="button"
                    aria-pressed={level === n}
                    onClick={() => setLevel(level === n ? null : n)}
                    className="w-full text-start"
                  >
                    <span className={`headline text-3xl tabular-nums block ${level === n ? "mark" : ""}`}>
                      {num(hoursAt(levels[String(n)]), locale)}
                    </span>
                    <span className="text-sm">{fill(m.levelHours, { n }, locale)}</span>
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p>
              <span className="headline text-5xl tabular-nums">{num(Math.round((daily! / 60) * 10) / 10, locale)}</span>{" "}
              <span>{m.dailyHours}</span>
            </p>
          )}
        </section>
      )}

      <p className="rule pt-4">
        <Link prefetch={false} href={feederHref(locale, feeder.feeder_id)} className="link">
          {m.fullLink}
        </Link>
      </p>
    </div>
  );
}
