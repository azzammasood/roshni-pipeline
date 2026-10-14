import type { Metadata } from "next";
import { loadDocument } from "@/lib/data";
import { num } from "@/lib/format";
import { resolveLocale } from "@/lib/locale";
import { Stamp } from "@/components/Clock";

export async function generateMetadata({ params }: PageProps<"/[lang]/architecture">): Promise<Metadata> {
  return { title: (await resolveLocale(params)).dict.architecture.title };
}

/** Public repository the daily publish job writes the site to. */
const SITE_REPO = "https://github.com/azzammasood/roshni-site";

// Tool names are proper nouns and stay in Latin script in every language; the words around them
// come from the dictionaries. Order follows the data: sources -> page.
const STAGES = [
  { key: "sources", tools: ["robots.txt", "httpx", "Beautiful Soup", "RSS"] },
  { key: "snapshot", tools: ["GitHub Actions", "SHA-256", "ETag / If-Modified-Since", "git"] },
  { key: "parse", tools: ["Docker", "poppler pdftotext", "openpyxl", "pydantic", "Parquet", "Great Expectations"] },
  { key: "warehouse", tools: ["dbt", "DuckDB", "Databricks"] },
  { key: "resolve", tools: ["RapidFuzz", "OpenRouter", "Claude"] },
  { key: "publish", tools: ["JSON Schema", "Next.js", "React", "TypeScript", "Tailwind CSS", "GitHub Pages"] },
] as const;

const RUNNERS = ["GitHub Actions", "Apache Airflow", "Docker Compose", "Typer CLI", "uv"];
const CHECKS = ["pytest", "ruff", "pre-commit", "dbt tests", "Great Expectations", "Vitest", "axe-core", "ESLint"];

export default async function Architecture({ params }: PageProps<"/[lang]/architecture">) {
  const { locale, dict } = await resolveLocale(params);
  const t = dict.architecture;
  const meta = await loadDocument("meta");
  const feeders = (await loadDocument("feeders")).data.filter((f) => f.has_schedule).length;
  const national = (await loadDocument("national")).data.series.length;
  const shutdowns = (await loadDocument("planned_shutdowns")).data.length;
  const news = (await loadDocument("news")).data.length;
  const n = (v: number) => num(v, locale);
  const stats: [string, string][] = [
    [n(meta.data.sources.length), t.statSources],
    [n(feeders), t.statFeeders],
    [n(shutdowns), t.statShutdowns],
    [n(national), t.statNational],
    [n(news), t.statNews],
  ];
  const stages = t.stages as Record<(typeof STAGES)[number]["key"], { title: string; body: string }>;

  return (
    <article className="space-y-12">
      <header className="space-y-3 max-w-4xl">
        <p className="kicker">{t.kicker}</p>
        <h1 className="headline text-4xl sm:text-6xl">{t.title}</h1>
        <p className="text-lg max-w-prose">{t.intro}</p>
      </header>

      <section aria-labelledby="flow" className="space-y-6">
        <div className="rule pt-4 flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1">
          <h2 id="flow" className="headline text-3xl">
            {t.flowTitle}
          </h2>
          <p className="text-sm text-muted">{t.flowHint}</p>
        </div>
        <ol className="arch-flow" style={{ "--n": STAGES.length } as React.CSSProperties}>
          {STAGES.map((s, i) => (
            <li
              key={s.key}
              className="arch-stage arch-reveal"
              style={{ "--i": i } as React.CSSProperties}
            >
              <span className="arch-num" dir="ltr">
                {String(i + 1).padStart(2, "0")}
              </span>
              <span className="arch-lamp" aria-hidden="true" />
              <h3 className="headline text-2xl pe-6">{stages[s.key].title}</h3>
              <p className="mt-1 text-sm">{stages[s.key].body}</p>
              <ul className="mt-3 flex flex-wrap gap-1.5" aria-label={t.toolsLabel} dir="ltr">
                {s.tools.map((tool) => (
                  <li key={tool} className="arch-tool">
                    {tool}
                  </li>
                ))}
              </ul>
            </li>
          ))}
        </ol>
      </section>

      <div className="grid gap-8 md:grid-cols-2">
        <section aria-labelledby="runs" className="rule pt-4 space-y-2">
          <h2 id="runs" className="headline text-2xl">
            {t.runsTitle}
          </h2>
          <p className="text-sm max-w-prose">{t.runs}</p>
          <ul className="flex flex-wrap gap-1.5" aria-label={t.toolsLabel} dir="ltr">
            {RUNNERS.map((tool) => (
              <li key={tool} className="arch-tool">
                {tool}
              </li>
            ))}
          </ul>
        </section>
        <section aria-labelledby="checks" className="rule pt-4 space-y-2">
          <h2 id="checks" className="headline text-2xl">
            {t.checksTitle}
          </h2>
          <p className="text-sm max-w-prose">{t.checks}</p>
          <ul className="flex flex-wrap gap-1.5" aria-label={t.toolsLabel} dir="ltr">
            {CHECKS.map((tool) => (
              <li key={tool} className="arch-tool">
                {tool}
              </li>
            ))}
          </ul>
        </section>
      </div>

      <section aria-labelledby="today" className="rule pt-4 space-y-4">
        <h2 id="today" className="headline text-2xl">
          {t.todayTitle}
        </h2>
        <dl className="grid grid-cols-2 sm:grid-cols-5 gap-x-6 gap-y-4">
          {stats.map(([value, label]) => (
            <div key={label} className="border-t border-line pt-2 flex flex-col-reverse">
              <dt className="text-sm">{label}</dt>
              <dd className="headline text-4xl tabular-nums">{value}</dd>
            </div>
          ))}
        </dl>
        <p className="text-sm text-muted">
          {t.todayNote} <Stamp iso={meta.last_updated} />
        </p>
      </section>

      <section aria-labelledby="principles" className="rule pt-4 space-y-3">
        <h2 id="principles" className="headline text-2xl">
          {t.principlesTitle}
        </h2>
        <ul className="grid gap-x-8 gap-y-3 sm:grid-cols-2 max-w-5xl">
          {t.principles.map((p) => (
            <li key={p} className="border-s-4 border-wire ps-3 text-sm">
              {p}
            </li>
          ))}
        </ul>
        <p className="text-sm pt-2">
          {t.repo}{" "}
          <a href={SITE_REPO} className="link" rel="noopener noreferrer" target="_blank" dir="ltr">
            github.com/azzammasood/roshni-site
          </a>
        </p>
      </section>
    </article>
  );
}
