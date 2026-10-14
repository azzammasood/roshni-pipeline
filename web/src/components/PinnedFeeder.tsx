"use client";
// Home page lead story: the visitor's pinned feeder (kept in this browser), its scheduled-dark
// window now or next, and its day as a power line. Without a pin, the lead is a feeder finder.
// IESCO is a scenario playbook: the lead never says which level is in force; the visitor picks one.
import Link from "next/link";
import { useEffect, useId, useMemo, useRef, useState } from "react";
import type { Dictionary } from "@/i18n/dictionaries";
import { fill } from "@/i18n/fill";
import { rich } from "@/i18n/rich";
import { IESCO_LEVELS, windowStatus, type IescoLevel } from "@/lib/darkNow";
import { num } from "@/lib/format";
import { circleName, ibcName } from "@/lib/names";
import { setPin } from "@/lib/pin";
import { feederHref } from "@/lib/urls";
import { hourWindows } from "@/lib/windows";
import type { DarkProfile, Feeder } from "@/types/v1";
import { useClock } from "@/components/Clock";
import { PowerLine } from "@/components/PowerLine";

export type LeadStrings = Pick<Dictionary, "lead" | "common" | "sources">;

const areaOf = (f: Feeder) => (f.ibc ? ibcName(f.ibc) : f.circle ? circleName(f.circle) : f.grid);

export function duration(minutes: number, t: LeadStrings["lead"], locale: string) {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return h ? fill(t.hours, { h, m }, locale) : fill(t.minutes, { m }, locale);
}

