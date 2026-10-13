import type { Metadata } from "next";
import { ShutdownTable } from "@/components/ShutdownTable";
import { fill } from "@/i18n/dictionaries";
import { loadDocument } from "@/lib/data";
import { resolveLocale } from "@/lib/locale";

export async function generateMetadata({
  params,
}: PageProps<"/[lang]/shutdowns">): Promise<Metadata> {
  return { title: (await resolveLocale(params)).dict.shutdowns.title };
}

export default async function Shutdowns({ params }: PageProps<"/[lang]/shutdowns">) {
  const { locale, dict } = await resolveLocale(params);
  const rows = (await loadDocument("planned_shutdowns")).data;
  const dates = rows.map((r) => r.outage_date).sort();
  const { shutdowns, common, matchState, feeder, match } = dict;
  return (
    <div className="space-y-5">
      <section className="space-y-2">
        <h1 className="text-2xl font-semibold">{shutdowns.title}</h1>
        <p className="max-w-prose">{shutdowns.intro}</p>
        {rows.length > 0 && (
          <p className="text-sm text-muted">
            {fill(shutdowns.count, { n: rows.length, from: dates[0], to: dates.at(-1)! }, locale)}
          </p>
        )}
      </section>
      <ShutdownTable locale={locale} t={{ shutdowns, common, matchState, feeder, match }} />
    </div>
  );
}
