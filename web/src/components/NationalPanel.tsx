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
import { ScrollRegion } from "@/components/ScrollRegion";

// Stepped colours, day to night: each passes WCAG AA with its text colour (5.3:1 or better).
// [upper bound in hours (exclusive), background, text]
const BINS: [number, string, string][] = [
  [1, "#f5c518", "#14213d"],
  [3, "#f29a3a", "#14213d"],
  [6, "#b03a3a", "#f4f1ea"],
  [9, "#6b2d5c", "#f4f1ea"],
  [Infinity, "#14213d", "#f4f1ea"],
];
const BIN_LABELS = ["< 1", "1–3", "3–6", "6–9", "9+"];

function cellStyle(hours: number) {
  const [, background, color] = BINS.find(([max]) => hours < max)!;
  return { background, color };
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
  const top = latestRows.reduce((a, b) => (b.reported_hours_per_day > a.reported_hours_per_day ? b : a));
  const flagged = data.series.filter((s) => s.values_disagree);
  const region = t.regions as Record<string, string>;
  const n = (v: number) => num(v, locale);

  return (
    <section aria-labelledby="national" className="space-y-4">
      <p className="kicker">{t.kicker}</p>
      <h2 id="national" className="headline text-3xl sm:text-5xl max-w-4xl">
        {t.title}
      </h2>
      <p className="headline text-xl sm:text-2xl max-w-3xl">
        {fill(t.lead, { year: latest, min: n(Math.min(...hours)), max: n(Math.max(...hours)) }, locale)}{" "}
        {fill(t.top, { company: top.company, region: region[top.company] ?? "", hours: n(top.reported_hours_per_day) }, locale)}
      </p>

      <figure className="m-0 space-y-2">
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
                    {y}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {companies.map((c) => (
                <tr key={c}>
                  <th scope="row" className="sticky start-0 bg-bg z-[1]">
                    <span className="block font-semibold">{c}</span>
                    <span className="block text-xs text-muted font-normal">{region[c]}</span>
                  </th>
                  {years.map((y) => {
                    const s = cell.get(`${c}|${y}`);
                    if (!s) return <td key={y} className="is-empty">–</td>;
                    return (
                      <td
                        key={y}
                        style={cellStyle(s.reported_hours_per_day)}
                        className={y === latest ? "is-latest" : undefined}
                        title={
                          s.values_disagree
                            ? fill(t.disagree, { min: n(s.min_reported), max: n(s.max_reported) }, locale)
                            : undefined
                        }
                      >
                        {n(s.reported_hours_per_day)}
                        {s.values_disagree && <sup aria-hidden="true">*</sup>}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollRegion>
        <figcaption className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
          <span className="inline-flex flex-wrap items-center gap-x-2 gap-y-1">
            <span>{t.legend}</span>
            <span className="inline-flex" dir="ltr">
              {BINS.map(([max, background, color], i) => (
                <span key={max} className="national-swatch" style={{ background, color }}>
                  {BIN_LABELS[i]}
                </span>
              ))}
            </span>
          </span>
          {flagged.map((s) => (
            <span key={`${s.company}${s.fiscal_year}`}>
              *{" "}
              {fill(
                t.flag,
                { company: s.company, year: s.fiscal_year, min: n(s.min_reported), max: n(s.max_reported), used: s.chosen_report_year },
                locale,
              )}
            </span>
          ))}
        </figcaption>
      </figure>

      <div className="grid gap-4 sm:grid-cols-2 text-sm max-w-5xl">
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
