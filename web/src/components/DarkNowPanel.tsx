"use client";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import type { Dictionary } from "@/i18n/dictionaries";
import { fill } from "@/i18n/fill";
import { darkNow, IESCO_LEVELS, type DarkNote, type DarkRow, type IescoLevel } from "@/lib/darkNow";
import { num } from "@/lib/format";
import { circleName, ibcName } from "@/lib/names";
import { KARACHI_OFFSET_MIN, parseHhmm } from "@/lib/time";
import { feederHref } from "@/lib/urls";
import { useExport } from "@/lib/useExport";
import { ScrollRegion } from "@/components/ScrollRegion";
import { useClock, useClockMode } from "@/components/Clock";
import { usePin } from "@/lib/pin";

type Strings = Pick<Dictionary, "home" | "common" | "matchState" | "sources" | "lead" | "maintenance"> & {
  halves: { am: string; pm: string };
};
const PREVIEW_ROWS = 25;

/** "YYYY-MM-DDTHH:MM" Karachi wall time, the value format of <input type="datetime-local">. */
const toInput = (d: Date) =>
  new Date(d.getTime() + KARACHI_OFFSET_MIN * 60000).toISOString().slice(0, 16);
/** The input's value is Karachi wall time, whatever the browser's own zone is. */
const fromInput = (v: string) => new Date(`${v}:00+05:00`);
const VALUE = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/;
const pad = (n: number) => String(n).padStart(2, "0");

/** Area column: the IBC without its "IBC - " prefix, or the IESCO circle's name; for maintenance,
 *  the schedule file's listing row (a circle, grid stations or construction). */
const areaText = (r: DarkRow, t: Strings) =>
  r.kind === "maintenance"
    ? ((t.maintenance.items as Record<string, string>)[r.area ?? ""] ?? r.area ?? "")
    : r.area
      ? (circleName(ibcName(r.area)) ?? r.area)
      : "";

/** Time, level and search live in the URL (?at=2026-10-13T17:40&level=12&q=...), so a view can be
 *  bookmarked or shared. Read once after mount (static export: no server-side search params). */
function readUrl() {
  const p = new URLSearchParams(window.location.search);
  const at = p.get("at");
  const level = Number(p.get("level"));
  return {
    at: at && VALUE.test(at) ? at : null,
    level: (IESCO_LEVELS as readonly number[]).includes(level) ? (level as IescoLevel) : null,
    q: p.get("q") ?? "",
  };
}

function writeUrl(at: string | null, level: IescoLevel | null, q: string) {
  const p = new URLSearchParams();
  if (at) p.set("at", at);
  if (level !== null) p.set("level", String(level));
  if (q.trim()) p.set("q", q.trim());
  const search = p.toString();
  window.history.replaceState(null, "", `${window.location.pathname}${search ? `?${search}` : ""}`);
}

