import { DarkNowPanel } from "@/components/DarkNowPanel";
import { NationalPanel } from "@/components/NationalPanel";
import { NewsStrip } from "@/components/NewsStrip";
import { fill } from "@/i18n/dictionaries";
import { loadDocument } from "@/lib/data";
import { resolveLocale } from "@/lib/locale";

export default async function Home({ params }: PageProps<"/[lang]">) {
  const { locale, dict } = await resolveLocale(params);
  const feeders = (await loadDocument("feeders")).data.filter((f) => f.has_schedule);
  const iesco = feeders.filter((f) => f.source === "iesco").length;
  const national = await loadDocument("national");
  const news = await loadDocument("news");
  const { home, common, matchState, sources, lead } = dict;
  return (
    <div className="space-y-12">
      {/* The national picture first (owner, 2026-10-13), then the visitor's own feeder. */}
      <NationalPanel data={national.data} locale={locale} t={dict.national} />
      <NewsStrip items={news.data} t={dict.news} />
      <div className="rule pt-6">
    <DarkNowPanel
      locale={locale}
      counts={fill(home.counts, { feeders: feeders.length, iesco, ke: feeders.length - iesco }, locale)}
      t={{ home, common, matchState, sources, lead, halves: { am: dict.site.clock.am, pm: dict.site.clock.pm } }}
    />
      </div>
    </div>
  );
}
