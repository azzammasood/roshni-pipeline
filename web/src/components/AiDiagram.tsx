// Ask Roshni's architecture as one drawing: the visitor's browser, the Cloudflare edge, the model
// providers and the daily GitHub publish, with every tool and model shown by its mark. Numbered
// badges on the wires match the ordered list under the drawing, which is the text alternative
// (the SVG itself is aria-hidden). Marks come from Simple Icons via ToolLogo; tools without one get
// letters, never a lookalike. Wires carry a moving dash under prefers-reduced-motion:
// no-preference (motion.css, "AI diagram").
import type { Dictionary } from "@/i18n/dictionaries";
import { num } from "@/lib/format";
import { logoMark } from "./ToolLogo";
import { ScrollRegion } from "./ScrollRegion";

type D = Dictionary["aiDiagram"];
type Kind = "code" | "model" | "data";

function Node({
  x,
  y,
  w,
  logo,
  name,
  role,
  kind = "code",
}: {
  x: number;
  y: number;
  w: number;
  logo: string;
  name: string;
  role: string;
  kind?: Kind;
}) {
  const m = logoMark(logo);
  const h = 54;
  return (
    <g className={`aid-node aid-${kind}`}>
      <rect x={x} y={y} width={w} height={h} rx={3} className="aid-box" />
      <rect x={x + 9} y={y + 10} width={34} height={34} rx={4} className="aid-tile" />
      {"path" in m ? (
        <svg x={x + 15} y={y + 16} width={22} height={22} viewBox="0 0 24 24">
          <path d={m.path} fill={m.color} />
        </svg>
      ) : (
        <text x={x + 26} y={y + 31} textAnchor="middle" dominantBaseline="middle" className="aid-letters">
          {m.letters}
        </text>
      )}
      <text x={x + 52} y={y + 23} className="aid-name">
        {name}
      </text>
      <text x={x + 52} y={y + 41} className="aid-role">
        {role}
      </text>
    </g>
  );
}

function Badge({ x, y, n, locale }: { x: number; y: number; n: number; locale: string }) {
  return (
    <g className="aid-badge">
      <circle cx={x} cy={y} r={11} />
      <text x={x} y={y + 1} textAnchor="middle" dominantBaseline="middle">
        {num(n, locale)}
      </text>
    </g>
  );
}

function Zone({ x, y, w, h, title }: { x: number; y: number; w: number; h: number; title: string }) {
  return (
    <g className="aid-zone">
      <rect x={x} y={y} width={w} height={h} rx={6} />
      <text x={x + w / 2} y={y + 22} textAnchor="middle">
        {title}
      </text>
    </g>
  );
}

const Wire = ({ d, dashed = false }: { d: string; dashed?: boolean }) => (
  <path d={d} className={`aid-wire${dashed ? " is-dashed" : ""}`} markerEnd="url(#aid-arrow)" />
);

