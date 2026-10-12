"use client";
import Link from "next/link";
import { useMemo, useState } from "react";
import type { Dictionary } from "@/i18n/dictionaries";
import { fill } from "@/i18n/fill";
import { karachiDate } from "@/lib/time";
import { feederHref } from "@/lib/urls";
import { useExport } from "@/lib/useExport";
import type { PlannedShutdown } from "@/types/v1";
import { ScrollRegion } from "@/components/ScrollRegion";

type Strings = Pick<Dictionary, "shutdowns" | "common" | "matchState" | "feeder">;
const PAGE = 50;
const STATES: PlannedShutdown["feeder_match_state"][] = [
  "matched",
  "pending_review",
  "unmatched",
  "out_of_scope",
];

export function ShutdownTable({ locale, t }: { locale: string; t: Strings }) {
  const state = useExport(["feeders", "planned_shutdowns"] as const);
  const [query, setQuery] = useState("");
  const [circle, setCircle] = useState("");
  const [match, setMatch] = useState("");
  const [upcoming, setUpcoming] = useState(false);
  const [page, setPage] = useState(0);

  const all = useMemo(
    () =>
      state.status === "ready"
        ? [...state.data.planned_shutdowns.data].sort(
            (a, b) => (a.start_utc < b.start_utc ? 1 : a.start_utc > b.start_utc ? -1 : 0),
          )
        : [],
    [state],
  );
  const names = useMemo(
    () =>
      state.status === "ready"
        ? new Map(state.data.feeders.data.map((f) => [f.feeder_id, f.name]))
        : new Map<string, string>(),
    [state],
  );
  const circles = useMemo(() => [...new Set(all.map((s) => s.circle_as_printed))].sort(), [all]);

  const q = query.trim().toLowerCase();
  // Only read the clock when the filter is on (after user input, so never during prerender).
  const today = upcoming ? karachiDate(new Date()) : "";
  const rows = all.filter(
    (s) =>
      (!circle || s.circle_as_printed === circle) &&
      (!match || s.feeder_match_state === match) &&
      (!upcoming || s.outage_date >= today) &&
      (!q ||
        `${s.feeder_name_as_printed} ${names.get(s.feeder_id ?? "") ?? ""} ${s.release_no ?? ""}`
          .toLowerCase()
          .includes(q)),
  );
  const pages = Math.max(1, Math.ceil(rows.length / PAGE));
  const current = Math.min(page, pages - 1);
  const shown = rows.slice(current * PAGE, current * PAGE + PAGE);
  const reset = <T,>(set: (v: T) => void) => (v: T) => {
    set(v);
    setPage(0);
  };

  if (state.status === "error") return <p role="alert">{t.common.loadError}</p>;
  if (state.status === "loading") return <p className="text-muted">{t.common.loading}</p>;

  return (
    <div className="space-y-4">
      <form className="grid gap-3 sm:grid-cols-4 items-end" onSubmit={(e) => e.preventDefault()}>
        <label className="grid gap-1 text-sm sm:col-span-2">
          <span className="font-medium">{t.common.search}</span>
          <input
            type="search"
            className="field"
            value={query}
            onChange={(e) => reset(setQuery)(e.target.value)}
          />
        </label>
        <label className="grid gap-1 text-sm">
          <span className="font-medium">{t.shutdowns.circle}</span>
          <select className="field" value={circle} onChange={(e) => reset(setCircle)(e.target.value)}>
            <option value="">{t.shutdowns.allCircles}</option>
            {circles.map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
        </label>
        <label className="grid gap-1 text-sm">
          <span className="font-medium">{t.shutdowns.state}</span>
          <select className="field" value={match} onChange={(e) => reset(setMatch)(e.target.value)}>
            <option value="">{t.shutdowns.allStates}</option>
            {STATES.map((s) => (
              <option key={s} value={s}>
                {t.matchState[s]}
              </option>
            ))}
          </select>
        </label>
        <label className="flex gap-2 items-center text-sm sm:col-span-4">
          <input
            type="checkbox"
            checked={upcoming}
            onChange={(e) => reset(setUpcoming)(e.target.checked)}
          />
          {t.shutdowns.upcoming}
        </label>
      </form>

      <p aria-live="polite">{fill(t.shutdowns.results, { n: rows.length }, locale)}</p>

      {rows.length > 0 && (
        <ScrollRegion label={t.shutdowns.title}>
          <table className="data">
            <thead>
              <tr>
                <th scope="col">{t.common.date}</th>
                <th scope="col">{t.common.window}</th>
                <th scope="col">{t.shutdowns.circle}</th>
                <th scope="col">{t.feeder.asPrinted}</th>
                <th scope="col">{t.shutdowns.state}</th>
                <th scope="col">{t.feeder.release}</th>
              </tr>
            </thead>
            <tbody>
              {shown.map((s) => (
                <tr key={s.shutdown_id}>
                  <td className="tabular-nums whitespace-nowrap">{s.outage_date}</td>
                  <td className="tabular-nums whitespace-nowrap" dir="ltr">
                    {s.start_local}–{s.end_local}
                  </td>
                  <td>
                    <bdi>{s.circle_as_printed}</bdi>
                  </td>
                  <td>
                    <bdi>{s.feeder_name_as_printed}</bdi>
                  </td>
                  <td>
                    {s.feeder_id && s.feeder_match_state === "matched" ? (
                      <Link prefetch={false} href={feederHref(locale, s.feeder_id)} className="link">
                        <bdi>{names.get(s.feeder_id) ?? s.feeder_id}</bdi>
                      </Link>
                    ) : (
                      <span className="text-muted">{t.matchState[s.feeder_match_state]}</span>
                    )}
                    {s.match_confidence !== null && s.match_confidence < 1 && (
                      <span className="block text-xs text-muted">
                        {fill(t.common.confidence, { pct: Math.round(s.match_confidence * 100) }, locale)}
                      </span>
                    )}
                  </td>
                  <td>{s.release_no}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollRegion>
      )}

      {pages > 1 && (
        <nav aria-label={fill(t.common.page, { page: current + 1, pages }, locale)} className="flex gap-4 items-center">
          <button type="button" className="link disabled:opacity-40" disabled={current === 0} onClick={() => setPage(current - 1)}>
            {t.common.previous}
          </button>
          <span className="text-sm text-muted">{fill(t.common.page, { page: current + 1, pages }, locale)}</span>
          <button type="button" className="link disabled:opacity-40" disabled={current >= pages - 1} onClick={() => setPage(current + 1)}>
            {t.common.next}
          </button>
        </nav>
      )}
    </div>
  );
}
