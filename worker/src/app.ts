// Ask Roshni API (no Cloudflare imports here, so it runs under plain vitest).
//
//   POST /v1/ask      {question}                      -> guard, plan  (costs one question)
//   POST /v1/replan   {ticket, kind, detail}          -> one corrected plan for that question
//   POST /v1/narrate  {ticket, columns, facts}        -> one checked narration for that question
//   GET  /v1/quota                                    -> questions left today
//
// The browser runs the SQL (DuckDB-WASM over the published Parquet) and its own SQL guard; this
// Worker holds the key, the prompts (fetched from the site's ask/context.json, never taken from
// the browser) and the caps. Numbers in answers come from the browser's query result; the
// narration may only refer to them by placeholder and is checked here before it is returned.
import { type Attempt, type ChainDeps, CONFIG, complete, guardScore, parseJson, tokens } from "./chain";
import { checkProse, pyColumns } from "./prose";
import { type Admission, MAX_REPLANS, type Msg, type Remaining, type Ticket } from "./quota";

export type Context = {
  bundle_version: number;
  built_at: string | null;
  planner_system: string;
  narrator_system: string;
  feedback: { error: string; empty: string; guard: string };
  max_fact_rows: number;
  max_question_chars: number;
};

/** What the handler needs from the Durable Object (time is the object's own clock). */
export interface QuotaApi {
  admit(visitor: string): Promise<Admission>;
  remaining(visitor: string): Promise<Remaining>;
  addTokens(n: number): Promise<void>;
  putTicket(id: string, t: Ticket): Promise<void>;
  ticket(id: string, visitor: string): Promise<Ticket | null>;
}

export type Deps = {
  quota: QuotaApi;
  chain: ChainDeps;
  context: () => Promise<Context>;
  visitor: string;
  newId: () => string;
  now: () => number;
};

const MAX_BODY = 16_384;
const MAX_SQL = 4_000;
const MAX_DETAIL = 300;
const FACT_KEY = /^(row_count|r\d{1,2}_[a-z0-9_]{1,60})$/;

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json; charset=utf-8" } });

const publicAttempts = (atts: Attempt[], stage: string) =>
  atts.map((a) => ({ stage, model: `${a.provider}/${a.model}`, outcome: a.outcome, tokens: a.tokens_in + a.tokens_out, latency_s: a.latency_s }));

/** Light checks on the planner's reply; the browser's DuckDB-based guard does the full check. */
export function planProblems(text: string): string[] {
  let plan: Record<string, unknown>;
  try {
    plan = parseJson(text);
  } catch {
    return ["reply is not JSON"];
  }
  if (!plan.answerable) return [];
  const sql = typeof plan.sql === "string" ? plan.sql.trim().replace(/;\s*$/, "") : "";
  if (!sql) return ["answerable but no sql"];
  if (sql.length > MAX_SQL) return ["sql too long"];
  if (!/^(select|with)\b/i.test(sql)) return ["only SELECT queries are allowed"];
  if (sql.includes(";")) return ["expected exactly one statement"];
  return [];
}

async function readBody(req: Request): Promise<Record<string, unknown> | null> {
  const text = await req.text();
  if (text.length > MAX_BODY) return null;
  try {
    const v = JSON.parse(text);
    return v && typeof v === "object" && !Array.isArray(v) ? v : null;
  } catch {
    return null;
  }
}

/** Plan (or re-plan) from the conversation so far; records tokens; answers the browser. */
async function plan(deps: Deps, ctx: Context, history: Msg[], ticketId: string, t: Ticket, stage: string) {
  const comp = await complete([{ role: "system", content: ctx.planner_system }, ...history], planProblems, deps.chain, true);
  await deps.quota.addTokens(tokens(comp.attempts));
  const attempts = publicAttempts(comp.attempts, stage);
  if (comp.text === null) return json(200, { status: "failed", reason: "No model produced a valid query.", attempts });
  const p = parseJson(comp.text);
  if (!p.answerable) return json(200, { status: "refused", reason: String(p.reason ?? "") || "Not answerable from Roshni.", attempts });
  const sql = String(p.sql).trim().replace(/;\s*$/, "");
  t.history = [...history, { role: "assistant", content: comp.text }];
  await deps.quota.putTicket(ticketId, t);
  return json(200, {
    status: "planned",
    ticket: ticketId,
    sql,
    reason: String(p.reason ?? ""),
    model: comp.model,
    replans_left: MAX_REPLANS - t.replans,
    attempts,
  });
}

