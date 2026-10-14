import { DarkNowPanel } from "@/components/DarkNowPanel";
import { NationalPanel } from "@/components/NationalPanel";
import { MonthlyPanel } from "@/components/MonthlyPanel";
import { NewsStrip } from "@/components/NewsStrip";
import { Reveal } from "@/components/Reveal";
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
  const jump: [string, string][] = [
    ["#national", home.jumpNational],
    ["#monthly", home.jumpMonthly],
    ["#news", home.jumpNews],
    ["#lead", home.jumpFeeder],
  ];
  return (
    <div className="space-y-12">
      <nav aria-label={home.jumpLabel} className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm border-b border-line pb-2">
        <span className="kicker text-muted">{home.jumpLabel}</span>
        {jump.map(([href, label]) => (
          <a key={href} href={href} className="link">
            {label}
          </a>
        ))}
      </nav>
      {/* The national picture first (owner, 2026-10-13), then the visitor's own feeder. */}
      <NationalPanel data={national.data} locale={locale} t={dict.national} />
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
          t={{ home, common, matchState, sources, lead, halves: { am: dict.site.clock.am, pm: dict.site.clock.pm } }}
        />
      </div>
    </div>
  );
}