export function PinnedFeeder({
  feeders,
  feeder,
  profile,
  minute,
  today,
  level,
  onLevel,
  locale,
  t,
}: {
  feeders: Feeder[];
  feeder: Feeder;
  profile: DarkProfile | undefined;
  minute: number;
  today: string;
  level: IescoLevel | null;
  onLevel: (n: IescoLevel) => void;
  locale: string;
  t: LeadStrings;
}) {
  const clock = useClock();
  const [finding, setFinding] = useState(false);
  const { lead } = t;
  const iesco = feeder.source === "iesco";
  const windows = iesco
    ? level !== null && profile?.scenario_levels?.[String(level)]
      ? hourWindows(profile.scenario_levels[String(level)])
      : null
    : (profile?.daily_windows?.map((w) => ({ start: w.start_min, end: w.end_min })) ?? []);
  const notYet = profile && profile.effective_from > today;
  const status = windows && !notYet ? windowStatus(windows, minute) : null;
  const name = <bdi>{feeder.name}</bdi>;
  const time = (m: number) => (
    <span dir="ltr" className="mark tabular-nums whitespace-nowrap">
      {clock(m % 1440)}
    </span>
  );
  const match =
    feeder.schedule_match_confidence === null || feeder.schedule_match_method === "exact"
      ? t.common.exact
      : fill(t.common.confidence, { pct: Math.round(feeder.schedule_match_confidence * 100) }, locale);

  if (finding) return <FeederFinder feeders={feeders} locale={locale} t={t} onDone={() => setFinding(false)} />;

  return (
    <section aria-labelledby="lead" className="space-y-3">
      <p className="kicker flex flex-wrap gap-x-2">
        <span>{lead.kicker}</span>
        <span aria-hidden="true">·</span>
        <span>{t.sources[feeder.source]}</span>
        {areaOf(feeder) && (
          <>
            <span aria-hidden="true">·</span>
            <bdi>{areaOf(feeder)}</bdi>
          </>
        )}
        {!iesco && (
          <>
            <span aria-hidden="true">·</span>
            <span>{match}</span>
          </>
        )}
      </p>

      {iesco && (
        <div className="space-y-2">
          <p className="text-sm max-w-prose">{lead.chooseLevel}</p>
          <div role="group" aria-label={lead.levelGroup} className="flex flex-wrap gap-1.5">
            {IESCO_LEVELS.map((n) => (
              <button
                key={n}
                type="button"
                aria-pressed={level === n}
                onClick={() => onLevel(n)}
                className={`chip px-2 py-0.5 ${level === n ? "bg-ink text-bg" : "hover:bg-surface"}`}
              >
                {fill(lead.levelChip, { n }, locale)}
              </button>
            ))}
          </div>
        </div>
      )}

      <h1 id="lead" className="headline text-[2.1rem] sm:text-5xl max-w-3xl">
        {iesco && level !== null && !notYet && (
          <span className="block kicker text-signal mb-2">{fill(lead.ifLevel, { n: level }, locale)}</span>
        )}
        {notYet
          ? rich(lead.notYet, { name, date: <span dir="ltr">{profile!.effective_from}</span> })
          : iesco && level === null
            ? rich(lead.pickLevel, { name })
            : !status
              ? rich(lead.none, { name })
              : status.active
                ? rich(lead.darkNow, { name, end: time(status.end) })
                : rich(lead.next, { name, start: time(status.start) })}
      </h1>
      {status && (
        <p className="text-lg text-muted">
          {status.active
            ? fill(lead.darkLeft, { left: duration(status.minutesUntil, lead, locale) }, locale)
            : rich(lead.nextLeft, {
                left: duration(status.minutesUntil, lead, locale),
                end: <span dir="ltr">{clock(status.end % 1440)}</span>,
              })}
        </p>
      )}

      {windows && !notYet && (
        <div className="pt-2">
          <PowerLine windows={windows} now={minute} label={lead.strip} />
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 text-sm">
            <h2 className="kicker">{lead.windows}</h2>
            {windows.length === 0 ? (
              <p>{t.common.none}</p>
            ) : (
              <ul className="flex flex-wrap gap-x-3 gap-y-1">
                {windows.map((w) => (
                  <li key={w.start} dir="ltr" className="tabular-nums whitespace-nowrap">
                    {clock(w.start)}–{clock(w.end % 1440)}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}

      <p className="flex flex-wrap gap-x-5 gap-y-1 text-sm pt-1">
        <Link prefetch={false} href={feederHref(locale, feeder.feeder_id)} className="link">
          {lead.open}
        </Link>
        <button type="button" className="link" onClick={() => setFinding(true)}>
          {lead.change}
        </button>
        <button type="button" className="link" onClick={() => setPin(null)}>
          {lead.unpin}
        </button>
      </p>
    </section>
  );
}

/** Search the feeders passed in (those with a published schedule) and pin one. */
export function FeederFinder({
  locale,
  t,
  feeders,
  onDone,
}: {
  locale: string;
  t: LeadStrings;
  feeders: Feeder[];
  onDone?: () => void;
}) {
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  const listId = useId();
  const { lead } = t;
  const all = feeders;
  useEffect(() => {
    if (!open) return;
    const away = (e: PointerEvent) => !box.current?.contains(e.target as Node) && setOpen(false);
    document.addEventListener("pointerdown", away);
    return () => document.removeEventListener("pointerdown", away);
  }, [open]);
  const term = q.trim().toLowerCase();
  const hits = useMemo(
    () =>
      term.length < 2
        ? []
        : all.filter((f) =>
            [f.name, f.feeder_code ?? "", f.grid ?? "", f.ibc ?? "", f.circle ?? "", circleName(f.circle) ?? ""]
              .join(" ")
              .toLowerCase()
              .includes(term),
          ),
    [all, term],
  );
  const status = term.length < 2 ? "" : hits.length ? fill(lead.results, { n: hits.length }, locale) : lead.noResults;
  return (
    <section aria-labelledby="lead" className="space-y-3">
      <p className="kicker">{lead.kicker}</p>
      <h1 id="lead" className="headline text-[2.1rem] sm:text-5xl">
        {lead.findTitle}
      </h1>
      <p className="max-w-prose">{lead.findIntro}</p>
      {/* Results float over the page (no reflow below); Escape or a click outside closes them. */}
      <div ref={box} className="relative max-w-xl">
        <label className="block">
          <span className="sr-only">{t.common.search}</span>
          <input
            type="search"
            className="field w-full text-lg"
            placeholder={t.common.searchPlaceholder}
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              setOpen(true);
            }}
            onFocus={() => setOpen(true)}
            onKeyDown={(e) => e.key === "Escape" && setOpen(false)}
          />
        </label>
        <p aria-live="polite" className="sr-only">
          {status}
        </p>
        {open && term.length >= 2 && (
          <div
            id={listId}
            className="pop-in absolute inset-x-0 top-full z-20 mt-1 border-[1.5px] border-ink bg-surface shadow-[0_18px_40px_-18px_rgb(0_0_0/0.45)]"
          >
            <p className="kicker px-3 pt-2 pb-1 text-muted" aria-hidden="true">
              {status}
            </p>
            {hits.length > 0 && (
              <ul className="max-h-[22rem] overflow-y-auto">
                {hits.slice(0, 8).map((f, i) => (
                  <li key={f.feeder_id} className="stagger-in border-t border-line" style={{ "--i": i } as React.CSSProperties}>
                    <button
                      type="button"
                      className="w-full text-start px-3 py-2 flex items-baseline gap-3 hover:bg-bg focus-visible:bg-bg"
                      onKeyDown={(e) => e.key === "Escape" && setOpen(false)}
                      onClick={() => {
                        setPin(f.feeder_id);
                        setOpen(false);
                        onDone?.();
                      }}
                    >
                      <span className="flex-1 min-w-0">
                        <bdi className="font-semibold">{f.name}</bdi>
                        <span className="block text-sm text-muted">
                          {t.sources[f.source]}
                          {areaOf(f) && (
                            <>
                              {" · "}
                              <bdi>{areaOf(f)}</bdi>
                            </>
                          )}
                          {f.feeder_code && (
                            <>
                              {" · "}
                              <span className="font-mono">{f.feeder_code}</span>
                            </>
                          )}
                        </span>
                      </span>
                      <span className="chip shrink-0">{lead.pin}</span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
            {hits.length > 8 && (
              <p className="border-t border-line px-3 py-2 text-sm text-muted">
                {fill(lead.more, { n: num(hits.length - 8, locale) }, locale)}
              </p>
            )}
          </div>
        )}
      </div>
      {onDone && (
        <button type="button" className="link text-sm" onClick={onDone}>
          {lead.cancel}
        </button>
      )}
    </section>
  );
}
