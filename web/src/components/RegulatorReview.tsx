// "What the regulator found": NEPRA's order on K-Electric, feeders by average daily outage band
// for each loss category, against K-Electric's own schedule. NEPRA's figures from K-Electric data,
// as printed; never Roshni's measurement. Each category is one stacked bar (widths = NEPRA's
// printed shares) with the bands listed as text under it; every number comes from equity.json.
import type { Locale } from "@/i18n/config";
import type { Dictionary } from "@/i18n/dictionaries";
import { fill, fromExport } from "@/i18n/dictionaries";
import { columnFormat, num } from "@/lib/format";
import type { RegulatorReview as Review } from "@/types/v1";
import { ExportText } from "@/components/ExportText";

// Within schedule: muted. Above it: dusk to night, the same steps as the national table.
const ABOVE = ["#f29a3a", "#b03a3a", "#6b2d5c", "#14213d"];
const ABOVE_TEXT = ["#14213d", "#f4f1ea", "#f4f1ea", "#f4f1ea"];

export function RegulatorReview({
  review,
  locale,
  t,
}: {
  review: Review;
  locale: Locale;
  t: Dictionary["equity"]["review"];
}) {
  const n = (v: number) => num(v, locale);
  const names = t.categories as Record<string, string>;
  return (
    <section aria-labelledby="review" className="rule pt-4 space-y-5">
      <p className="kicker">{t.kicker}</p>
      <h2 id="review" className="headline text-3xl sm:text-4xl max-w-3xl">
        {t.title}
      </h2>
      <p className="max-w-prose border-s-4 border-wire ps-3 text-sm">
        <ExportText value={fromExport(review.basis, locale)} />
      </p>
      <div className="space-y-8">
        {review.categories.map((c) => {
          const pct = columnFormat(c.bands.map((b) => b.pct_feeders), locale, "%");
          let step = 0;
          const styled = c.bands.map((b) => {
            if (!b.above_schedule) return { b, bg: "var(--line)", fg: "var(--ink)" };
            const i = Math.min(step++, ABOVE.length - 1);
            return { b, bg: ABOVE[i], fg: ABOVE_TEXT[i] };
          });
          return (
            <article key={c.category} className="space-y-2">
              <h3 className="headline text-2xl">
                <span className="text-4xl sm:text-5xl me-2 tabular-nums">
                  {n(c.pct_feeders_above_schedule)}%
                </span>
                {fill(
                  t.line,
                  { n: n(c.feeders), category: names[c.category] ?? c.category, hours: n(c.scheduled_hours_per_day) },
                  locale,
                )}
              </h3>
              <p className="text-sm text-muted">
                {fill(t.meta, { consumers: n(c.consumers), atc: n(c.avg_atc_loss_pct) }, locale)}
              </p>
              <div className="flex h-9 w-full overflow-hidden border border-ink" dir="ltr" aria-hidden="true">
                {styled.map(({ b, bg, fg }) => (
                  <span
                    key={b.band}
                    className="flex items-center justify-center font-mono text-xs overflow-hidden whitespace-nowrap"
                    style={{ width: `${b.pct_feeders}%`, background: bg, color: fg }}
                  >
                    {b.pct_feeders >= 9 ? b.band : ""}
                  </span>
                ))}
              </div>
              <ul className="grid gap-x-6 gap-y-1 text-sm sm:grid-cols-2 lg:grid-cols-4">
                {styled.map(({ b, bg }) => (
                  <li key={b.band} className="flex items-baseline gap-2">
                    <span aria-hidden="true" className="inline-block h-3 w-3 shrink-0 border border-ink" style={{ background: bg }} />
                    <span>
                      <span dir="ltr" className="font-mono">
                        {b.band}
                      </span>{" "}
                      {fill(t.band, { feeders: n(b.feeders), pct: pct(b.pct_feeders) }, locale)}
                      {b.above_schedule && <span className="kicker ms-1 text-signal">{t.above}</span>}
                    </span>
                  </li>
                ))}
              </ul>
            </article>
          );
        })}
      </div>
      <p className="text-sm">
        {fill(t.source, { date: review.order_date }, locale)}{" "}
        <a href={review.source_url} className="link" rel="noopener noreferrer" target="_blank">
          {t.read}
        </a>
      </p>
    </section>
  );
}
