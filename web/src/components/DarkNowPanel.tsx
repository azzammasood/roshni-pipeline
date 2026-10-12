"use client";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import type { Dictionary } from "@/i18n/dictionaries";
import { fill } from "@/i18n/fill";
import { darkNow, IESCO_LEVELS, type DarkNote, type DarkRow, type IescoLevel } from "@/lib/darkNow";
import { hhmm, KARACHI_OFFSET_MIN } from "@/lib/time";
import { feederHref } from "@/lib/urls";
import { useExport } from "@/lib/useExport";
import { ScrollRegion } from "@/components/ScrollRegion";

type Strings = Pick<Dictionary, "home" | "common" | "matchState" | "sources">;
const PREVIEW_ROWS = 25;

/** "YYYY-MM-DDTHH:MM" Karachi wall time, the value format of <input type="datetime-local">. */
const toInput = (d: Date) =>
  new Date(d.getTime() + KARACHI_OFFSET_MIN * 60000).toISOString().slice(0, 16);
/** The input's value is Karachi wall time, whatever the browser's own zone is. */
const fromInput = (v: string) => new Date(`${v}:00+05:00`);

export function DarkNowPanel({ locale, t }: { locale: string; t: Strings }) {
  const state = useExport(["feeders", "dark_profiles", "planned_shutdowns"] as const);
  const [chosen, setChosen] = useState<string | null>(null); // null = follow the clock
  const [now, setNow] = useState<Date | null>(null);
  const [level, setLevel] = useState<IescoLevel | null>(null);
  const [query, setQuery] = useState("");

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
      { feeders: feeders.data, profiles: dark_profiles.data, shutdowns: planned_shutdowns.data },
      instant,
      level,
    );
    // Recompute per minute, not per render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state, instant && Math.floor(instant.getTime() / 60000), level]);

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
      [r.feederName, r.feederId ?? "", r.area ?? "", grids.get(r.feederId ?? "") ?? ""]
        .join(" ")
        .toLowerCase()
        .includes(q),
  );
  const daily = rows.filter((r) => r.kind === "daily_cycle");
  const scenario = rows.filter((r) => r.kind.startsWith("scenario_level_"));
  const planned = rows.filter((r) => r.kind === "planned_shutdown");

  return (
    <div className="space-y-5">
      <form className="grid gap-3 sm:grid-cols-3 items-end" onSubmit={(e) => e.preventDefault()}>
        <label className="grid gap-1 text-sm">
          <span className="font-medium">{t.home.time}</span>
          <input
            type="datetime-local"
            className="field"
            value={chosen ?? (now ? toInput(now) : "")}
            onChange={(e) => setChosen(e.target.value || null)}
          />
          {chosen && (
            <button type="button" className="link text-start" onClick={() => setChosen(null)}>
              {t.home.useNow}
            </button>
          )}
        </label>
        <label className="grid gap-1 text-sm">
          <span className="font-medium">{t.home.level}</span>
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
          <span className="font-medium">{t.common.search}</span>
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
        <p className="text-muted">{t.common.loading}</p>
      )}

      {result && (
        <>
          <p aria-live="polite" className="text-lg font-medium">
            {/* No grand total: IESCO rows are "if level N", not the published daily schedule. */}
            {fill(t.home.summary, { time: hhmm(result.minuteOfDay), date: result.localDate }, locale)}
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
        </>
      )}
    </div>
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
  }
}

function Group({ title, rows, locale, t }: { title: string; rows: DarkRow[]; locale: string; t: Strings }) {
  const [all, setAll] = useState(false);
  const shown = all ? rows : rows.slice(0, PREVIEW_ROWS);
  return (
    <section className="space-y-2">
      <h2 className="text-lg font-semibold">
        {title} <span className="text-muted font-normal">({rows.length.toLocaleString(locale)})</span>
      </h2>
      {rows.length === 0 ? (
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
                        {r.feederName}
                      </Link>
                    ) : (
                      <>
                        {r.feederName}
                        {r.matchState && (
                          <span className="block text-xs text-muted">{t.matchState[r.matchState]}</span>
                        )}
                      </>
                    )}
                  </td>
                  <td>{r.area}</td>
                  <td className="tabular-nums whitespace-nowrap">
                    <span dir="ltr">{r.windowLocal.replace("-", "–")}</span>
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
