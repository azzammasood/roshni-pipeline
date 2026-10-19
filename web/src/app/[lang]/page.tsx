import { DarkNowPanel } from "@/components/DarkNowPanel";
import { NationalPanel } from "@/components/NationalPanel";
import { MonthlyPanel } from "@/components/MonthlyPanel";
import { NewsStrip } from "@/components/NewsStrip";
import { PageNav } from "@/components/PageNav";
import { Reveal } from "@/components/Reveal";
import { fill } from "@/i18n/dictionaries";
import { loadDocument } from "@/lib/data";
import { schedulePlans } from "@/lib/plans";
import { resolveLocale } from "@/lib/locale";

export default async function Home({ params }: PageProps<"/[lang]">) {
  const { locale, dict } = await resolveLocale(params);
  const feeders = (await loadDocument("feeders")).data.filter((f) => f.has_schedule);
  const iesco = feeders.filter((f) => f.source === "iesco").length;
  const national = await loadDocument("national");
  const news = await loadDocument("news");
  const plans = schedulePlans((await loadDocument("dark_profiles")).data, national.data, locale);
  const { home, common, matchState, sources, lead } = dict;
  const jump: [string, string][] = [
    ["#national", home.jumpNational],
    ["#monthly", home.jumpMonthly],
    ["#news", home.jumpNews],
    ["#lead", home.jumpFeeder],
    ["#listings", home.jumpNow],
  ];
  return (
    <div className="space-y-12">
      <PageNav label={home.jumpLabel} links={jump} />
      {/* The national picture first (owner, 2026-10-13), then the visitor's own feeder. */}
      <NationalPanel data={national.data} locale={locale} t={dict.national} plans={plans} />
      <Reveal>
        <MonthlyPanel data={national.data} locale={locale} t={dict.monthly} />
      </Reveal>
      <Reveal>
        <NewsStrip items={news.data} t={dict.news} />
      </Reveal>
      <div className="rule pt-6 scroll-mt-4">
        <DarkNowPanel
          locale={locale}
          counts={fill(home.counts, { feeders: feeders.length, iesco, ke: feeders.length - iesco }, locale)}
          t={{ home, common, matchState, sources, lead, maintenance: dict.maintenance, halves: { am: dict.site.clock.am, pm: dict.site.clock.pm } }}
        />
      </div>
    </div>
  );
}
