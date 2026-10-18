import type { Metadata } from "next";
import { BulbArt } from "@/components/Bulb";
import { StoryLine } from "@/components/maker/StoryLine";
import { fill } from "@/i18n/dictionaries";
import { resolveLocale } from "@/lib/locale";
import { MAKER, makerName } from "@/lib/maker";

export async function generateMetadata({ params }: PageProps<"/[lang]/maker">): Promise<Metadata> {
  const { dict } = await resolveLocale(params);
  return { title: dict.maker.title };
}

export default async function Maker({ params }: PageProps<"/[lang]/maker">) {
  const { locale, dict } = await resolveLocale(params);
  const t = dict.maker;
  const name = makerName(locale);
  const rows: [string, React.ReactNode][] = [
    [t.rowRole, fill(t.role, { clouds: MAKER.clouds }, locale)],
    [t.rowBased, t.based],
    [t.rowExperience, t.experience],
    [t.rowRecent, fill(t.recent, { company: MAKER.company }, locale)],
    [t.rowStudied, fill(t.studied, { university: MAKER.university }, locale)],
    [
      t.rowTools,
      <ul key="tools" className="flex flex-wrap gap-1.5" dir="ltr">
        {MAKER.skills.map((s) => (
          <li key={s} className="chip">
            {s}
          </li>
        ))}
      </ul>,
    ],
    [t.rowOff, fill(t.off, { platform: MAKER.platform }, locale)],
  ];
  const links: [string, string, string][] = [
    [t.linkPortfolio, MAKER.links.portfolio, "azzammasood.github.io"],
    [t.linkGithub, MAKER.links.github, "github.com/azzammasood"],
    [t.linkLinkedin, MAKER.links.linkedin, "linkedin.com/in/azzammasood"],
    [t.linkCode, MAKER.links.code, "roshni-pipeline"],
  ];

  return (
    <article className="space-y-12">
      <section aria-labelledby="night" className="maker-night">
        <div className="maker-sky" aria-hidden="true">
          {Array.from({ length: 28 }, (_, i) => (
            <span
              key={i}
              className="maker-star"
              style={{ "--s": i, insetInlineStart: `${(i * 37) % 97}%`, top: `${(i * 53) % 89}%` } as React.CSSProperties}
            />
          ))}
        </div>
        <header className="relative space-y-4 max-w-3xl">
          <svg viewBox="0 0 40 48" className="maker-bulb h-20 w-20" aria-hidden="true">
            <BulbArt />
          </svg>
          <p className="kicker">{t.kicker}</p>
          <h1 id="night" className="headline text-5xl sm:text-7xl">
            {t.title}
          </h1>
          <p className="headline text-xl sm:text-2xl">{t.intro}</p>
        </header>
        <StoryLine chapters={t.chapters} finale={t.finale} />
      </section>

      <section aria-labelledby="card" className="maker-card">
        <div className="maker-card-head">
          <p className="kicker">{t.cardKicker}</p>
          <h2 id="card" className="headline text-4xl sm:text-5xl">
            {name}
          </h2>
          <p className="text-lg">{t.title2}</p>
        </div>
        <blockquote className="maker-quote" lang="en" dir="ltr">
          “{MAKER.quote}”
        </blockquote>
        <dl className="maker-rows">
          {rows.map(([label, value]) => (
            <div key={label} className="maker-row">
              <dt className="kicker">{label}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
        <div className="maker-links">
          <p className="headline text-2xl">{t.ctaTitle}</p>
          <ul className="grid gap-2 sm:grid-cols-2">
            {links.map(([label, href, shown]) => (
              <li key={href}>
                <a href={href} className="maker-link" rel="noopener noreferrer" target="_blank">
                  <span className="kicker">{label}</span>
                  <span className="font-mono text-sm" dir="ltr">
                    {shown}
                  </span>
                  <span aria-hidden="true" className="maker-arrow rtl:-scale-x-100">
                    →
                  </span>
                </a>
              </li>
            ))}
          </ul>
        </div>
      </section>
    </article>
  );
}
