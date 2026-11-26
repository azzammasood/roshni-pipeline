import type { Metadata } from "next";
import { AskPanel } from "@/components/AskPanel";
import { num } from "@/lib/format";
import { resolveLocale } from "@/lib/locale";

export async function generateMetadata({ params }: PageProps<"/[lang]/ask">): Promise<Metadata> {
  return { title: (await resolveLocale(params)).dict.nav.ask };
}

/** Ask Roshni: questions answered by a query the visitor's browser runs on the published data. */
export default async function Ask({ params }: PageProps<"/[lang]/ask">) {
  const { locale, dict } = await resolveLocale(params);
  const t = dict.ask;
  return (
    <article className="space-y-10">
      <header className="space-y-3 max-w-4xl">
        <p className="kicker">{t.kicker}</p>
        <h1 className="headline text-4xl sm:text-6xl">{t.title}</h1>
        <p className="text-lg max-w-prose">{t.intro}</p>
      </header>
      <AskPanel locale={locale} t={t} />
      <section aria-labelledby="ask-how" className="rule pt-4 space-y-5">
        <h2 id="ask-how" className="headline text-3xl">
          {t.howTitle}
        </h2>
        <ol className="ask-how">
          {[t.how1, t.how2, t.how3, t.how4, t.how5].map((s, i) => (
            <li key={s}>
              <span className="ask-how-num" aria-hidden="true">
                {num(i + 1, locale)}
              </span>
              <p>{s}</p>
            </li>
          ))}
        </ol>
      </section>
    </article>
  );
}