export function AiDiagram({ t, locale }: { t: D; locale: string }) {
  const r = t.roles;
  return (
    <figure className="space-y-4">
      <ScrollRegion label={t.title}>
        <div dir="ltr" className="aid-wrap">
          <svg viewBox="0 0 1000 640" className="aid" aria-hidden="true" focusable="false" direction="ltr">
            <defs>
              <marker id="aid-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
                <path d="M0 0 L10 5 L0 10 z" className="aid-head" />
              </marker>
            </defs>

            <Zone x={20} y={30} w={390} h={370} title={t.zones.browser} />
            <Zone x={450} y={30} w={200} h={370} title={t.zones.edge} />
            <Zone x={680} y={30} w={300} h={370} title={t.zones.models} />
            <Zone x={20} y={440} w={960} h={185} title={t.zones.github} />

            {/* Browser */}
            <Node x={40} y={70} w={350} logo="Next.js" name="Ask page · Next.js" role={r.page} />
            <Node x={40} y={150} w={165} logo="Schedule engine" name="dark-now" role={r.schedule} />
            <Node x={225} y={150} w={165} logo="Intent router" name="intent router" role={r.router} />
            <Node x={40} y={240} w={350} logo="SQL guard" name="SQL guard · json_serialize_sql" role={r.guard} />
            <Node x={40} y={320} w={350} logo="DuckDB-WASM" name="DuckDB-WASM" role={r.run} />

            {/* Edge */}
            <Node x={462} y={90} w={176} logo="Cloudflare Workers" name="Worker" role={r.worker} />
            <Node x={462} y={190} w={176} logo="Durable Objects" name="Durable Object" role={r.limits} />
            <Node x={462} y={300} w={176} logo="Prose check" name="prose check" role={r.prose} />

            {/* Models */}
            <text x={830} y={80} textAnchor="middle" className="aid-sub">
              Groq
            </text>
            <Node x={695} y={88} w={270} logo="Llama Prompt Guard 2" name="Llama Prompt Guard 2 86M" role={r.screen} kind="model" />
            <Node x={695} y={152} w={270} logo="Qwen3.8 27B" name="Qwen3.8 27B" role={r.plan} kind="model" />
            <Node x={695} y={216} w={270} logo="gpt-oss-120b" name="gpt-oss-120b · 20b" role={r.fallback} kind="model" />
            <text x={697} y={296} className="aid-sub">
              OpenRouter
            </text>
            <Node x={695} y={304} w={132} logo="Gemma 4 31B" name="Gemma 4" role={r.last} kind="model" />
            <Node x={833} y={304} w={132} logo="Nemotron 3 Ultra" name="Nemotron 3" role={r.last} kind="model" />

            {/* GitHub */}
            <Node x={40} y={485} w={210} logo="GitHub Actions" name="GitHub Actions" role={r.actions} kind="data" />
            <Node x={280} y={485} w={210} logo="DuckDB" name="dbt · DuckDB" role={r.warehouse} kind="data" />
            <Node x={520} y={485} w={210} logo="GitHub Pages" name="GitHub Pages" role={r.pages} kind="data" />
            <Node x={760} y={485} w={205} logo="YAML" name="evals" role={r.evals} kind="data" />

            {/* 1 question -> router; router -> schedule engine (personal) */}
            <Wire d="M307 124 L307 150" />
            <Badge x={322} y={137} n={1} locale={locale} />
            <Wire d="M225 177 L205 177" />
            {/* 2 router -> Worker */}
            <Wire d="M390 177 L404 177 L404 112 L462 112" />
            <Badge x={449} y={112} n={2} locale={locale} />
            {/* 3 Worker -> Prompt Guard; 4 Worker -> Qwen (plan); fallbacks */}
            <Wire d="M638 108 L695 112" />
            <Badge x={666} y={98} n={3} locale={locale} />
            <Wire d="M638 128 L695 176" />
            <Badge x={662} y={160} n={4} locale={locale} />
            <Wire d="M830 206 L830 216" dashed />
            <Wire d="M830 270 L830 304" dashed />
            <text x={838} y={292} className="aid-flow">
              {t.flows.busy}
            </text>
            {/* Worker <-> Durable Object */}
            <Wire d="M550 144 L550 190" />
            {/* 5 SQL back to the browser guard */}
            <Wire d="M462 134 L420 134 L420 262 L390 262" />
            <Badge x={420} y={210} n={5} locale={locale} />
            {/* 6 guard -> run; data files from Pages */}
            <Wire d="M215 294 L215 320" />
            <Badge x={232} y={307} n={6} locale={locale} />
            <Wire d="M625 485 L625 420 L130 420 L130 374" />
            <text x={380} y={414} textAnchor="middle" className="aid-flow">
              Parquet · JSON
            </text>
            {/* 7 result facts -> Worker; the model narrates; the check runs */}
            <Wire d="M390 347 L462 330" />
            <Badge x={425} y={350} n={7} locale={locale} />
            <Wire d="M695 190 L638 318" dashed />
            {/* 8 checked answer back to the page */}
            <Wire d="M462 345 L436 345 L436 92 L390 92" />
            <Badge x={436} y={76} n={8} locale={locale} />

            {/* GitHub: daily build, Monday evals scoring the main model */}
            <Wire d="M250 512 L280 512" />
            <Wire d="M490 512 L520 512" />
            <Wire d="M145 539 L145 600 L862 600 L862 539" />
            <text x={500} y={594} textAnchor="middle" className="aid-flow">
              {t.flows.mondays}
            </text>
            <Wire d="M900 485 L900 358" dashed />
            <Badge x={900} y={430} n={9} locale={locale} />
          </svg>
        </div>
      </ScrollRegion>
      <figcaption className="space-y-3">
        <ol className="aid-steps">
          {t.steps.map((s, i) => (
            <li key={s}>
              <span className="aid-step-num" aria-hidden="true">
                {num(i + 1, locale)}
              </span>
              <span>{s}</span>
            </li>
          ))}
        </ol>
        <ul className="flex flex-wrap gap-x-5 gap-y-1 text-sm" aria-label={t.keyLabel}>
          <li className="flex items-center gap-2">
            <span className="ai-key" aria-hidden="true" />
            {t.keyCode}
          </li>
          <li className="flex items-center gap-2">
            <span className="ai-key ai-key-model" aria-hidden="true" />
            {t.keyModel}
          </li>
          <li className="flex items-center gap-2">
            <span className="ai-key ai-key-data" aria-hidden="true" />
            {t.keyData}
          </li>
        </ul>
      </figcaption>
    </figure>
  );
}
