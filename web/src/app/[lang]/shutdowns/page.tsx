import type { Metadata } from "next";
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
  return (
    <section className="space-y-3">
      <h1 className="text-2xl font-semibold">{dict.shutdowns.title}</h1>
      <p className="max-w-prose">{dict.shutdowns.intro}</p>
      {rows.length > 0 && (
        <p className="text-muted">
          {fill(dict.shutdowns.count, { n: rows.length, from: dates[0], to: dates.at(-1)! }, locale)}
        </p>
      )}
    </section>
  );
}