export function DarkNowPanel({ locale, t, counts }: { locale: string; t: Strings; counts: string }) {
  const state = useExport(["feeders", "dark_profiles", "planned_shutdowns"] as const);
  // Large; loaded on its own so the schedules above never wait for it.
  const maint = useExport(["maintenance"] as const);
  const [chosen, setChosen] = useState<string | null>(null); // null = follow the clock
  const [now, setNow] = useState<Date | null>(null);
  const [level, setLevel] = useState<IescoLevel | null>(null);
  const [query, setQuery] = useState("");
  const loaded = useRef(false);
  const clock = useClock();
  const pin = usePin();

  useEffect(() => {
    const u = readUrl();
    /* eslint-disable react-hooks/set-state-in-effect -- one-time read of the URL after hydration */
    setChosen(u.at);
    setLevel(u.level);
    setQuery(u.q);
    /* eslint-enable react-hooks/set-state-in-effect */
    loaded.current = true;
  }, []);
  useEffect(() => {
    if (loaded.current) writeUrl(chosen, level, query);
  }, [chosen, level, query]);

  useEffect(() => {
    // The clock only starts in the browser, so the static HTML never shows a build-time "now".
    const tick = () => setNow(new Date());
    tick();
    const id = setInterval(tick, 30_000);
    return () => clearInterval(id);
  }, []);

  const instant = chosen ? fromInput(chosen) : now;
  const result = useMemo(() => {
    if (state.status !== "ready" || !instant || Number.isNaN(instant.getTime())) return null;
    const { feeders, dark_profiles, planned_shutdowns } = state.data;
    return darkNow(
      {
        feeders: feeders.data,
        profiles: dark_profiles.data,
        shutdowns: planned_shutdowns.data,
        maintenance: maint.status === "ready" ? maint.data.maintenance.data : undefined,
      },
      instant,
      level,
    );
    // Recompute per minute, not per render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state, maint, instant && Math.floor(instant.getTime() / 60000), level]);

  const grids = useMemo(
    () =>
      state.status === "ready"
        ? new Map(state.data.feeders.data.map((f) => [f.feeder_id, f.grid ?? ""]))
        : new Map<string, string>(),
    [state],
  );
  const q = query.trim().toLowerCase();
  const rows = (result?.rows ?? []).filter(
    (r) =>
      !q ||
      [r.feederName, r.feederId ?? "", r.area ?? "", areaText(r, t), grids.get(r.feederId ?? "") ?? ""]
        .join(" ")
        .toLowerCase()
        .includes(q),
  );
  const daily = rows.filter((r) => r.kind === "daily_cycle");
  const scenario = rows.filter((r) => r.kind.startsWith("scenario_level_"));
  const planned = rows.filter((r) => r.kind === "planned_shutdown");
  const maintenance = rows.filter((r) => r.kind === "maintenance");

  const ready = state.status === "ready" ? state.data : null;
  const scheduled = useMemo(() => ready?.feeders.data.filter((f) => f.has_schedule) ?? [], [ready]);
  const profiles = useMemo(
    () => new Map((ready?.dark_profiles.data ?? []).map((p) => [p.feeder_id, p])),
    [ready],
  );
  const stats = useMemo(() => {
    if (!result) return null;
    const unique = (kind: (k: string) => boolean, source?: string) =>
      new Set(result.rows.filter((r) => kind(r.kind) && (!source || r.source === source)).map((r) => r.feederId)).size;
    const keTotal = [...profiles.values()].filter(
      (p) => p.source === "kelectric" && (p.daily_windows?.length ?? 0) > 0 && p.effective_from <= result.localDate,
    ).length;
    return {
      ke: unique((k) => k === "daily_cycle", "kelectric"),
      keTotal,
      planned: result.rows.filter((r) => r.kind === "planned_shutdown").length,
      maintenance: result.rows.filter((r) => r.kind === "maintenance").length,
      scenario: unique((k) => k.startsWith("scenario_level_")),
    };
  }, [result, profiles]);
  const pinned = pin ? scheduled.find((f) => f.feeder_id === pin) : undefined;
  const time = result ? clock(result.minuteOfDay) : "";

  return (
    <div className="space-y-10">
      <div className="space-y-4">
        {/* The visitor's own feeder lives on its own tab (owner, 2026-10-20); here only a pointer. */}
        <p className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
          <span className="kicker">{t.lead.kicker}</span>
          <span className="headline text-xl sm:text-2xl">
            {pinned ? fill(t.home.yourFeederPinned, { name: pinned.name }, locale) : t.home.yourFeederNone}
          </span>
          <Link prefetch={false} href={`/${locale}/my-feeder/`} transitionTypes={["nav-forward"]} className="link">
            {t.home.yourFeederOpen}
          </Link>
        </p>
        <aside
          aria-label={t.lead.statsLabel}
          className="rule grid grid-cols-2 sm:grid-cols-4 gap-x-6"
        >
          <Stat value={stats ? num(stats.ke, locale) : "–"} text={fill(t.lead.statKe, { total: stats ? stats.keTotal : "–", time }, locale)} />
          <Stat value={stats ? num(stats.planned, locale) : "–"} text={fill(t.lead.statPlanned, { time }, locale)} />
          <Stat
            value={stats && maint.status === "ready" ? num(stats.maintenance, locale) : "–"}
            text={fill(t.lead.statMaintenance, { time }, locale)}
          />
          {level !== null ? (
            <Stat
              value={stats ? num(stats.scenario, locale) : "–"}
              text={fill(t.lead.statLevel, { n: level, time }, locale)}
            />
          ) : (
            <p className="col-span-2 sm:col-span-1 py-3 text-sm text-muted rule-thin">{t.lead.statLevelNone}</p>
          )}
        </aside>
      </div>

      <section aria-labelledby="listings" className="rule pt-4 space-y-5">
        <div className="space-y-2">
          <p className="kicker">{t.lead.listingsKicker}</p>
          <h2 id="listings" className="headline text-3xl sm:text-4xl">
            {t.home.title}
          </h2>
          <p className="max-w-prose">{t.home.intro}</p>
          <p className="text-sm text-muted">{counts}</p>
        </div>
      <form className="grid gap-3 sm:grid-cols-3 items-end" onSubmit={(e) => e.preventDefault()}>
        <WhenField
          value={chosen ?? (now ? toInput(now) : "")}
          following={!chosen}
          onChange={setChosen}
          t={t}
        />
        <label className="grid gap-1 text-sm">
          <span className="kicker">{t.home.level}</span>
          <select
            className="field"
            value={level ?? ""}
            onChange={(e) => setLevel(e.target.value ? (Number(e.target.value) as IescoLevel) : null)}
          >
            <option value="">{t.home.levelNone}</option>
            {IESCO_LEVELS.map((n) => (
              <option key={n} value={n}>
                {fill(t.home.levelOption, { n }, locale)}
              </option>
            ))}
          </select>
        </label>
        <label className="grid gap-1 text-sm">
          <span className="kicker">{t.common.search}</span>
          <input
            type="search"
            className="field"
            placeholder={t.common.searchPlaceholder}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </label>
      </form>

      {state.status === "error" && <p role="alert">{t.common.loadError}</p>}
      {(state.status === "loading" || !result) && state.status !== "error" && (
        <div className="space-y-3">
          <p className="text-muted">{t.common.loading}</p>
          <Skeleton lines={5} />
        </div>
      )}

      {result && (
        <>
          <p aria-live="polite" className="headline text-xl stagger-in" key={`${result.localDate}${result.minuteOfDay}${level}`}>
            {/* No grand total: IESCO rows are "if level N", not the published daily schedule. */}
            {fill(t.home.summary, { time: clock(result.minuteOfDay), date: result.localDate }, locale)}
          </p>
          {result.notes.length > 0 && (
            <ul className="space-y-1 text-sm text-muted">
              {result.notes.map((n, i) => (
                <li key={i}>{noteText(n, t, locale)}</li>
              ))}
            </ul>
          )}
          <Group title={t.home.groupDaily} rows={daily} locale={locale} t={t} />
          {level !== null && (
            <Group title={fill(t.home.groupScenario, { n: level }, locale)} rows={scenario} locale={locale} t={t} />
          )}
          <Group title={t.home.groupPlanned} rows={planned} locale={locale} t={t} />
          <Group
            title={t.home.groupMaintenance}
            note={t.home.groupMaintenanceNote}
            rows={maintenance}
            status={maint.status}
            locale={locale}
            t={t}
          />
        </>
      )}
      </section>
    </div>
  );
}

/** Placeholder rows while the schedules load (shimmer only when motion is welcome). */
function Skeleton({ lines }: { lines: number }) {
  return (
    <div aria-hidden="true" className="space-y-2 max-w-xl">
      {Array.from({ length: lines }, (_, i) => (
        <div key={i} className="skeleton h-4" style={{ width: `${90 - ((i * 23) % 40)}%` }} />
      ))}
    </div>
  );
}

function Stat({ value, text }: { value: string; text: string }) {
  return (
    <p className="py-3 lg:border-t lg:border-line lg:first:border-t-0">
      <span className="block headline text-5xl tabular-nums">{value}</span>
      <span className="block text-sm">{text}</span>
    </p>
  );
}

function noteText(n: DarkNote, t: Strings, locale: string): string {
  switch (n.kind) {
    case "not_yet_effective":
      return fill(t.home.noteNotYet, { source: t.sources[n.source as "iesco" | "kelectric"] ?? n.source, date: n.effectiveFrom }, locale);
    case "iesco_level_not_chosen":
      return t.home.noteLevel;
    case "unmatched_shutdowns":
      return fill(t.home.noteUnmatched, { n: n.count }, locale);
    case "unlinked_maintenance":
      return fill(t.home.noteUnlinkedMaintenance, { n: n.count }, locale);
  }
}

function WindowText({ value }: { value: string }) {
  const clock = useClock();
  const [start, end] = value.split("-");
  return (
    <span dir="ltr">
      {clock(parseHhmm(start))}–{clock(parseHhmm(end))}
    </span>
  );
}

/** Date (ISO, native calendar on click) plus hour and minute lists in the viewer's clock, instead
 *  of <input type="datetime-local">, whose format follows the browser's locale. */
function WhenField({
  value,
  following,
  onChange,
  t,
}: {
  value: string;
  following: boolean;
  onChange: (v: string | null) => void;
  t: Strings;
}) {
  const mode = useClockMode();
  const date = value.slice(0, 10);
  const hour = Number(value.slice(11, 13)) || 0;
  const minute = Number(value.slice(14, 16)) || 0;
  const set = (d: string, h: number, m: number) => d && onChange(`${d}T${pad(h)}:${pad(m)}`);
  const hourText = (h: number) =>
    mode === "24" ? pad(h) : `${h % 12 || 12} ${h < 12 ? t.halves.am : t.halves.pm}`;
  return (
    <fieldset className="grid gap-1 text-sm min-w-0">
      <legend className="kicker mb-1">{t.home.time}</legend>
      <div className="flex flex-wrap gap-2" dir="ltr">
        <label className="field relative flex items-center gap-2 cursor-pointer focus-within:outline-2 focus-within:outline-accent tabular-nums">
          <span className="sr-only">{t.home.date}</span>
          <span aria-hidden="true">{date || "––––-––-––"}</span>
          <svg aria-hidden="true" viewBox="0 0 16 16" className="h-4 w-4 fill-none stroke-current text-muted">
            <rect x="2" y="3" width="12" height="11" rx="1.5" />
            <path d="M2 6.5h12M5 1.5v3M11 1.5v3" />
          </svg>
          <input
            type="date"
            className="absolute inset-0 opacity-0 cursor-pointer"
            value={date}
            onChange={(e) => set(e.target.value, hour, minute)}
            onClick={(e) => {
              try {
                e.currentTarget.showPicker();
              } catch {
                // Older browsers open their own picker or accept typing.
              }
            }}
          />
        </label>
        <label>
          <span className="sr-only">{t.home.hour}</span>
          <select className="field tabular-nums" value={hour} onChange={(e) => set(date, Number(e.target.value), minute)}>
            {Array.from({ length: 24 }, (_, h) => (
              <option key={h} value={h}>
                {hourText(h)}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span className="sr-only">{t.home.minute}</span>
          <select className="field tabular-nums" value={minute} onChange={(e) => set(date, hour, Number(e.target.value))}>
            {Array.from({ length: 60 }, (_, m) => (
              <option key={m} value={m}>
                {`:${pad(m)}`}
              </option>
            ))}
          </select>
        </label>
      </div>
      {!following && (
        <button type="button" className="link text-start w-fit" onClick={() => onChange(null)}>
          {t.home.useNow}
        </button>
      )}
    </fieldset>
  );
}

function Group({
  title,
  note,
  rows,
  status = "ready",
  locale,
  t,
}: {
  title: string;
  note?: string;
  rows: DarkRow[];
  /** Load state of a document fetched apart from the schedules (maintenance). */
  status?: "loading" | "error" | "ready";
  locale: string;
  t: Strings;
}) {
  const [all, setAll] = useState(false);
  const shown = all ? rows : rows.slice(0, PREVIEW_ROWS);
  return (
    <section className="space-y-2">
      <h3 className="headline text-2xl">
        {title}{" "}
        {status === "ready" && <span className="font-mono text-base text-muted">({num(rows.length, locale)})</span>}
      </h3>
      {note && <p className="text-sm text-muted max-w-prose">{note}</p>}
      {status === "loading" ? (
        <p className="text-muted">{t.common.loading}</p>
      ) : status === "error" ? (
        <p role="alert">{t.common.loadError}</p>
      ) : rows.length === 0 ? (
        <p className="text-muted">{t.common.none}</p>
      ) : (
        <ScrollRegion label={title}>
          <table className="data">
            <thead>
              <tr>
                <th scope="col">{t.common.feeder}</th>
                <th scope="col">{t.common.area}</th>
                <th scope="col">{t.common.window}</th>
                <th scope="col" className="hidden sm:table-cell">
                  {t.common.effectiveFrom}
                </th>
              </tr>
            </thead>
            <tbody>
              {shown.map((r, i) => (
                <tr key={`${r.feederId}-${r.windowLocal}-${i}`}>
                  <td>
                    {r.feederId && (r.matchState ?? "matched") === "matched" ? (
                      <Link prefetch={false} href={feederHref(locale, r.feederId)} className="link">
                        <bdi>{r.feederName}</bdi>
                      </Link>
                    ) : (
                      <>
                        <bdi>{r.feederName}</bdi>
                        {r.matchState && (
                          <span className="block text-xs text-muted">{t.matchState[r.matchState]}</span>
                        )}
                      </>
                    )}
                  </td>
                  <td>
                    <bdi>{areaText(r, t)}</bdi>
                  </td>
                  <td className="tabular-nums whitespace-nowrap">
                    <WindowText value={r.windowLocal} />
                    <span className="block text-xs text-muted sm:hidden">
                      {t.common.effectiveFrom} {r.effectiveFrom}
                    </span>
                  </td>
                  <td className="hidden sm:table-cell tabular-nums whitespace-nowrap">{r.effectiveFrom}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollRegion>
      )}
      {rows.length > PREVIEW_ROWS && (
        <button type="button" className="link" onClick={() => setAll(!all)}>
          {all ? t.common.showFewer : fill(t.common.showAll, { n: rows.length }, locale)}
        </button>
      )}
    </section>
  );
}
