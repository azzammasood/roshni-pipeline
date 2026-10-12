import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { HourBars } from "@/components/HourBars";
import { LevelGrid } from "@/components/LevelGrid";
import { builtLocales } from "@/i18n/config";
import { fill, fromExport } from "@/i18n/dictionaries";
import { loadDocument, loadFeederIndex } from "@/lib/data";
import { num, pct } from "@/lib/format";
import { resolveLocale } from "@/lib/locale";
import { feederSlug, slugIndex } from "@/lib/slug";
import { formatKarachi, hhmm } from "@/lib/time";
import { ScrollRegion } from "@/components/ScrollRegion";
import { ExportText } from "@/components/ExportText";

export const dynamicParams = false;

export async function generateStaticParams() {
  const feeders = (await loadDocument("feeders")).data;
  slugIndex(feeders); // fails the build on a slug collision
  return builtLocales.flatMap((lang) => feeders.map((f) => ({ lang, slug: feederSlug(f.feeder_id) })));
}

async function findFeeder(slug: string) {
  const feeder = (await loadFeederIndex()).bySlug.get(slug);
  if (!feeder) notFound();
  return feeder;
}

export async function generateMetadata({
  params,
}: PageProps<"/[lang]/feeder/[slug]">): Promise<Metadata> {
  return { title: (await findFeeder((await params).slug)).name };
}

export default async function FeederPage({ params }: PageProps<"/[lang]/feeder/[slug]">) {
  const { locale, dict } = await resolveLocale(params);
  const t = dict.feeder;
  const feeder = await findFeeder((await params).slug);
  const profilesDoc = await loadDocument("dark_profiles");
  const index = await loadFeederIndex();
  const profile = index.profiles.get(feeder.feeder_id);
  const shutdowns = index.shutdowns.get(feeder.feeder_id) ?? [];

  const rows: [string, string | null][] = [
    [t.source, dict.sources[feeder.source]],
    [t.code, feeder.feeder_code],
    [t.circle, feeder.circle],
    [t.grid, feeder.grid],
    [t.ibc, feeder.ibc],
    [t.category, feeder.category],
    [t.atcLoss, feeder.atc_loss_pct === null ? null : pct(feeder.atc_loss_pct, locale)],
    [t.effectiveFrom, profile?.effective_from ?? null],
  ];
  const dailyTotal = profile?.daily?.reduce((a, b) => a + b, 0) ?? 0;

  return (
    <article className="space-y-8">
      <header className="space-y-3">
        <h1 className="text-2xl font-semibold">
          <bdi>{feeder.name}</bdi>
        </h1>
        <dl className="grid grid-cols-[fit-content(50%)_1fr] gap-x-6 gap-y-1">
          {rows
            .filter(([, v]) => v)
            .map(([k, v]) => (
              <div key={k} className="contents">
                <dt className="text-muted">{k}</dt>
                <dd>
                  <bdi>{v}</bdi>
                </dd>
              </div>
            ))}
        </dl>
        <p className="text-sm text-muted">
          <ExportText value={fromExport(profilesDoc.label, locale)} />. {dict.footer.lastUpdated}:{" "}
          <time dateTime={profilesDoc.last_updated}>{formatKarachi(profilesDoc.last_updated, locale)}</time>
        </p>
      </header>

      {!profile && <p>{t.noSchedule}</p>}

      {profile?.daily && (
        <section className="space-y-2">
          <h2 className="text-lg font-semibold">{t.dailyTitle}</h2>
          <p className="text-sm text-muted">{t.dailyIntro}</p>
          <HourBars minutes={profile.daily} label={t.dailyIntro} />
          <p className="font-medium">
            {fill(t.minutesPerDay, { h: Math.floor(dailyTotal / 60), m: dailyTotal % 60 }, locale)}
          </p>
          {profile.daily_windows && (
            <>
              <h3 className="font-semibold">{t.windows}</h3>
              <ul className="tabular-nums" dir="ltr">
                {profile.daily_windows.map((w) => (
                  <li key={w.start_min} className="text-start">
                    {hhmm(w.start_min)}–{hhmm(w.end_min)}
                  </li>
                ))}
              </ul>
            </>
          )}
        </section>
      )}

      {profile?.scenario_levels && (
        <section className="space-y-2">
          <h2 className="text-lg font-semibold">{t.scenarioTitle}</h2>
          <p className="text-sm text-muted max-w-prose">{t.scenarioIntro}</p>
          <LevelGrid
            levels={profile.scenario_levels}
            caption={t.scenarioTitle}
            levelLabel={(n) => fill(t.levelRow, { n }, locale)}
            hourLabel={t.hour}
            darkLabel={t.darkCell}
          />
        </section>
      )}

      {feeder.localities.length > 0 && (
        <section className="space-y-2">
          <h2 className="text-lg font-semibold">{t.localitiesTitle}</h2>
          <p className="text-sm text-muted">{t.localitiesIntro}</p>
          <ul className="space-y-1">
            {feeder.localities.map((l) => (
              <li key={l.area_id}>
                <bdi>{l.area_name}</bdi>{" "}
                <span className="text-sm text-muted">
                  (
                  {l.match_status === "auto_exact"
                    ? dict.common.exact
                    : fill(dict.common.confidence, { pct: Math.round(l.match_confidence * 100) }, locale)}
                  )
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {shutdowns.length > 0 && (
        <section className="space-y-2">
          <h2 className="text-lg font-semibold">
            {t.shutdownsTitle}{" "}
            <span className="font-normal text-muted">({num(shutdowns.length, locale)})</span>
          </h2>
          <ScrollRegion label={t.shutdownsTitle}>
            <table className="data">
              <thead>
                <tr>
                  <th scope="col">{dict.common.date}</th>
                  <th scope="col">{dict.common.window}</th>
                  <th scope="col">{t.asPrinted}</th>
                  <th scope="col">{t.release}</th>
                </tr>
              </thead>
              <tbody>
                {shutdowns.map((s) => (
                  <tr key={s.shutdown_id}>
                    <td className="tabular-nums whitespace-nowrap">{s.outage_date}</td>
                    <td className="tabular-nums whitespace-nowrap" dir="ltr">
                      {s.start_local}–{s.end_local}
                    </td>
                    <td>
                      <bdi>{s.feeder_name_as_printed}</bdi>
                      {s.match_confidence !== null && s.match_confidence < 1 && (
                        <span className="block text-xs text-muted">
                          {fill(dict.common.confidence, { pct: Math.round(s.match_confidence * 100) }, locale)}
                        </span>
                      )}
                    </td>
                    <td>{s.release_no}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </ScrollRegion>
        </section>
      )}
    </article>
  );
}
