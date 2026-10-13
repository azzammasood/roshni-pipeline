import type { Metadata } from "next";
import { ScrollRegion } from "@/components/ScrollRegion";
import { ShareBars } from "@/components/ShareBars";
import { fill, fromExport } from "@/i18n/dictionaries";
import { loadDocument } from "@/lib/data";
import { columnFormat, num } from "@/lib/format";
import { censusName, ibcName } from "@/lib/names";
import { isoWeekMonday } from "@/lib/time";
import { resolveLocale } from "@/lib/locale";
import { ExportText } from "@/components/ExportText";

/** IBCs with fewer scheduled feeders than this are flagged (same threshold as the weekly report). */
const MIN_N = 10;

export async function generateMetadata({
  params,
}: PageProps<"/[lang]/karachi-equity">): Promise<Metadata> {
  return { title: (await resolveLocale(params)).dict.equity.title };
}

export default async function Equity({ params }: PageProps<"/[lang]/karachi-equity">) {
  const { locale, dict } = await resolveLocale(params);
  const t = dict.equity;
  const doc = await loadDocument("equity");
  const meta = (await loadDocument("meta")).data;
  const { ibc, subdivisions, correlations, anomalies, report, scope_note } = doc.data;
  const effective = meta.sources.find((s) => s.source === "kelectric_schedule")?.effective_from;

  const sum = (pick: (r: (typeof ibc)[number]) => number) => ibc.reduce((a, r) => a + pick(r), 0);
  const kpis: [string, number][] = [
    [t.kpiListed, sum((r) => r.listed_feeders)],
    [t.kpiScheduled, sum((r) => r.scheduled_feeders)],
    [t.kpi12h, sum((r) => r.feeders_12h)],
    [t.kpi6h, sum((r) => r.feeders_6h)],
    [t.kpiIbcs, ibc.length],
  ];
  const ranked = ibc
    .filter((r) => r.share_12h_pct !== null)
    .sort((a, b) => b.share_12h_pct! - a.share_12h_pct! || (a.ibc < b.ibc ? -1 : 1));
  const byName = [...ibc].sort((a, b) => (a.ibc < b.ibc ? -1 : 1));
  const measure = (k: string) => (t.measures as Record<string, string>)[k] ?? k;
  const n = (v: number) => num(v, locale);
  // One number of decimals per column (padded, never rounded: the equity gate checks values).
  const col = <T,>(rows: T[], pick: (r: T) => number | null, suffix = "") =>
    columnFormat(rows.map(pick), locale, suffix);
  const ibcShare = col(ibc, (r) => r.share_12h_pct, "%");
  const ibcHours = col(ibc, (r) => r.mean_scheduled_hours);
  const ibcLoss = col(ibc, (r) => r.mean_atc_loss_pct, "%");
  const subShare = col(subdivisions, (s) => s.share_12h_pct, "%");
  const subHours = col(subdivisions, (s) => s.mean_scheduled_hours);
  const subLit = col(subdivisions, (s) => s.literacy_pct, "%");
  const subDeg = col(subdivisions, (s) => s.degree_share_pct, "%");
  const subPacca = col(subdivisions, (s) => s.pacca_share_pct, "%");
  const subHh = col(subdivisions, (s) => s.avg_household_size);
  const rho = col(correlations, (c) => c.spearman_rho);

  return (
    <article className="space-y-10">
      <header className="space-y-3">
        <h1 className="text-2xl font-semibold">{t.title}</h1>
        <p className="max-w-prose">{t.intro}</p>
        <p className="max-w-prose rounded border border-line bg-surface p-3 text-sm">
          <strong>{t.scope}:</strong> <ExportText value={fromExport(scope_note, locale)} />
        </p>
        {effective && (
          <p className="text-sm text-muted">
            <ExportText value={fromExport(doc.label, locale)} />. {fill(t.effective, { date: effective }, locale)}
          </p>
        )}
      </header>

      <section>
        <dl className="grid grid-cols-2 sm:grid-cols-5 gap-3">
          {kpis.map(([label, value]) => (
            <div key={label} className="rounded border border-line bg-surface p-3">
              <dt className="text-xs text-muted">{label}</dt>
              <dd className="text-2xl font-semibold tabular-nums">{n(value)}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">{t.shareTitle}</h2>
        <p className="max-w-prose text-sm text-muted">{fill(t.shareIntro, { min: MIN_N }, locale)}</p>
        <ShareBars
          rows={ranked.map((r) => ({
            label: ibcName(r.ibc),
            value: r.share_12h_pct!,
            note: `(n = ${n(r.scheduled_feeders)})`,
            flag: r.scheduled_feeders < MIN_N ? t.smallN : undefined,
          }))}
          valueText={ibcShare}
        />
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">{t.ibcTableTitle}</h2>
        <ScrollRegion label={t.ibcTableTitle}>
          <table className="data">
            <thead>
              <tr>
                <th scope="col">{t.colIbc}</th>
                <th scope="col">{t.colListed}</th>
                <th scope="col">{t.colScheduled}</th>
                <th scope="col">{t.col12h}</th>
                <th scope="col">{t.col6h}</th>
                <th scope="col">{t.colShare}</th>
                <th scope="col">{t.colMeanHours}</th>
                <th scope="col">{t.colLoss}</th>
                <th scope="col">{t.colLossN}</th>
                <th scope="col">{t.colSubdivision}</th>
              </tr>
            </thead>
            <tbody className="tabular-nums">
              {byName.map((r) => (
                <tr key={r.ibc}>
                  <th scope="row" className="whitespace-nowrap font-normal">
                    <bdi>{ibcName(r.ibc)}</bdi>
                  </th>
                  <td>{n(r.listed_feeders)}</td>
                  <td>{n(r.scheduled_feeders)}</td>
                  <td>{n(r.feeders_12h)}</td>
                  <td>{n(r.feeders_6h)}</td>
                  <td>{ibcShare(r.share_12h_pct)}</td>
                  <td>{ibcHours(r.mean_scheduled_hours)}</td>
                  <td>{ibcLoss(r.mean_atc_loss_pct)}</td>
                  <td>{n(r.feeders_with_loss)}</td>
                  <td>
                    <bdi>{r.census_subdivision ? censusName(r.census_subdivision) : "–"}</bdi>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollRegion>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">{t.subTitle}</h2>
        <p className="max-w-prose text-sm text-muted">
          {fill(
            t.subIntro,
            { ibcs: subdivisions.reduce((a, s) => a + s.ibcs, 0), subs: subdivisions.length },
            locale,
          )}
        </p>
        <ScrollRegion label={t.subTitle}>
          <table className="data">
            <thead>
              <tr>
                <th scope="col">{t.colSubName}</th>
                <th scope="col">{t.colIbcs}</th>
                <th scope="col">{t.colScheduled}</th>
                <th scope="col">{t.colShare}</th>
                <th scope="col">{t.colMeanHours}</th>
                <th scope="col">{t.colLiteracy}</th>
                <th scope="col">{t.colDegree}</th>
                <th scope="col">{t.colPacca}</th>
                <th scope="col">{t.colHousehold}</th>
              </tr>
            </thead>
            <tbody className="tabular-nums">
              {[...subdivisions]
                .sort((a, b) => b.share_12h_pct - a.share_12h_pct || (a.subdivision_name < b.subdivision_name ? -1 : 1))
                .map((s) => (
                  <tr key={s.subdivision_area_id}>
                    <th scope="row" className="whitespace-nowrap font-normal">
                      <bdi>{censusName(s.subdivision_name)}</bdi>
                    </th>
                    <td>{n(s.ibcs)}</td>
                    <td>{n(s.scheduled_feeders)}</td>
                    <td>{subShare(s.share_12h_pct)}</td>
                    <td>{subHours(s.mean_scheduled_hours)}</td>
                    <td>{subLit(s.literacy_pct)}</td>
                    <td>{subDeg(s.degree_share_pct)}</td>
                    <td>{subPacca(s.pacca_share_pct)}</td>
                    <td>{subHh(s.avg_household_size)}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </ScrollRegion>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">{t.corrTitle}</h2>
        <p className="max-w-prose text-sm text-muted">
          {fill(t.corrIntro, { n: subdivisions.length }, locale)}
        </p>
        <ScrollRegion label={t.corrTitle}>
          <table className="data">
            <thead>
              <tr>
                <th scope="col">{t.colUnit}</th>
                <th scope="col">{t.colPair}</th>
                <th scope="col">{t.colRho}</th>
                <th scope="col">{t.colN}</th>
              </tr>
            </thead>
            <tbody>
              {correlations.map((c) => (
                <tr key={`${c.unit}-${c.y_name}-${c.x_name}`}>
                  <td>{t.units[c.unit]}</td>
                  <th scope="row" className="font-normal">
                    {fill(t.pair, { y: measure(c.y_name), x: measure(c.x_name) }, locale)}
                  </th>
                  <td className="tabular-nums">{rho(c.spearman_rho)}</td>
                  <td className="tabular-nums">{n(c.n)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollRegion>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">{t.anomTitle}</h2>
        <p className="max-w-prose text-sm text-muted">{t.anomIntro}</p>
        <ScrollRegion label={t.anomTitle}>
          <table className="data">
            <thead>
              <tr>
                <th scope="col">{t.colRule}</th>
                <th scope="col">{t.colFeeders}</th>
              </tr>
            </thead>
            <tbody>
              {anomalies.map((a) => (
                <tr key={a.rule}>
                  <th scope="row" className="font-normal">
                    {(t.rules as Record<string, string>)[a.rule] ?? a.description}
                  </th>
                  <td className="tabular-nums">{n(a.feeders)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollRegion>
      </section>

      {report && (
        <section className="space-y-3">
          <h2 className="text-lg font-semibold">{fill(t.reportTitle, { week: isoWeekMonday(report.iso_week) }, locale)}</h2>
          <p className="text-sm text-muted max-w-prose">
            {report.engine === "template" ? t.engineTemplate : fill(t.engineLlm, { engine: report.engine }, locale)}
          </p>
          {locale !== "en" && <p className="text-sm font-medium">{dict.common.englishOnly}</p>}
          <div className="space-y-3 max-w-prose" lang="en" dir="ltr">
            {report.narrative
              .split(/\n\s*\n/)
              .filter((p) => p.trim())
              .map((p, i) => (
                <p key={i}>{p.trim()}</p>
              ))}
          </div>
          <details className="text-sm">
            <summary className="link w-fit">{t.factsTitle}</summary>
            <ScrollRegion label={t.factsTitle}>
              <table className="data mt-2">
                <thead>
                  <tr>
                    <th scope="col">{t.colFact}</th>
                    <th scope="col">{t.colValue}</th>
                    <th scope="col">{t.colQuery}</th>
                  </tr>
                </thead>
                <tbody>
                  {report.facts.map((f) => (
                    <tr key={f.id}>
                      <th scope="row" className="font-normal font-mono text-xs">
                        {f.id}
                      </th>
                      <td className="tabular-nums">{typeof f.value === "number" ? n(f.value) : f.value}</td>
                      <td className="font-mono text-xs">{f.query_id}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </ScrollRegion>
          </details>
        </section>
      )}
    </article>
  );
}
