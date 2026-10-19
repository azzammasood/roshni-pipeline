import type { Metadata } from "next";
import { loadDocument } from "@/lib/data";
import { resolveLocale } from "@/lib/locale";
import { ScrollRegion } from "@/components/ScrollRegion";
import { ExportText } from "@/components/ExportText";
import { fill, fromExport } from "@/i18n/dictionaries";
import { IESCO_RELEASES } from "@/components/ReleaseLink";

/** NEPRA's list of Performance Evaluation Reports (the `nepra_per_distribution` listing page). */
const NEPRA_REPORTS = "https://nepra.org.pk/publications/Performance%20Reports.php";
/** IESCO's monthly maintenance-schedule listing (owner approval 2026-10-18). */
const IESCO_MAINTENANCE = "https://iesco.com.pk/maintenance-schedule";

export async function generateMetadata({ params }: PageProps<"/[lang]/about">): Promise<Metadata> {
  return { title: (await resolveLocale(params)).dict.about.title };
}

export default async function About({ params }: PageProps<"/[lang]/about">) {
  const { locale, dict } = await resolveLocale(params);
  const t = dict.about;
  const meta = (await loadDocument("meta")).data;
  const shutdowns = (await loadDocument("planned_shutdowns")).data;
  const releases = new Set(shutdowns.map((r) => `${r.release_period}#${r.release_no}`)).size;
  const dates = shutdowns.map((r) => r.outage_date).sort();
  const iesco = meta.sources.find((s) => s.source === "iesco_schedule_xlsx");
  const national = (await loadDocument("national")).data;
  const review = (await loadDocument("equity")).data.regulator_review;
  const editions = national.reports.map((r) => r.report_year).sort();
  const maintenanceWindows = (await loadDocument("maintenance")).data.length;
  const prose: [string, string][] = [
    [t.whatTitle, t.what],
    [t.levelsTitle, t.levels],
    [t.timeTitle, t.time],
    [t.matchingTitle, t.matching],
  ];
  return (
    <article className="space-y-10">
      <header className="space-y-3">
        <p className="kicker">{t.kicker}</p>
        <h1 className="headline text-4xl sm:text-6xl">{t.title}</h1>
      </header>
      <div className="rule pt-4 grid gap-8 lg:grid-cols-[minmax(0,1fr)_17rem]">
        <div className="space-y-6">
          {prose.map(([title, body], i) => (
            <section key={title} className="space-y-1">
              <h2 className="headline text-2xl">{title}</h2>
              <p className={`max-w-prose text-lg leading-relaxed ${i === 0 ? "dropcap" : ""}`}>{body}</p>
            </section>
          ))}
        </div>
        <aside aria-labelledby="glossary" className="lg:border-s lg:border-line lg:ps-6 space-y-3">
          <h2 id="glossary" className="kicker">
            {t.glossaryTitle}
          </h2>
          <dl className="space-y-3">
            {t.glossary.map(([term, text]) => (
              <div key={term} className="border-t border-line pt-2">
                <dt className="headline text-xl">{term}</dt>
                <dd className="text-sm">{text}</dd>
              </div>
            ))}
          </dl>
        </aside>
      </div>
      <section className="rule pt-4 space-y-2">
        <h2 className="headline text-3xl">{t.sourcesTitle}</h2>
        <ScrollRegion label={t.sourcesTitle}>
          <table className="data">
            <thead>
              <tr>
                <th scope="col">{t.sourceName}</th>
                <th scope="col">{t.sourceFile}</th>
                <th scope="col">{dict.common.effectiveFrom}</th>
                <th scope="col">{t.published}</th>
                <th scope="col">{t.basis}</th>
              </tr>
            </thead>
            <tbody>
              {/* One row per source: IESCO publishes one file per circle, all listed together. */}
              {[...Map.groupBy(meta.sources, (s) => s.source)].map(([source, files]) => {
                const once = <T,>(pick: (s: (typeof files)[number]) => T) => [...new Set(files.map(pick))];
                return (
                  <tr key={source}>
                    <th scope="row" className="font-normal">
                      {(t.sourceNames as Record<string, string>)[source] ?? source}
                      {files.length > 1 && (
                        <span className="block text-xs text-muted">{fill(t.filesCount, { n: files.length }, locale)}</span>
                      )}
                    </th>
                    <td className="font-mono text-xs">
                      <ul>
                        {files.map((s) => (
                          <li key={s.source_file} className="break-all">
                            <bdi>{s.source_file}</bdi>
                          </li>
                        ))}
                      </ul>
                    </td>
                    <td className="tabular-nums whitespace-nowrap">
                      {once((s) => s.effective_from).map((v) => (
                        <span key={v} className="block">{v}</span>
                      ))}
                    </td>
                    <td>
                      {once((s) => s.published_label).map((v) => (
                        <bdi key={String(v)} className="block">{v}</bdi>
                      ))}
                    </td>
                    <td>
                      {once((s) => s.effective_basis).map((v) => (
                        <ExportText key={String(v)} as="p" value={fromExport(v, locale)} />
                      ))}
                    </td>
                  </tr>
                );
              })}
              {releases > 0 && (
                <tr>
                  <th scope="row" className="font-normal">
                    {t.sourceNames.iesco_press_release}
                  </th>
                  <td>
                    <a href={IESCO_RELEASES} className="link" rel="noopener noreferrer" target="_blank">
                      {fill(t.pressFile, { n: releases }, locale)}
                    </a>
                  </td>
                  <td className="tabular-nums whitespace-nowrap">
                    {fill(t.pressFrom, { from: dates[0], to: dates.at(-1)! }, locale)}
                  </td>
                  <td />
                  <td>{t.pressBasis}</td>
                </tr>
              )}
              {editions.length > 0 && (
                <tr>
                  <th scope="row" className="font-normal">
                    {t.sourceNames.nepra_per}
                  </th>
                  <td>
                    <a href={NEPRA_REPORTS} className="link" rel="noopener noreferrer" target="_blank">
                      {fill(t.nepraFile, { n: editions.length, from: editions[0], to: editions.at(-1)! }, locale)}
                    </a>
                  </td>
                  <td />
                  <td />
                  <td>{t.nepraBasis}</td>
                </tr>
              )}
              {review && (
                <tr>
                  <th scope="row" className="font-normal">
                    {t.sourceNames.nepra_ke_order}
                  </th>
                  <td>
                    <a href={review.source_url} className="link" rel="noopener noreferrer" target="_blank">
                      {fill(t.orderFile, { date: review.order_date }, locale)}
                    </a>
                  </td>
                  <td className="tabular-nums whitespace-nowrap">{review.order_date}</td>
                  <td />
                  <td>{t.orderBasis}</td>
                </tr>
              )}
              {maintenanceWindows > 0 && (
                <tr>
                  <th scope="row" className="font-normal">
                    {t.sourceNames.iesco_maintenance}
                  </th>
                  <td>
                    <a href={IESCO_MAINTENANCE} className="link" rel="noopener noreferrer" target="_blank">
                      {fill(t.maintFile, { n: maintenanceWindows }, locale)}
                    </a>
                  </td>
                  <td />
                  <td />
                  <td>{t.maintBasis}</td>
                </tr>
              )}
              <tr>
                <th scope="row" className="font-normal">
                  {t.sourceNames.news}
                </th>
                <td>{t.newsFile}</td>
                <td />
                <td />
                <td>{t.newsBasis}</td>
              </tr>
            </tbody>
          </table>
        </ScrollRegion>
        {iesco?.published_label && (
          <p className="max-w-prose text-sm text-muted">
            {fill(t.datesNote, { label: iesco.published_label, date: iesco.effective_from }, locale)}
          </p>
        )}
      </section>
      <section className="rule pt-4 space-y-1">
        <h2 className="headline text-2xl">{t.attribution}</h2>
        <ul className="list-disc ps-5">
          {meta.attribution.map((a) => (
            <li key={a}>
              <ExportText value={fromExport(a, locale)} />
            </li>
          ))}
        </ul>
      </section>
      <section className="rule pt-4 space-y-1">
        <h2 className="headline text-2xl">{t.disclaimer}</h2>
        <ExportText as="p" className="max-w-prose" value={fromExport(meta.disclaimer, locale)} />
      </section>
    </article>
  );
}
