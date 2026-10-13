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
import { censusName, circleName, ibcName } from "@/lib/names";
import { hourWindows } from "@/lib/windows";
import { ScrollRegion } from "@/components/ScrollRegion";
import { ExportText } from "@/components/ExportText";
import { ClockRange, Stamp } from "@/components/Clock";
import { MatchInfo } from "@/components/MatchInfo";
import { ReleaseLink } from "@/components/ReleaseLink";

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
    [t.circle, circleName(feeder.circle)],
    [t.grid, feeder.grid],
    [t.ibc, feeder.ibc && ibcName(feeder.ibc)],
    [t.category, feeder.category],
    [t.atcLoss, feeder.atc_loss_pct === null ? null : pct(feeder.atc_loss_pct, locale)],
    [t.effectiveFrom, profile?.effective_from ?? null],
  ];
  const dailyTotal = profile?.daily?.reduce((a, b) => a + b, 0) ?? 0;
  const halves = { am: dict.site.clock.am, pm: dict.site.clock.pm };
  const matchStrings = { ...dict.match, confidence: dict.common.confidence, exact: dict.common.exact };

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
          <Stamp iso={profilesDoc.last_updated} />
        </p>
      </header>

      {!profile && <p>{t.noSchedule}</p>}

      {profile?.daily && (
        <section className="space-y-2">
          <h2 className="text-lg font-semibold">{t.dailyTitle}</h2>
          <p className="text-sm text-muted">{t.dailyIntro}</p>
          <HourBars
            minutes={profile.daily}
            label={t.dailyIntro}
            unit={(n) => fill(t.minutes, { n }, locale)}
          />
          <p className="font-medium">
            {fill(t.minutesPerDay, { h: Math.floor(dailyTotal / 60), m: dailyTotal % 60 }, locale)}
          </p>
          {profile.daily_windows && (
            <>
              <h3 className="font-semibold">{t.windows}</h3>
              <ul className="tabular-nums" dir="ltr">
                {profile.daily_windows.map((w) => (
                  <li key={w.start_min} className="text-start">
                    <ClockRange start={w.start_min} end={w.end_min} />
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
            halves={halves}
          />
          <h3 className="font-semibold pt-2">{t.levelWindows}</h3>
          <dl className="grid grid-cols-[fit-content(30%)_1fr] gap-x-4 gap-y-1 text-sm">
            {Object.entries(profile.scenario_levels).map(([n, mins]) => (
              <div key={n} className="contents">
                <dt className="text-muted whitespace-nowrap">{fill(t.levelRow, { n }, locale)}</dt>
                <dd className="flex flex-wrap gap-x-3">
                  {hourWindows(mins).map((w) => (
                    <ClockRange key={w.start} start={w.start} end={w.end} />
                  ))}
                </dd>
              </div>
            ))}
          </dl>
        </section>
      )}

      {feeder.localities.length > 0 && (
        <section className="space-y-2">
          <h2 className="text-lg font-semibold">{t.localitiesTitle}</h2>
          <p className="text-sm text-muted">{t.localitiesIntro}</p>
          <ul className="space-y-1">
            {feeder.localities.map((l) => (
              <li key={l.area_id}>
                <bdi>{censusName(l.area_name)}</bdi>{" "}
                <MatchInfo
                  confidence={l.match_status === "auto_exact" ? null : l.match_confidence}
                  review={l.review}
                  printed={feeder.name}
                  matched={l.area_name}
                  locale={locale}
                  t={matchStrings}
                />
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
                    <td>
                      <ClockRange start={s.start_local} end={s.end_local} />
                    </td>
                    <td>
                      <bdi>{s.feeder_name_as_printed}</bdi>
                      <span className="block">
                        <MatchInfo
                          confidence={s.match_confidence}
                          review={s.match_review}
                          printed={s.feeder_name_as_printed}
                          matched={feeder.name}
                          locale={locale}
                          t={matchStrings}
                        />
                      </span>
                    </td>
                    <td>
                      <ReleaseLink no={s.release_no} period={s.release_period} locale={locale} t={dict.common} />
                    </td>
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
