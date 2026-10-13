import { DarkNowPanel } from "@/components/DarkNowPanel";
import { fill } from "@/i18n/dictionaries";
import { loadDocument } from "@/lib/data";
import { resolveLocale } from "@/lib/locale";

export default async function Home({ params }: PageProps<"/[lang]">) {
  const { locale, dict } = await resolveLocale(params);
  const feeders = (await loadDocument("feeders")).data.filter((f) => f.has_schedule);
  const iesco = feeders.filter((f) => f.source === "iesco").length;
  const { home, common, matchState, sources } = dict;
  return (
    <div className="space-y-6">
      <section className="space-y-2">
        <h1 className="text-2xl font-semibold">{home.title}</h1>
        <p className="max-w-prose">{home.intro}</p>
        <p className="text-sm text-muted">
          {fill(home.counts, { feeders: feeders.length, iesco, ke: feeders.length - iesco }, locale)}
        </p>
      </section>
      <DarkNowPanel
        locale={locale}
        t={{ home, common, matchState, sources, halves: { am: dict.site.clock.am, pm: dict.site.clock.pm } }}
      />
    </div>
  );
}
