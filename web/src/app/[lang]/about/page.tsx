import type { Metadata } from "next";
import { loadDocument } from "@/lib/data";
import { resolveLocale } from "@/lib/locale";
import { ScrollRegion } from "@/components/ScrollRegion";

export async function generateMetadata({ params }: PageProps<"/[lang]/about">): Promise<Metadata> {
  return { title: (await resolveLocale(params)).dict.about.title };
}

export default async function About({ params }: PageProps<"/[lang]/about">) {
  const { dict } = await resolveLocale(params);
  const t = dict.about;
  const meta = (await loadDocument("meta")).data;
  const prose: [string, string][] = [
    [t.whatTitle, t.what],
    [t.levelsTitle, t.levels],
    [t.timeTitle, t.time],
    [t.matchingTitle, t.matching],
  ];
  return (
    <article className="space-y-6">
      <h1 className="text-2xl font-semibold">{t.title}</h1>
      {prose.map(([title, body]) => (
        <section key={title} className="space-y-1">
          <h2 className="text-lg font-semibold">{title}</h2>
          <p className="max-w-prose">{body}</p>
        </section>
      ))}
      <section className="space-y-2">
        <h2 className="text-lg font-semibold">{t.sourcesTitle}</h2>
        <ScrollRegion label={t.sourcesTitle}>
          <table className="data">
            <thead>
              <tr>
                <th scope="col">{t.sourceFile}</th>
                <th scope="col">{dict.common.effectiveFrom}</th>
                <th scope="col">{t.published}</th>
                <th scope="col">{t.basis}</th>
              </tr>
            </thead>
            <tbody>
              {meta.sources.map((s) => (
                <tr key={s.source_file}>
                  <td>{s.source_file}</td>
                  <td className="tabular-nums whitespace-nowrap">{s.effective_from}</td>
                  <td>{s.published_label}</td>
                  <td>{s.effective_basis}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollRegion>
      </section>
      <section className="space-y-1">
        <h2 className="text-lg font-semibold">{t.attribution}</h2>
        <ul className="list-disc ps-5">
          {meta.attribution.map((a) => (
            <li key={a}>{a}</li>
          ))}
        </ul>
      </section>
      <section className="space-y-1">
        <h2 className="text-lg font-semibold">{t.disclaimer}</h2>
        <p className="max-w-prose">{meta.disclaimer}</p>
      </section>
    </article>
  );
}