export async function handle(req: Request, deps: Deps): Promise<Response> {
  const path = new URL(req.url).pathname.replace(/\/+$/, "");

  if (req.method === "GET" && path === "/v1/quota") {
    return json(200, { status: "ok", remaining: await deps.quota.remaining(deps.visitor) });
  }
  if (req.method !== "POST") return json(404, { status: "not_found" });
  const body = await readBody(req);
  if (!body) return json(400, { status: "bad_request", reason: "Send a JSON object under 16 KB." });
  const ctx = await deps.context();

  if (path === "/v1/ask") {
    const question = typeof body.question === "string" ? body.question.trim() : "";
    if (!question || question.length > ctx.max_question_chars)
      return json(400, { status: "bad_request", reason: `Questions must be 1 to ${ctx.max_question_chars} characters.` });
    const adm = await deps.quota.admit(deps.visitor);
    if (!adm.ok) return json(429, { status: "capped", reason: adm.reason, retry_after_s: adm.retry_after_s, remaining: adm.remaining });
    const score = await guardScore(question, deps.chain);
    if (score !== null && score >= CONFIG.guard.threshold)
      return json(200, { status: "blocked", reason: "The question looks like a prompt-injection attempt.", remaining: adm.remaining });
    const id = deps.newId();
    const t: Ticket = { visitor: deps.visitor, question, created: deps.now(), replans: 0, narrated: false, history: [] };
    const res = await plan(deps, ctx, [{ role: "user", content: question }], id, t, "plan1");
    const out = (await res.json()) as Record<string, unknown>;
    return json(200, { ...out, remaining: adm.remaining, guard: score });
  }

  const id = typeof body.ticket === "string" ? body.ticket : "";
  const t = id ? await deps.quota.ticket(id, deps.visitor) : null;
  if (!t) return json(404, { status: "unknown_ticket", reason: "Ask the question again." });

  if (path === "/v1/replan") {
    if (t.replans >= MAX_REPLANS) return json(409, { status: "used", reason: "This question already had its corrected try." });
    const kind = body.kind;
    if (kind !== "error" && kind !== "empty" && kind !== "guard") return json(400, { status: "bad_request", reason: "kind is error, empty or guard." });
    const detail = String(body.detail ?? "").replace(/\s+/g, " ").slice(0, MAX_DETAIL);
    const feedback = ctx.feedback[kind].replace("{err}", detail).replace("{problems}", detail);
    t.replans++;
    await deps.quota.putTicket(id, t);
    return plan(deps, ctx, [...t.history, { role: "user", content: feedback }], id, t, "plan2");
  }

  if (path === "/v1/narrate") {
    if (t.narrated) return json(409, { status: "used", reason: "This answer was already narrated." });
    const columns = Array.isArray(body.columns) ? body.columns.map(String).slice(0, 40) : [];
    const raw = body.facts && typeof body.facts === "object" ? (body.facts as Record<string, unknown>) : {};
    const facts: Record<string, string> = {};
    for (const [k, v] of Object.entries(raw).slice(0, 1 + ctx.max_fact_rows * 40)) {
      if (!FACT_KEY.test(k)) return json(400, { status: "bad_request", reason: `bad fact id ${k.slice(0, 40)}` });
      facts[k] = String(v).slice(0, 200);
    }
    if (!("row_count" in facts)) return json(400, { status: "bad_request", reason: "facts need row_count" });
    t.narrated = true;
    await deps.quota.putTicket(id, t);
    const listing = Object.entries(facts).map(([k, v]) => `${k} = ${v}`).join("\n");
    const comp = await complete(
      [
        { role: "system", content: ctx.narrator_system },
        { role: "user", content: `Question: ${t.question}\nColumns: ${pyColumns(columns)}\nFacts (id = value; write the id, never the value):\n${listing}` },
      ],
      (text) => checkProse(text, facts, t.question),
      deps.chain,
    );
    await deps.quota.addTokens(tokens(comp.attempts));
    const attempts = publicAttempts(comp.attempts, "narrate");
    if (comp.text === null) return json(200, { status: "template", attempts });
    return json(200, { status: "narrated", text: comp.text, model: comp.model, attempts });
  }

  return json(404, { status: "not_found" });
}

let cached: { at: number; ctx: Context; url: string } | null = null;
const CONTEXT_TTL_MS = 10 * 60_000;

/** The site's ask/context.json, cached per isolate for ten minutes. */
export async function loadContext(url: string, fetcher: typeof fetch = fetch, now = Date.now()): Promise<Context> {
  if (cached && cached.url === url && now - cached.at < CONTEXT_TTL_MS) return cached.ctx;
  const resp = await fetcher(url, { headers: { "User-Agent": "roshni-ask-worker" } });
  if (!resp.ok) throw new Error(`context ${resp.status}`);
  const ctx = (await resp.json()) as Context;
  if (ctx.bundle_version !== 1 || !ctx.planner_system) throw new Error("unexpected context");
  cached = { at: now, ctx, url };
  return ctx;
}
