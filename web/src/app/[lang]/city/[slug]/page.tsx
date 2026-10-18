import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { DayRings } from "@/components/city/DayRings";
import { MaintenancePanel } from "@/components/MaintenancePanel";
import { NoticesList } from "@/components/NoticesList";
import { ScheduleClock } from "@/components/city/ScheduleClock";
import { YearLines } from "@/components/city/YearLines";
import { builtLocales } from "@/i18n/config";
import { fill } from "@/i18n/dictionaries";
import { CITY_SLUGS, companyOfSlug, medianOf, rankIn } from "@/lib/cities";
import { IESCO_LEVELS, iescoClocks, keClock, pressCircles } from "@/lib/cityData";
import { loadDocument } from "@/lib/data";
import { num } from "@/lib/format";
import { resolveLocale } from "@/lib/locale";
import { monthLabel } from "@/lib/time";

export const dynamicParams = false;

export async function generateStaticParams() {
  const companies = new Set((await loadDocument("national")).data.series.map((s) => s.company));
  const slugs = Object.entries(CITY_SLUGS).filter(([c]) => companies.has(c)).map(([, s]) => s);
  return builtLocales.flatMap((lang) => slugs.map((slug) => ({ lang, slug })));
}

export async function generateMetadata({ params }: PageProps<"/[lang]/city/[slug]">): Promise<Metadata> {
  const { dict } = await resolveLocale(params);
  const company = companyOfSlug((await params).slug);
  const regions = dict.national.regions as Record<string, string>;
  return { title: company ? (regions[company] ?? company) : dict.city.indexTitle };
}

