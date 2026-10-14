import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { HourBars } from "@/components/HourBars";
import { PinButton } from "@/components/PinButton";
import { HourAxis, PowerLine } from "@/components/PowerLine";
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
  const area = feeder.ibc ? ibcName(feeder.ibc) : circleName(feeder.circle);
  const matchStrings = { ...dict.match, confidence: dict.common.confidence, exact: dict.common.exact };

  return (
    <article className="space-y-10">
      <header className="space-y-4">
        <p className="kicker flex flex-wrap gap-x-2">
          <span>{dict.sources[feeder.source]}</span>
          {area && (
            <>
              <span aria-hidden="true">·</span>
              <bdi>{area}</bdi>
            </>
          )}
          {feeder.grid && (
            <>
              <span aria-hidden="true">·</span>
              <span>
                {t.grid} <bdi>{feeder.grid}</bdi>
              </span>
            </>
          )}
        </p>
        <h1 className="headline text-4xl sm:text-6xl break-words">
          <bdi>{feeder.name}</bdi>
        </h1>
        <PinButton feederId={feeder.feeder_id} pin={t.pin} pinned={t.pinned} />
        <dl className="rule grid grid-cols-2 sm:grid-cols-4 gap-x-6">
          {rows
            .filter(([, v]) => v)
            .map(([k, v]) => (
              <div key={k} className="py-2 border-b border-line min-w-0">
                <dt className="kicker text-muted">{k}</dt>
                <dd className="font-mono text-sm break-words">
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

      {!profile && <p className="headline text-2xl">{t.noSchedule}</p>}

      {profile?.daily && (
        <section className="rule pt-4 space-y-4">
          <h2 className="headline text-3xl">{t.dailyTitle}</h2>
          <p className="headline text-xl">
            {fill(t.minutesPerDay, { h: Math.floor(dailyTotal / 60), m: dailyTotal % 60 }, locale)}
          </p>
          {profile.daily_windows && (
            <>
              <PowerLine
                windows={profile.daily_windows.map((w) => ({ start: w.start_min, end: w.end_min }))}
                label={dict.lead.strip}
              />
              <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                <h3 className="kicker">{t.windows}</h3>
                <ul className="flex flex-wrap gap-x-3 gap-y-1 tabular-nums">
                  {profile.daily_windows.map((w) => (
                    <li key={w.start_min}>
                      <ClockRange start={w.start_min} end={w.end_min} />
                    </li>
                  ))}
                </ul>
              </div>
            </>
          )}
          <h3 className="kicker pt-2">{t.dailyIntro}</h3>
          <HourBars minutes={profile.daily} label={t.dailyIntro} unit={(n) => fill(t.minutes, { n }, locale)} />
        </section>
      )}

      {profile?.scenario_levels && (
        <section className="rule pt-4 space-y-3">
          <h2 className="headline text-3xl">{t.scenarioTitle}</h2>
          <p className="max-w-prose">{t.scenarioIntro}</p>
          <div className="grid gap-x-4 sm:grid-cols-[7rem_minmax(0,1fr)] sticky top-0 bg-bg z-[1]">
            <span aria-hidden="true" className="hidden sm:block" />
            <HourAxis wide />
          </div>
          <ul className="space-y-1">
            {Object.entries(profile.scenario_levels).map(([n, mins]) => {
              const windows = hourWindows(mins);
              return (
                <li key={n} className="grid gap-x-4 sm:grid-cols-[7rem_minmax(0,1fr)] items-center border-b border-line py-2">
                  <h3 className="headline text-xl">{fill(t.levelRow, { n }, locale)}</h3>
                  <div className="min-w-0">
                    <PowerLine windows={windows} label={fill(t.levelStrip, { n }, locale)} compact />
                    <p className="flex flex-wrap gap-x-3 text-sm">
                      {windows.length === 0
                        ? dict.common.none
                        : windows.map((w) => <ClockRange key={w.start} start={w.start} end={w.end} />)}
                    </p>
                  </div>
                </li>
              );
            })}
          </ul>
        </section>
      )}

      {feeder.localities.length > 0 && (
        <section className="rule pt-4 space-y-2">
          <h2 className="headline text-3xl">{t.localitiesTitle}</h2>
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
        <section className="rule pt-4 space-y-2">
          <h2 className="headline text-3xl">
            {t.shutdownsTitle}{" "}
            <span className="font-mono text-base text-muted">({num(shutdowns.length, locale)})</span>
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
