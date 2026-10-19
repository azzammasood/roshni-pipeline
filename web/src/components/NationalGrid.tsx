"use client";
// The NEPRA company x fiscal-year grid. Every filled cell is a button: it opens a small popup
// (grows out of the cell) with the reported value, the company's rank that year, the change from
// the year before, a sparkline of every year on record and a link to the city page. Reported
// figures, not measurements; the popup says so.
import Link from "next/link";
import { useCallback, useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import type { Dictionary } from "@/i18n/dictionaries";
import { fill } from "@/i18n/fill";
import { num } from "@/lib/format";
import { cityHref, rankIn } from "@/lib/cities";
import { cellStyle } from "@/lib/nepraBins";
import type { National } from "@/types/v1";
import { ScrollRegion } from "@/components/ScrollRegion";

type Series = National["series"];
type Cell = Series[number];

type Open = { cell: Cell; x: number; y: number; above: boolean };

export function NationalGrid({
  series,
  years,
  companies,
  latest,
  locale,
  t,
  plans = {},
}: {
  series: Series;
  years: string[];
  companies: string[];
  latest: string;
  locale: string;
  t: Dictionary["national"];
  /** Hours a day the company's own published schedule plans per feeder, as text ("2–12"). */
  plans?: Record<string, string>;
}) {
  const [open, setOpen] = useState<Open | null>(null);
  const wrap = useRef<HTMLDivElement>(null);
  const pop = useRef<HTMLDivElement>(null);
  const opener = useRef<HTMLButtonElement | null>(null);
  const popId = useId();
  const cell = new Map(series.map((s) => [`${s.company}|${s.fiscal_year}`, s]));
  const region = t.regions as Record<string, string>;
  const n = (v: number) => num(v, locale);

  const close = useCallback((refocus = true) => {
    setOpen(null);
    if (refocus) opener.current?.focus();
  }, []);

  const show = (c: Cell, button: HTMLButtonElement) => {
    if (open && open.cell === c) return close();
    const box = wrap.current!.getBoundingClientRect();
    const r = button.getBoundingClientRect();
    opener.current = button;
    const above = r.bottom - box.top > box.height * 0.6; // lower rows open upwards
    setOpen({
      cell: c,
      x: r.left + r.width / 2 - box.left,
      y: above ? r.top - box.top : r.bottom - box.top,
      above,
    });
  };

  // Keep the popup inside the figure; grow it from the cell it belongs to.
  useLayoutEffect(() => {
    const el = pop.current;
    if (!open || !el || !wrap.current) return;
    const width = el.offsetWidth;
    const max = wrap.current.clientWidth;
    const left = Math.min(Math.max(open.x - width / 2, 0), Math.max(max - width, 0));
    el.style.left = `${left}px`;
    el.style.top = open.above ? `${open.y - el.offsetHeight - 8}px` : `${open.y + 8}px`;
    // Grow from the cell, but never from outside the popup (an off-screen cell would widen the page).
    const origin = Math.min(Math.max(open.x - left, 0), width);
    el.style.transformOrigin = `${origin}px ${open.above ? "100%" : "0"}`;
    el.focus();
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const away = (e: PointerEvent) => {
      const target = e.target as Node;
      if (!pop.current?.contains(target) && !opener.current?.contains(target)) close(false);
    };
    const key = (e: KeyboardEvent) => e.key === "Escape" && close();
    const scrolled = () => close(false); // the grid scrolled sideways under the popup
    const region = wrap.current?.querySelector("[role=region]");
    document.addEventListener("pointerdown", away);
    document.addEventListener("keydown", key);
    region?.addEventListener("scroll", scrolled);
    return () => {
      region?.removeEventListener("scroll", scrolled);
      document.removeEventListener("pointerdown", away);
      document.removeEventListener("keydown", key);
    };
  }, [open, close]);

  return (
    <div ref={wrap} className="relative">
      <ScrollRegion label={t.tableLabel} dir="ltr">
        <table className="national-grid">
          <caption className="sr-only">{t.tableLabel}</caption>
          <thead>
            <tr>
              <th scope="col" className="sticky start-0 bg-bg z-[1]">
                {t.company}
              </th>
              {years.map((y) => (
                <th key={y} scope="col" className={y === latest ? "is-latest" : undefined}>
                  <span className="block font-normal text-[0.6rem] leading-tight">{t.fyShort}</span>
                  {y}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {companies.map((c) => {
              const href = cityHref(locale, c);
              return (
                <tr key={c}>
                  <th scope="row" className="sticky start-0 bg-bg z-[1]">
                    {href ? (
                      <Link prefetch={false} href={href} transitionTypes={["nav-forward"]} className="grid-city">
                        <span className="block font-semibold">{c}</span>
                        <span className="block text-xs text-muted font-normal">{region[c]}</span>
                        {plans[c] && <PlanBadge text={fill(t.planBadge, { hours: plans[c] }, locale)} />}
                      </Link>
                    ) : (
                      <>
                        <span className="block font-semibold">{c}</span>
                        <span className="block text-xs text-muted font-normal">{region[c]}</span>
                      </>
                    )}
                  </th>
                  {years.map((y) => {
                    const s = cell.get(`${c}|${y}`);
                    if (!s) return <td key={y} className="is-empty">–</td>;
                    const nil = s.reported_hours_per_day === 0;
                    const label = fill(nil ? t.cellTitleNil : t.cellTitle, { company: c, year: y, hours: n(s.reported_hours_per_day) }, locale);
                    const isOpen = open?.cell === s;
                    return (
                      <td
                        key={y}
                        style={nil ? undefined : cellStyle(s.reported_hours_per_day)}
                        className={`${y === latest ? "is-latest" : ""} ${isOpen ? "is-open" : ""} ${nil ? "is-nil" : ""}`.trim() || undefined}
                      >
                        <button
                          type="button"
                          className="grid-cell"
                          aria-label={label}
                          aria-expanded={isOpen}
                          aria-controls={isOpen ? popId : undefined}
                          onClick={(e) => show(s, e.currentTarget)}
                        >
                          {nil ? (
                            <span className="nil-label">{t.nilCell}</span>
                          ) : (
                            <span>
                              {n(s.reported_hours_per_day)}
                              {s.values_disagree && <sup aria-hidden="true">*</sup>}
                            </span>
                          )}
                        </button>
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </ScrollRegion>
      {open && (
        <CellPopup
          ref={pop}
          id={popId}
          cell={open.cell}
          series={series}
          years={years}
          locale={locale}
          t={t}
          plan={plans[open.cell.company]}
          onClose={() => close()}
        />
      )}
    </div>
  );
}

function CellPopup({
  ref,
  id,
  cell,
  series,
  years,
  locale,
  t,
  plan,
  onClose,
}: {
  ref: React.Ref<HTMLDivElement>;
  id: string;
  cell: Cell;
  series: Series;
  years: string[];
  locale: string;
  t: Dictionary["national"];
  plan?: string;
  onClose: () => void;
}) {
  const region = t.regions as Record<string, string>;
  const n = (v: number) => num(v, locale);
  const own = years
    .map((y) => series.find((s) => s.company === cell.company && s.fiscal_year === y))
    .filter((s): s is Cell => Boolean(s));
  const at = own.indexOf(cell);
  const prev = at > 0 ? own[at - 1] : null;
  const rank = rankIn(series, cell.company, cell.fiscal_year);
  const delta = prev ? Math.round((cell.reported_hours_per_day - prev.reported_hours_per_day) * 1000) / 1000 : null;
  const href = cityHref(locale, cell.company);
  const titleId = `${id}-title`;

  // Sparkline: every year on record, this year marked.
  const W = 220;
  const H = 44;
  const max = Math.max(...own.map((s) => s.reported_hours_per_day), 1);
  const x = (i: number) => (own.length === 1 ? W / 2 : 4 + (i * (W - 8)) / (own.length - 1));
  const y = (v: number) => H - 4 - (v / max) * (H - 10);
  const path = own.map((s, i) => `${i ? "L" : "M"}${x(i)} ${y(s.reported_hours_per_day)}`).join("");

  return (
    <div
      ref={ref}
      id={id}
      role="dialog"
      aria-labelledby={titleId}
      tabIndex={-1}
      className="grid-pop absolute z-30 w-[17rem] max-w-full border-[1.5px] border-ink bg-surface p-3 text-sm shadow-[0_18px_40px_-18px_rgb(0_0_0/0.55)] focus:outline-none"
    >
      <div className="flex items-start justify-between gap-2">
        <p id={titleId} className="kicker">
          {cell.company} · {region[cell.company]} · {t.fyShort} {cell.fiscal_year}
        </p>
        <button type="button" onClick={onClose} aria-label={t.popClose} className="-mt-1 -me-1 px-1.5 text-lg leading-none text-muted hover:text-ink">
          ×
        </button>
      </div>
      <p className="mt-1">
        <span className="headline text-4xl tabular-nums">{n(cell.reported_hours_per_day)}</span>{" "}
        <span>{t.popUnit}</span>
      </p>
      <p className="text-xs text-muted">{t.popBasis}</p>
      <ul className="mt-2 space-y-0.5">
        {rank && <li>{fill(t.popRank, { rank: rank.rank, of: rank.of }, locale)}</li>}
        {prev && delta !== null && (
          <li>
            {delta === 0
              ? fill(t.popSame, { prev: prev.fiscal_year }, locale)
              : fill(delta > 0 ? t.popUp : t.popDown, { delta: n(Math.abs(delta)), prev: prev.fiscal_year }, locale)}
          </li>
        )}
        {cell.reported_hours_per_day === 0 && <li>{t.popZero}</li>}
        {plan && <li>{fill(t.popPlan, { hours: plan }, locale)}</li>}
        {cell.values_disagree && (
          <li className="text-muted">
            * {fill(t.disagree, { min: n(cell.min_reported), max: n(cell.max_reported) }, locale)}
          </li>
        )}
      </ul>
      {own.length > 1 && (
        <figure className="m-0 mt-2">
          <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-11 overflow-visible" aria-hidden="true">
            <line x1={0} x2={W} y1={H - 4} y2={H - 4} className="stroke-line" strokeWidth={1} />
            <path d={path} fill="none" className="stroke-accent" strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
            <circle cx={x(at)} cy={y(cell.reported_hours_per_day)} r={4} className="fill-accent stroke-surface" strokeWidth={2} />
          </svg>
          <figcaption className="flex justify-between text-[0.65rem] text-muted font-mono" dir="ltr">
            <span>{own[0].fiscal_year}</span>
            <span>{own.at(-1)!.fiscal_year}</span>
          </figcaption>
        </figure>
      )}
      {href && (
        <Link prefetch={false} href={href} transitionTypes={["nav-forward"]} className="link mt-2 inline-block">
          {fill(t.popOpen, { city: region[cell.company] ?? cell.company }, locale)}
        </Link>
      )}
    </div>
  );
}

function PlanBadge({ text }: { text: string }) {
  return <span className="plan-badge">{text}</span>;
}
