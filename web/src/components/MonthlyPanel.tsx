// Month by month, from Roshni's own records: IESCO planned shutdowns announced per month (summed
// window hours; announced maintenance, not load shedding) and K-Electric's published schedule per
// month (only from its effective date; no earlier schedule on file). Months only partly covered
// by the collected releases are hatched and say which dates they cover. HTML, so every value is
// text; the per-circle breakdown is a table under a disclosure.
import type { Dictionary } from "@/i18n/dictionaries";
import { fill } from "@/i18n/dictionaries";
import { num } from "@/lib/format";
import type { National } from "@/types/v1";
import { ScrollRegion } from "@/components/ScrollRegion";

const BAR_MAX_REM = 9;

export function MonthlyPanel({
  data,
  locale,
  t,
}: {
  data: National;
  locale: string;
  t: Dictionary["monthly"];
}) {
  const shut = data.monthly_shutdowns ?? [];
  const keRows = data.monthly_ke ?? [];
  const ke = new Map(keRows.map((k) => [k.month, k]));
  if (shut.length === 0 && ke.size === 0) return null;
  const months = [...new Set([...shut.map((s) => s.month), ...ke.keys()])].sort();
  const byMonth = new Map(shut.map((s) => [s.month, s]));
  const max = Math.max(...shut.map((s) => s.window_hours), 1);
  const asOfMonth = data.as_of?.slice(0, 7);
  const n = (v: number) => num(v, locale);
  const keFirst = keRows[0];
  const circles = [...new Set(shut.flatMap((s) => s.circles.map((c) => c.circle)))].sort();

  return (
    <section aria-labelledby="monthly" className="space-y-4">
      <p className="kicker">{t.kicker}</p>
      <h2 id="monthly" className="headline text-2xl sm:text-3xl">
        {t.title}
      </h2>

      <div className="space-y-2">
        <h3 className="headline text-xl">{t.shutTitle}</h3>
        <p className="text-sm text-muted max-w-prose">{t.shutNote}</p>
        <ScrollRegion label={t.shutTitle}>
        <ol className="grid gap-3 rule pt-3" style={{ gridTemplateColumns: `repeat(${months.length}, minmax(4.5rem, 1fr))` }}>
          {months.map((mo) => {
            const s = byMonth.get(mo);
            const partialStart = s && s.first_date.slice(8) !== "01" && mo === shut[0]?.month;
            const soFar = mo === asOfMonth;
            return (
              <li key={mo} className="flex flex-col justify-end min-w-0">
                {s ? (
                  <>
                    <p className="headline text-lg tabular-nums leading-tight">
                      {fill(t.hours, { h: n(s.window_hours) }, locale)}
                    </p>
                    <p className="text-xs text-muted">{fill(t.windows, { w: n(s.windows), r: n(s.releases) }, locale)}</p>
                    <div
                      aria-hidden="true"
                      className={`mt-1 border border-ink ${partialStart || soFar ? "month-partial" : "bg-dark"}`}
                      style={{ height: `${Math.max((s.window_hours / max) * BAR_MAX_REM, 0.3)}rem` }}
                    />
                  </>
                ) : (
                  <p className="text-xs text-muted">{t.none}</p>
                )}
                <p className="font-mono text-xs pt-1 border-t-2 border-ink" dir="ltr">
                  {mo}
                </p>
                {s && partialStart && (
                  <p className="text-xs text-muted">{fill(t.from, { date: s.first_date }, locale)}</p>
                )}
                {s && soFar && <p className="text-xs text-muted">{fill(t.soFar, { date: s.last_date }, locale)}</p>}
              </li>
            );
          })}
        </ol>
        </ScrollRegion>
        <details className="text-sm">
          <summary className="link w-fit">{t.byCircle}</summary>
          <ScrollRegion label={t.byCircle}>
            <table className="data mt-2">
              <thead>
                <tr>
                  <th scope="col">{t.circle}</th>
                  {shut.map((s) => (
                    <th key={s.month} scope="col" className="num">
                      <span dir="ltr">{s.month}</span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {circles.map((c) => (
                  <tr key={c}>
                    <th scope="row" className="font-normal">
                      <bdi>{c}</bdi>
                    </th>
                    {shut.map((s) => {
                      const cm = s.circles.find((x) => x.circle === c);
                      return (
                        <td key={s.month} className="num">
                          {cm ? fill(t.cell, { h: n(cm.window_hours), w: n(cm.windows) }, locale) : "–"}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </ScrollRegion>
        </details>
      </div>

      {keFirst && (
        <div className="space-y-2">
          <h3 className="headline text-xl">{t.keTitle}</h3>
          <ScrollRegion label={t.keTitle}>
          <ol className="grid gap-3" style={{ gridTemplateColumns: `repeat(${months.length}, minmax(4.5rem, 1fr))` }}>
            {months.map((mo) => {
              const k = ke.get(mo);
              return (
                <li key={mo} className="min-w-0">
                  {k ? (
                    <>
                      <p className="font-mono text-sm">
                        <span className="mark">{fill(t.keHours, { h: n(k.avg_scheduled_hours) }, locale)}</span>
                      </p>
                      {k.changed_in_month && (
                        <p className="kicker text-signal">{fill(t.keChanged, { date: k.effective_from }, locale)}</p>
                      )}
                    </>
                  ) : (
                    <p className="text-xs text-muted">{t.keNone}</p>
                  )}
                  <p className="font-mono text-xs text-muted" dir="ltr">
                    {mo}
                  </p>
                </li>
              );
            })}
          </ol>
          </ScrollRegion>
          <p className="text-sm text-muted max-w-prose">
            {fill(t.keNote, { n: n(keFirst.feeders), date: keFirst.effective_from }, locale)}
          </p>
        </div>
      )}
    </section>
  );
}
