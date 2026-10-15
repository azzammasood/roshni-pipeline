import type { Metadata } from "next";
import Link from "next/link";
import { fill } from "@/i18n/dictionaries";
import { cityHref } from "@/lib/cities";
import { cellStyle } from "@/lib/nepraBins";
import { loadDocument } from "@/lib/data";
import { num } from "@/lib/format";
import { resolveLocale } from "@/lib/locale";

export async function generateMetadata({ params }: PageProps<"/[lang]/city">): Promise<Metadata> {
  return { title: (await resolveLocale(params)).dict.city.indexTitle };
}

export default async function Cities({ params }: PageProps<"/[lang]/city">) {
  const { locale, dict } = await resolveLocale(params);
  const t = dict.city;
  const regions = dict.national.regions as Record<string, string>;
  const series = (await loadDocument("national")).data.series;
  const years = [...new Set(series.map((s) => s.fiscal_year))].sort();
  const max = Math.max(...series.map((s) => s.reported_hours_per_day), 1);
  const cards = [...new Set(series.map((s) => s.company))]
    .map((company) => {
      const own = years.map((y) => series.find((s) => s.company === company && s.fiscal_year === y) ?? null);
      const last = [...own].reverse().find(Boolean)!;
      return { company, own, last };
    })
    .sort((a, b) => b.last.reported_hours_per_day - a.last.reported_hours_per_day || (a.company < b.company ? -1 : 1));
  const W = 200;
  const H = 48;
  const x = (i: number) => 3 + (i * (W - 6)) / Math.max(years.length - 1, 1);
  const y = (v: number) => H - 3 - (v / max) * (H - 8);

  return (
    <article className="space-y-8">
      <header className="space-y-3 max-w-4xl">
        <p className="kicker">{t.indexKicker}</p>
        <h1 className="headline text-4xl sm:text-6xl">{t.indexTitle}</h1>
        <p className="text-lg max-w-prose">{t.indexIntro}</p>
      </header>
      <ul className="rule pt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {cards.map(({ company, own, last }, i) => {
          const d = own
            .map((s, k) => (s ? `${x(k)} ${y(s.reported_hours_per_day)}` : null))
            .reduce<string>((acc, p, k, arr) => (p === null ? acc : `${acc}${k === 0 || arr[k - 1] === null ? "M" : "L"}${p}`), "");
          const swatch = cellStyle(last.reported_hours_per_day);
          return (
            <li key={company} className="city-card" style={{ "--i": i } as React.CSSProperties}>
              <Link prefetch={false} href={cityHref(locale, company)!} transitionTypes={["nav-forward"]} className="block p-4 h-full">
                <span className="flex items-start justify-between gap-3">
                  <span>
                    <span className="block headline text-3xl">{regions[company] ?? company}</span>
                    <span className="kicker">{company}</span>
                  </span>
                  <span className="national-swatch shrink-0" style={swatch}>
                    {num(last.reported_hours_per_day, locale)}
                  </span>
                </span>
                <svg viewBox={`0 0 ${W} ${H}`} className="mt-3 w-full h-12 overflow-visible" aria-hidden="true">
                  <line x1={0} x2={W} y1={H - 3} y2={H - 3} className="stroke-line" strokeWidth={1} />
                  <path d={d} fill="none" className="stroke-accent" strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
                </svg>
                <span className="mt-1 block text-sm text-muted">
                  {fill(t.cardLatest, { hours: num(last.reported_hours_per_day, locale), year: last.fiscal_year }, locale)}
                </span>
              </Link>
            </li>
          );
        })}
      </ul>
      <p className="text-sm text-muted max-w-prose">{t.reportedNote}</p>
    </article>
  );
}
