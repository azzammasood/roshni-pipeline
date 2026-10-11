import type { Metadata } from "next";
import { loadDocument } from "@/lib/data";
import { resolveLocale } from "@/lib/locale";

export async function generateMetadata({
  params,
}: PageProps<"/[lang]/karachi-equity">): Promise<Metadata> {
  return { title: (await resolveLocale(params)).dict.equity.title };
}

export default async function Equity({ params }: PageProps<"/[lang]/karachi-equity">) {
  const { dict } = await resolveLocale(params);
  const equity = (await loadDocument("equity")).data;
  return (
    <section className="space-y-3">
      <h1 className="text-2xl font-semibold">{dict.equity.title}</h1>
      <p className="max-w-prose">{dict.equity.intro}</p>
      <p className="text-muted">{equity.scope_note}</p>
    </section>
  );
}
