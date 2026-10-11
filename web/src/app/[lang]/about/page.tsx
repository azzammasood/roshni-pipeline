import type { Metadata } from "next";
import { loadDocument } from "@/lib/data";
import { resolveLocale } from "@/lib/locale";

export async function generateMetadata({ params }: PageProps<"/[lang]/about">): Promise<Metadata> {
  return { title: (await resolveLocale(params)).dict.about.title };
}

export default async function About({ params }: PageProps<"/[lang]/about">) {
  const { dict } = await resolveLocale(params);
  const meta = (await loadDocument("meta")).data;
  return (
    <section className="space-y-4">
      <h1 className="text-2xl font-semibold">{dict.about.title}</h1>
      <h2 className="text-lg font-semibold">{dict.about.attribution}</h2>
      <ul className="list-disc ps-5">
        {meta.attribution.map((a) => (
          <li key={a}>{a}</li>
        ))}
      </ul>
      <h2 className="text-lg font-semibold">{dict.about.disclaimer}</h2>
      <p className="max-w-prose">{meta.disclaimer}</p>
    </section>
  );
}