export default async function City({ params }: PageProps<"/[lang]/city/[slug]">) {
  const { locale, dict } = await resolveLocale(params);
  const company = companyOfSlug((await params).slug);
  if (!company) notFound();
  const t = dict.city;
  const regions = dict.national.regions as Record<string, string>;
  const cityName = regions[company] ?? company;
  const national = (await loadDocument("national")).data;
  const series = national.series;
  const years = [...new Set(series.map((s) => s.fiscal_year))].sort();
  const own = series.filter((s) => s.company === company);
  if (own.length === 0) notFound();
  const at = (c: string, y: string) => series.find((s) => s.company === c && s.fiscal_year === y)?.reported_hours_per_day ?? null;
  const values = years.map((y) => at(company, y));
  const latestRow = own.reduce((a, b) => (b.fiscal_year > a.fiscal_year ? b : a));
  const latest = latestRow.fiscal_year;
  const rank = rankIn(series, company, latest);
  const peak = own.reduce((a, b) => (b.reported_hours_per_day > a.reported_hours_per_day ? b : a));
  const median = years.map((y) => medianOf(series.filter((s) => s.fiscal_year === y).map((s) => s.reported_hours_per_day)));
  const others = [...new Set(series.map((s) => s.company))].filter((c) => c !== company).map((c) => years.map((y) => at(c, y)));
  const ranks = years.map((y) => rankIn(series, company, y));
  const n = (v: number) => num(v, locale);
  const fy = dict.national.fyShort;

  const iesco = company === "IESCO";
  const notices = iesco ? (await loadDocument("notices")).data : [];
  const ke = company === "K-Electric";
  const needSchedules = iesco || ke;
  const feeders = needSchedules ? (await loadDocument("feeders")).data : [];
  const profiles = needSchedules ? (await loadDocument("dark_profiles")).data : [];
  const ie = iesco ? iescoClocks(feeders, profiles) : null;
  const k = ke ? keClock(feeders, profiles) : null;
  const levelHours = ie ? IESCO_LEVELS.map((l) => ie.data[`islamabad|${l}`]?.avgHours).filter((v): v is number => v !== undefined) : [];
  const shutdowns = iesco
    ? (national.monthly_shutdowns ?? []).map((m) => ({
        month: m.month,
        hours: m.circles.filter((c) => pressCircles("islamabad")(c.circle)).reduce((a, c) => a + c.window_hours, 0),
        windows: m.circles.filter((c) => pressCircles("islamabad")(c.circle)).reduce((a, c) => a + c.windows, 0),
      }))
    : [];
  const shutMax = Math.max(...shutdowns.map((s) => s.hours), 1);
  const clockStrings = {
    circle: t.circleLabel,
    level: t.levelLabel,
    levelChip: dict.lead.levelChip,
    center: t.clockCenter,
    tip: t.clockTip,
    matrix: iesco ? t.matrixGrid : t.matrixIbc,
    rowHead: iesco ? t.gridCol : t.ibcCol,
    feeders: t.clockFeeders,
    scale: t.matrixScale,
  };

  return (
    <article className="space-y-12">
      <header className="space-y-4">
        <Link prefetch={false} href={`/${locale}/city/`} transitionTypes={["nav-back"]} className="link inline-flex items-center gap-1.5 text-sm">
          <svg aria-hidden="true" viewBox="0 0 16 16" className="h-3.5 w-3.5 fill-none stroke-current rtl:-scale-x-100" strokeWidth={1.6}>
            <path d="M10 3 5 8l5 5" />
          </svg>
          {t.back}
        </Link>
        <p className="kicker">{fill(t.kicker, { company }, locale)}</p>
        <h1 className="headline text-5xl sm:text-7xl">{cityName}</h1>
        <p className="headline text-xl sm:text-2xl max-w-3xl">
          {latestRow.reported_hours_per_day === 0
            ? fill(t.leadZero, { year: latest, company }, locale)
            : fill(t.lead, { year: latest, company, hours: n(latestRow.reported_hours_per_day), rank: rank?.rank ?? "–", of: rank?.of ?? "–" }, locale)}
        </p>
        <dl className="rule grid grid-cols-2 sm:grid-cols-4 gap-x-6">
          {[
            [n(latestRow.reported_hours_per_day), fill(t.statLatest, { year: latest }, locale)],
            [rank ? n(rank.rank) : "–", fill(t.statRank, { of: rank?.of ?? "–", year: latest }, locale)],
            [n(peak.reported_hours_per_day), fill(t.statPeak, { year: peak.fiscal_year }, locale)],
            [n(own.length), t.statYears],
          ].map(([v, label]) => (
            <div key={label} className="flex flex-col-reverse border-b border-line py-3">
              <dt className="text-sm">{label}</dt>
              <dd className="headline text-5xl tabular-nums">{v}</dd>
            </div>
          ))}
        </dl>
        <p className="text-sm text-muted max-w-prose">{t.reportedNote}</p>
      </header>

      {iesco && levelHours.length > 0 && (
        <aside className="border-s-4 border-wire ps-4 max-w-3xl">
          <p className="headline text-xl sm:text-2xl">
            {fill(t.contrast, { year: latest, reported: n(latestRow.reported_hours_per_day), min: n(Math.min(...levelHours)), max: n(Math.max(...levelHours)) }, locale)}
          </p>
          <p className="text-sm text-muted mt-1">{t.contrastNote}</p>
        </aside>
      )}

      <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <section aria-labelledby="years" className="rule pt-4 space-y-3 min-w-0">
          <h2 id="years" className="headline text-3xl">{t.linesTitle}</h2>
          <p className="text-sm max-w-prose">{fill(t.linesNote, { city: cityName }, locale)}</p>
          <YearLines
            years={years}
            city={{ name: cityName, values }}
            median={median}
            others={others}
            ranks={ranks}
            locale={locale}
            t={{ label: fill(t.linesLabel, { city: cityName }, locale), unit: t.unit, median: t.median, others: t.others, rank: t.tipRank, fy }}
          />
          <details className="text-sm">
            <summary className="link w-fit">{t.tableView}</summary>
            <table className="data mt-2 max-w-md">
              <thead>
                <tr>
                  <th scope="col">{t.tableYear}</th>
                  <th scope="col" className="num">{fill(t.tableValue, { city: cityName }, locale)}</th>
                  <th scope="col" className="num">{t.tableMedian}</th>
                  <th scope="col" className="num">{t.tableRank}</th>
                </tr>
              </thead>
              <tbody>
                {years.map((y, i) => (
                  <tr key={y}>
                    <th scope="row" className="font-normal" dir="ltr">{y}</th>
                    <td className="num">{values[i] === null ? "–" : n(values[i]!)}</td>
                    <td className="num">{median[i] === null ? "–" : n(median[i]!)}</td>
                    <td className="num">{ranks[i] ? `${ranks[i]!.rank} / ${ranks[i]!.of}` : "–"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </details>
        </section>
        <section aria-labelledby="rings" className="rule pt-4 space-y-3">
          <h2 id="rings" className="headline text-3xl">{t.ringsTitle}</h2>
          <p className="text-sm">{fill(t.ringsNote, { company }, locale)}</p>
          <DayRings
            rings={own.sort((a, b) => (a.fiscal_year < b.fiscal_year ? -1 : 1)).map((s) => ({ year: s.fiscal_year, hours: s.reported_hours_per_day }))}
            locale={locale}
            t={{ center: t.ringsCenter, fy, hours: t.unit }}
          />
        </section>
      </div>

      {ie && Object.keys(ie.data).length > 0 && (
        <section aria-labelledby="schedule" className="rule pt-4 space-y-3">
          <p className="kicker">{t.scheduleKicker}</p>
          <h2 id="schedule" className="headline text-3xl sm:text-4xl">{t.iescoTitle}</h2>
          <p className="text-sm max-w-prose">{fill(t.iescoNote, { date: ie.effective ?? "–" }, locale)}</p>
          <ScheduleClock circles={ie.circles} levels={[...IESCO_LEVELS]} data={ie.data} initial={{ circle: "islamabad", level: 4 }} locale={locale} t={clockStrings} />
        </section>
      )}

      {k && Object.keys(k.data).length > 0 && (
        <section aria-labelledby="schedule" className="rule pt-4 space-y-3">
          <p className="kicker">{t.scheduleKicker}</p>
          <h2 id="schedule" className="headline text-3xl sm:text-4xl">{t.keTitle}</h2>
          <p className="text-sm max-w-prose">{fill(t.keNote, { date: k.effective ?? "–" }, locale)}</p>
          <ScheduleClock data={k.data} initial={{}} locale={locale} t={clockStrings} />
          <p className="text-sm">
            <Link prefetch={false} href={`/${locale}/karachi-equity/`} className="link">{t.equityLink}</Link>
          </p>
        </section>
      )}

      {iesco && shutdowns.some((s) => s.hours > 0) && (
        <section aria-labelledby="shutdowns" className="rule pt-4 space-y-3">
          <h2 id="shutdowns" className="headline text-3xl">{t.shutTitle}</h2>
          <p className="text-sm text-muted max-w-prose">{t.shutNote}</p>
          <ol className="flex items-end gap-3 h-48 max-w-xl">
            {shutdowns.map((s) => (
              <li key={s.month} className="flex-1 flex flex-col justify-end h-full min-w-0">
                <p className="text-sm tabular-nums">{fill(dict.monthly.hours, { h: n(s.hours) }, locale)}</p>
                <div aria-hidden="true" className="bar-up bg-dark" style={{ height: `${Math.max((s.hours / shutMax) * 100, 2)}%` }} />
                <time dateTime={s.month} className="block text-xs font-semibold pt-1 border-t-2 border-ink whitespace-nowrap">
                  {monthLabel(s.month, locale)}
                </time>
              </li>
            ))}
          </ol>
        </section>
      )}

      {iesco && (
        <div className="rule pt-4">
          <MaintenancePanel data={national} focus="islamabad" locale={locale} t={dict.maintenance} />
        </div>
      )}
      {iesco && <NoticesList notices={notices} circle="Islamabad" t={dict.notices} />}

      {!needSchedules && <p className="rule pt-4 text-muted max-w-prose">{fill(t.noSchedule, { company }, locale)}</p>}
    </article>
  );
}
