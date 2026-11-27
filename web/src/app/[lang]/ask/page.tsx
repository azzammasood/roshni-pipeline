import type { Metadata } from "next";
import { AiDiagram } from "@/components/AiDiagram";
import { AskPanel } from "@/components/AskPanel";
import { ToolLogo } from "@/components/ToolLogo";
import { num } from "@/lib/format";
import { resolveLocale } from "@/lib/locale";

export async function generateMetadata({ params }: PageProps<"/[lang]/ask">): Promise<Metadata> {
  return { title: (await resolveLocale(params)).dict.nav.ask };
}

// What runs at each stage of "How an answer is made" (tool and model names stay in Latin script).
const HOW_TECH: string[][] = [
  ["Intent router", "Schedule engine"],
  ["Cloudflare Workers", "Durable Objects"],
  ["Llama Prompt Guard 2", "Groq"],
  ["Qwen3.8 27B", "gpt-oss-120b", "gpt-oss-20b", "OpenRouter"],
  ["DuckDB", "sqlglot"],
  ["DuckDB-WASM", "WebAssembly", "Parquet", "JSON"],
  ["Qwen3.8 27B", "Prose check"],
];
const MODEL_STAGES = new Set([2, 3, 6]);

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
      <AskPanel locale={locale} t={t} lt={{ lead: dict.lead, common: dict.common, sources: dict.sources }} />
      <section aria-labelledby="ask-how" className="rule pt-4 space-y-5">
        <h2 id="ask-how" className="headline text-3xl">
          {t.howTitle}
        </h2>
        <p className="max-w-prose">{t.howIntro}</p>
        <AiDiagram t={dict.aiDiagram} locale={locale} />
        <ol className="ask-how">
          {t.how.map((s, i) => (
            <li key={s.title} className={MODEL_STAGES.has(i) ? "is-model" : undefined}>
              <span className="ask-how-num" aria-hidden="true">
                {num(i + 1, locale)}
              </span>
              <div>
                <h3 className="headline text-xl">{s.title}</h3>
                <p>{s.body}</p>
                <ul className="flex flex-wrap gap-1.5 mt-2" aria-label={dict.architecture.toolsLabel} dir="ltr">
                  {HOW_TECH[i].map((tool) => (
                    <li key={tool} className="arch-tool gap-1.5">
                      <ToolLogo name={tool} size="sm" />
                      {tool}
                    </li>
                  ))}
                </ul>
              </div>
            </li>
          ))}
        </ol>
      </section>
    </article>
  );
}
