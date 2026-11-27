// "The AI layer" on the architecture page: the three places a language model does work (a
// visitor's question, the weekly evals, parser healing), drawn as power lines. Model steps are
// dark tiles; each is followed by a light code step that checks it. Real HTML (ordered lists),
// so the diagram is its own text alternative. Scores come from the export (health.ask_eval and
// health.healing.eval), never typed in.
import type { Locale } from "@/i18n/config";
import { type Dictionary, fill } from "@/i18n/dictionaries";
import type { Health } from "@/types/v1";
import { ToolLogo } from "./ToolLogo";

type Kind = "model" | "code";
type Station = { key: string; kind: Kind; files: string[] };
type Lane = { key: "ask" | "evals" | "heal"; tools: string[]; stations: Station[] };

// File paths and tool names stay in Latin script in every language.
const LANES: Lane[] = [
  {
    key: "ask",
    tools: ["Cloudflare Workers", "Durable Objects", "Groq", "OpenRouter", "DuckDB-WASM", "WebAssembly"],
    stations: [
      { key: "gate", kind: "code", files: ["worker/src/quota.ts"] },
      { key: "screen", kind: "model", files: ["config/llm.yml"] },
      { key: "plan", kind: "model", files: ["config/semantic_layer.yml", "worker/src/chain.ts"] },
      { key: "guard", kind: "code", files: ["web/src/lib/ask/guard.ts"] },
      { key: "run", kind: "code", files: ["web/src/lib/ask/duckdb.ts"] },
      { key: "narrate", kind: "model", files: ["worker/src/app.ts"] },
      { key: "check", kind: "code", files: ["worker/src/prose.ts"] },
    ],
  },
  {
    key: "evals",
    tools: ["GitHub Actions", "Groq", "YAML", "pytest"],
    stations: [
      { key: "golden", kind: "code", files: ["config/ask_golden.yml"] },
      { key: "answer", kind: "model", files: ["src/roshni/ask/evaluate.py"] },
      { key: "chaos", kind: "model", files: ["src/roshni/heal/simulate.py"] },
      { key: "score", kind: "code", files: ["src/roshni/evalrecord.py", "evals/"] },
      { key: "alert", kind: "code", files: [".github/workflows/publish.yml"] },
    ],
  },
  {
    key: "heal",
    tools: ["Groq", "openpyxl", "YAML", "git"],
    stations: [
      { key: "drift", kind: "code", files: ["src/roshni/heal/headers.py"] },
      { key: "name", kind: "model", files: ["src/roshni/heal/headers.py"] },
      { key: "gate", kind: "code", files: ["src/roshni/heal/headers.py"] },
      { key: "learn", kind: "code", files: ["config/parser_aliases.yml"] },
    ],
  },
];

type Text = { title: string; body: string };
type LaneText = Text & { when: string; stations: Record<string, Text & { stops: string }> };

export function AiLayer({ dict, locale, health }: { dict: Dictionary; locale: Locale; health: Health }) {
  const t = dict.architecture.ai;
  const lanes = t.lanes as Record<Lane["key"], LaneText>;
  const base = process.env.NEXT_PUBLIC_BASE_PATH ?? "";

  const askPoint = health.ask_eval?.history.at(-1) ?? null;
  const healPoint = health.healing?.eval?.history?.at(-1) ?? null;
  const scores: Partial<Record<Lane["key"], string>> = {};
  if (askPoint || healPoint) {
    scores.evals = [
      askPoint ? fill(t.scoreAsk, { passed: askPoint.passed, total: askPoint.total }, locale) : null,
      healPoint ? fill(t.scoreHeal, { passed: healPoint.passed, total: healPoint.total }, locale) : null,
    ]
      .filter(Boolean)
      .join(" · ");
  }
  const aliases = health.healing?.aliases.length ?? null;
  if (aliases !== null) scores.heal = fill(t.scoreAliases, { n: aliases }, locale);

  return (
    <section aria-labelledby="ai" className="rule pt-4 space-y-6">
      <div className="space-y-2 max-w-4xl">
        <p className="kicker">{t.kicker}</p>
        <h2 id="ai" className="headline text-3xl">
          {t.title}
        </h2>
        <p className="max-w-prose">{t.intro}</p>
        <ul className="flex flex-wrap gap-x-5 gap-y-1 text-sm pt-1" aria-label={t.legendLabel}>
          <li className="flex items-center gap-2">
            <span className="ai-key ai-key-model" aria-hidden="true" />
            {t.legendModel}
          </li>
          <li className="flex items-center gap-2">
            <span className="ai-key ai-key-code" aria-hidden="true" />
            {t.legendCode}
          </li>
        </ul>
      </div>

      {LANES.map((lane, li) => {
        const lt = lanes[lane.key];
        return (
          <section key={lane.key} aria-labelledby={`ai-${lane.key}`} className="ai-lane">
            <header className="ai-lane-head">
              <span className="arch-num" dir="ltr">
                {String.fromCharCode(65 + li)}
              </span>
              <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1">
                <h3 id={`ai-${lane.key}`} className="headline text-2xl">
                  {lt.title}
                </h3>
                <p className="text-sm text-muted">{lt.when}</p>
              </div>
              <p className="text-sm max-w-prose mt-1">{lt.body}</p>
              {scores[lane.key] && (
                <p className="mt-2 text-sm">
                  <a href={`${base}/${locale}/health/#${lane.key === "heal" ? "healing" : "ask"}`} className="ai-score">
                    {scores[lane.key]} <span aria-hidden="true" className="rtl:-scale-x-100 inline-block">→</span>
                  </a>
                </p>
              )}
            </header>
            <ol className="ai-line" style={{ "--n": lane.stations.length } as React.CSSProperties}>
              {lane.stations.map((s, i) => {
                const st = lt.stations[s.key];
                return (
                  <li key={s.key} className={`ai-node ai-${s.kind}`} style={{ "--i": i } as React.CSSProperties}>
                    <span className="ai-lamp" aria-hidden="true" />
                    <div className="ai-card">
                      <p className="ai-kind">{s.kind === "model" ? t.kindModel : t.kindCode}</p>
                      <h4 className="ai-title headline text-xl">{st.title}</h4>
                      <p className="ai-body text-sm">{st.body}</p>
                      <p className="ai-stops text-sm">
                        <span className="font-semibold">{t.stopsLabel}</span> {st.stops}
                      </p>
                      <p className="ai-files" dir="ltr">
                        {s.files.map((f) => (
                          <code key={f}>{f}</code>
                        ))}
                      </p>
                    </div>
                  </li>
                );
              })}
            </ol>
            <ul className="flex flex-wrap gap-1.5 ps-1" aria-label={dict.architecture.toolsLabel} dir="ltr">
              {lane.tools.map((tool) => (
                <li key={tool} className="arch-tool gap-1.5">
                  <ToolLogo name={tool} size="sm" />
                  {tool}
                </li>
              ))}
            </ul>
          </section>
        );
      })}
      <p className="text-sm text-muted max-w-prose">{t.note}</p>
    </section>
  );
}
