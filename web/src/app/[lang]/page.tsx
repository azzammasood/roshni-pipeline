import { fill } from "@/i18n/dictionaries";
import { loadDocument } from "@/lib/data";
import { resolveLocale } from "@/lib/locale";

export default async function Home({ params }: PageProps<"/[lang]">) {
  const { locale, dict } = await resolveLocale(params);
  const feeders = (await loadDocument("feeders")).data.filter((f) => f.has_schedule);
  const iesco = feeders.filter((f) => f.source === "iesco").length;
  return (
    <section className="space-y-3">
      <h1 className="text-2xl font-semibold">{dict.home.title}</h1>
      <p className="max-w-prose">{dict.home.intro}</p>
      <p className="text-muted">
        {fill(dict.home.counts, { feeders: feeders.length, iesco, ke: feeders.length - iesco }, locale)}
      </p>
    </section>
  );
}
