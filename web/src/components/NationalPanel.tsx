// Home page national picture: average daily load-shedding hours that each distribution company
// REPORTED TO NEPRA, per fiscal year, as a company x year grid. Cells shade from lamp yellow
// (little reported shedding) through dusk to night blue (more), in five steps. An HTML table, so every value is text.
// Never call these measurements: the basis and NEPRA's own caveat are always shown.
import type { Dictionary } from "@/i18n/dictionaries";
import { fill, fromExport } from "@/i18n/dictionaries";
import type { Locale } from "@/i18n/config";
import { ExportText } from "@/components/ExportText";
import { num } from "@/lib/format";
import type { National } from "@/types/v1";
import { NationalGrid } from "@/components/NationalGrid";
import { BINS, BIN_LABELS } from "@/lib/nepraBins";
import { joinList } from "@/lib/cities";


/** "2024-25" -> "2025-26". */
export function nextFiscalYear(fy: string): string {
  const start = Number(fy.slice(0, 4)) + 1;
  return `${start}-${String((start + 1) % 100).padStart(2, "0")}`;
}

export function NationalPanel({
  data,
  locale,
  t,
}: {
  data: National;
  locale: Locale;
  t: Dictionary["national"];
}) {
  if (data.series.length === 0) return null; // no NEPRA rows in this build: show nothing, never guess
  const years = [...new Set(data.series.map((s) => s.fiscal_year))].sort();
  const latest = years.at(-1)!;
  const cell = new Map(data.series.map((s) => [`${s.company}|${s.fiscal_year}`, s]));
  const latestRows = data.series.filter((s) => s.fiscal_year === latest);
  const companies = [...new Set(data.series.map((s) => s.company))].sort(
    (a, b) =>
      (cell.get(`${b}|${latest}`)?.reported_hours_per_day ?? -1) -
        (cell.get(`${a}|${latest}`)?.reported_hours_per_day ?? -1) || (a < b ? -1 : 1),
  );
  const hours = latestRows.map((s) => s.reported_hours_per_day);
  // A 0 is not a range end: name the companies that reported none (owner, 2026-10-15).
  const zeros = latestRows.filter((s) => s.reported_hours_per_day === 0).map((s) => s.company).sort();
  const nonZero = hours.filter((h) => h > 0);
  const top = latestRows.reduce((a, b) => (b.reported_hours_per_day > a.reported_hours_per_day ? b : a));
  const flagged = data.series.filter((s) => s.values_disagree);
  const hasZero = data.series.some((s) => s.reported_hours_per_day === 0);
  const region = t.regions as Record<string, string>;
  const n = (v: number) => num(v, locale);

  return (
    <section aria-labelledby="national" className="space-y-4">
      <p className="kicker">{t.kicker}</p>
      <h2 id="national" className="headline text-3xl sm:text-5xl max-w-4xl">
        {t.title}
      </h2>
      <p className="headline text-xl sm:text-2xl max-w-3xl">
        {zeros.length > 0 && nonZero.length > 0
          ? fill(
              t.leadZero,
              {
                year: latest,
                zeros: joinList(zeros, t.and, t.listComma),
                min: n(Math.min(...nonZero)),
                max: n(Math.max(...nonZero)),
              },
              locale,
            )
          : fill(t.lead, { year: latest, min: n(Math.min(...hours)), max: n(Math.max(...hours)) }, locale)}{" "}
        {fill(t.top, { company: top.company, region: region[top.company] ?? "", hours: n(top.reported_hours_per_day) }, locale)}
      </p>

      <figure className="m-0 space-y-4 pt-2">
        <NationalGrid
          series={data.series}
          years={years}
          companies={companies}
          latest={latest}
          locale={locale}
          t={t}
        />
        <figcaption className="space-y-3 text-sm">
          <p className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <span>{t.legend}</span>
            <span className="inline-flex" dir="ltr">
              {BINS.map(([max, background, color], i) => (
                <span key={max} className="national-swatch" style={{ background, color }}>
                  {BIN_LABELS[i]}
                </span>
              ))}
            </span>
            <span className="text-muted hidden sm:inline">· {t.hoverHint}</span>
          </p>
          {/* Fiscal years run July to June. The newest column is the newest year in NEPRA's
              reports on file; the next year appears when NEPRA publishes it (checked daily). */}
          <p className="max-w-prose">
            {fill(
              t.latestNote,
              { year: latest, from: latest.slice(0, 4), to: `20${latest.slice(5)}`, next: nextFiscalYear(latest) },
              locale,
            )}{" "}
            <a href="#monthly" className="link">
              {fill(t.monthlyLink, { year: (data.as_of ?? "").slice(0, 4) }, locale)}
            </a>
          </p>
          {hasZero && <p className="max-w-prose">{t.zeroNote}</p>}
          {flagged.length > 0 && (
            <ul className="space-y-1 text-muted">
              {flagged.map((s) => (
                <li key={`${s.company}${s.fiscal_year}`}>
                  *{" "}
                  {fill(
                    t.flag,
                    { company: s.company, year: s.fiscal_year, min: n(s.min_reported), max: n(s.max_reported), used: s.chosen_report_year },
                    locale,
                  )}
                </li>
              ))}
            </ul>
          )}
        </figcaption>
      </figure>

      <div className="grid gap-6 sm:grid-cols-2 text-sm max-w-5xl rule-thin !mt-8 pt-6">
        <p className="border-s-4 border-wire ps-3">
          <strong className="kicker text-ink me-1">{t.caveatLabel}</strong>{" "}
          <ExportText value={fromExport(data.caveat, locale)} />
        </p>
        <p className="border-s-4 border-line ps-3">
          <strong className="kicker text-ink me-1">{t.basisLabel}</strong>{" "}
          <ExportText value={fromExport(data.basis, locale)} />
          {data.gaps.map((g) => (
            <span key={g}>
              {" "}
              <ExportText value={fromExport(g, locale)} />
            </span>
          ))}
        </p>
      </div>
      {data.events.length > 0 && (
        <ul className="text-sm space-y-1">
          {data.events.map((e) => (
            <li key={e.id}>
              <span className="kicker me-2">{t.policy}</span>
              <time dateTime={e.date} dir="ltr" className="font-mono me-2">
                {e.date}
              </time>
              {e.max_hours != null ? fill(t.eventMax, { hours: n(e.max_hours) }, locale) : e.summary}{" "}
              <a href={e.source_url} className="link" rel="noopener noreferrer" target="_blank">
                {t.eventSource}
              </a>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
