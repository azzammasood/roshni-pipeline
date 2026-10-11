import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { locales } from "@/i18n/config";
import { loadDocument } from "@/lib/data";
import { resolveLocale } from "@/lib/locale";
import { feederSlug, slugIndex } from "@/lib/slug";

export const dynamicParams = false;

export async function generateStaticParams() {
  const feeders = (await loadDocument("feeders")).data;
  slugIndex(feeders); // fails the build on a slug collision
  return locales.flatMap((lang) => feeders.map((f) => ({ lang, slug: feederSlug(f.feeder_id) })));
}

async function findFeeder(slug: string) {
  const feeder = slugIndex((await loadDocument("feeders")).data).get(slug);
  if (!feeder) notFound();
  return feeder;
}

export async function generateMetadata({
  params,
}: PageProps<"/[lang]/feeder/[slug]">): Promise<Metadata> {
  return { title: (await findFeeder((await params).slug)).name };
}

export default async function FeederPage({ params }: PageProps<"/[lang]/feeder/[slug]">) {
  const { dict } = await resolveLocale(params);
  const feeder = await findFeeder((await params).slug);
  const profile = (await loadDocument("dark_profiles")).data.find(
    (p) => p.feeder_id === feeder.feeder_id,
  );
  const rows: [string, string | null][] = [
    [dict.feeder.source, dict.sources[feeder.source]],
    [dict.feeder.code, feeder.feeder_code],
    [dict.feeder.circle, feeder.circle],
    [dict.feeder.grid, feeder.grid],
    [dict.feeder.ibc, feeder.ibc],
    [dict.feeder.effectiveFrom, profile?.effective_from ?? null],
  ];
  return (
    <article className="space-y-4">
      <h1 className="text-2xl font-semibold">{feeder.name}</h1>
      <dl className="grid grid-cols-[max-content_1fr] gap-x-6 gap-y-1">
        {rows
          .filter(([, v]) => v)
          .map(([k, v]) => (
            <div key={k} className="contents">
              <dt className="text-muted">{k}</dt>
              <dd>{v}</dd>
            </div>
          ))}
      </dl>
      {!profile && <p>{dict.feeder.noSchedule}</p>}
    </article>
  );
}
