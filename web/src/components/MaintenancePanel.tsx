// IESCO's announced maintenance (monthly schedule files, since export 1.6.0): window hours per
// listing row (circle, grid stations, construction) and month; a bar under each value shows its
// size and the page's own circle is highlighted. Announcements, not load shedding and not
// measurements. An HTML table, so every value is text.
import type { Dictionary } from "@/i18n/dictionaries";
import { fill } from "@/i18n/fill";
import { num } from "@/lib/format";
import { monthLabel } from "@/lib/time";
import type { National } from "@/types/v1";
import { ScrollRegion } from "@/components/ScrollRegion";

const ORDER = ["islamabad", "rawalpindi_city", "rawalpindi_cantt", "attock", "jhelum", "chakwal", "gso", "construction"];

export function MaintenancePanel({
  data,
  focus,
  locale,
  t,
  headingLevel = 2,
}: {
  data: National;
  focus?: string;
  locale: string;
  t: Dictionary["maintenance"];
  headingLevel?: 2 | 3;
}) {
  const rows = data.monthly_maintenance ?? [];
  if (rows.length === 0) return null;
  const months = [...new Set(rows.map((r) => r.month))].sort();
  const items = [...new Set(rows.map((r) => r.item))].sort((a, b) => ORDER.indexOf(a) - ORDER.indexOf(b));
  const at = new Map(rows.map((r) => [`${r.item}|${r.month}`, r]));
  const max = Math.max(...rows.map((r) => r.window_hours), 1);
  const names = t.items as Record<string, string>;
  const n = (v: number) => num(v, locale);
  const own = focus ? rows.filter((r) => r.item === focus) : rows;
  // One circle: its file's own figures. All rows: GSO repeats of circle windows left out.
  const total = {
    windows: own.reduce((a, r) => a + (focus ? r.windows : r.unique_windows), 0),
    hours: own.reduce((a, r) => a + (focus ? r.window_hours : r.unique_window_hours), 0),
    from: own.map((r) => r.first_date).sort()[0],
    to: own.map((r) => r.last_date).sort().at(-1),
  };
  const H = headingLevel === 2 ? "h2" : "h3";
  const repeats = rows.reduce((a, r) => a + (r.windows - r.unique_windows), 0);

  return (
    <section aria-labelledby="maintenance" className="space-y-3">
      <p className="kicker">{t.kicker}</p>
      <H id="maintenance" className="headline text-3xl">
        {focus ? fill(t.titleFor, { circle: names[focus] ?? focus }, locale) : t.title}
      </H>
      <p className="headline text-xl max-w-3xl">
        {fill(t.lead, { windows: n(total.windows), hours: n(Math.round(total.hours)), from: total.from ?? "–", to: total.to ?? "–" }, locale)}
      </p>
      <p className="text-sm text-muted max-w-prose">{t.note}</p>
      <ScrollRegion label={t.tableLabel}>
        <table className="maint-grid">
          <caption className="sr-only">{t.tableLabel}</caption>
          <thead>
            <tr>
              <th scope="col" className="sticky start-0 bg-bg z-[1] text-start">
                {t.item}
              </th>
              {months.map((m) => (
                <th key={m} scope="col">
                  <time dateTime={m}>{monthLabel(m, locale)}</time>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item} className={item === focus ? "is-focus" : undefined}>
                <th scope="row" className="sticky start-0 bg-bg z-[1] text-start font-normal">
                  {names[item] ?? item}
                </th>
                {months.map((m) => {
                  const r = at.get(`${item}|${m}`);
                  if (!r) return <td key={m} className="is-empty">–</td>;
                  return (
                    <td key={m} title={fill(t.cellTitle, { windows: n(r.windows), feeders: n(r.feeders) }, locale)}>
                      <span className="maint-fill" aria-hidden="true" style={{ width: `${Math.max(4, (r.window_hours / max) * 100)}%` }} />
                      <span className="relative tabular-nums">{fill(t.hours, { h: n(Math.round(r.window_hours)) }, locale)}</span>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </ScrollRegion>
      <p className="text-xs text-muted max-w-prose">
        {t.source}{" "}
        {repeats > 0 && fill(t.repeats, { n: n(repeats) }, locale)}
      </p>
    </section>
  );
}
