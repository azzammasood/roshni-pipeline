// One question, end to end, as engine.ask does it (with the SQL run here instead of on a
// server): ask the Worker for a plan, guard it, run it (one corrected try after a guard refusal,
// a DuckDB error or an empty first result), narrate it (placeholders only, checked by the
// Worker), then add caveats, n and the build time in code.
import { factsFrom, render } from "./format";
import { type AskContext, type Db, type Serialize, guard, run, serializeWith } from "./runner";

export type Attempt = { stage: string; model: string; outcome: string; tokens: number; latency_s: number };
export type Remaining = { visitor_today: number; site_today: number };
export type PlanReply = {
  status: "planned" | "refused" | "blocked" | "failed" | "capped" | "used" | "unknown_ticket" | "bad_request" | "error";
  ticket?: string;
  sql?: string;
  reason?: string;
  model?: string;
  attempts?: Attempt[];
  remaining?: Remaining;
  retry_after_s?: number;
  /** Prompt Guard 2 score for the question (first plan only); null when the screen was skipped. */
  guard?: number | null;
  /** True when the Worker planned this as a follow-up to the visitor's earlier question. */
  follow_up?: boolean;
};
export type NarrateReply = { status: "narrated" | "template" | string; text?: string; model?: string; attempts?: Attempt[] };

export interface Api {
  ask(question: string, previous?: string): Promise<PlanReply>;
  replan(ticket: string, kind: "error" | "empty" | "guard", detail: string): Promise<PlanReply>;
  narrate(ticket: string, columns: string[], facts: Record<string, string>): Promise<NarrateReply>;
}

export type Step = "guard" | "plan" | "check" | "run" | "replan" | "narrate";

/** What the browser did, for the trace under "Show the query" (model calls are in attempts). */
export type TraceEvent = { step: "guard" | "run" | "replan"; ok: boolean; ms: number; detail: string };

export type Answer = {
  question: string;
  status: "answered" | "refused" | "blocked" | "failed" | "capped" | "unavailable";
  answer: string;
  narrated: boolean;
  sql: string | null;
  columns: string[];
  rows: string[][];
  truncated: boolean;
  tables: string[];
  caveats: string[];
  n: number;
  reason: string;
  retry_after_s?: number;
  remaining?: Remaining;
  models: string[];
  attempts: Attempt[];
  trace: TraceEvent[];
  ticket?: string;
  guard_score?: number | null;
  follow_up?: boolean;
  /** Set when the answer was prepared by the publish job (its data build time). */
  prepared?: string;
};

const blank = (question: string): Answer => ({
  question, status: "failed", answer: "", narrated: false, sql: null, columns: [], rows: [], truncated: false,
  tables: [], caveats: [], n: 0, reason: "", models: [], attempts: [], trace: [],
});

const ms = (t0: number) => Math.round(performance.now() - t0);

function stop(a: Answer, r: PlanReply): Answer | null {
  a.attempts.push(...(r.attempts ?? []));
  if (r.remaining) a.remaining = r.remaining;
  if (r.status === "planned") {
    if (r.model) a.models.push(r.model);
    return null;
  }
  a.reason = r.reason ?? "";
  if (r.status === "refused" || r.status === "blocked" || r.status === "capped") {
    a.status = r.status;
    a.retry_after_s = r.retry_after_s;
  } else if (r.status === "error") a.status = "unavailable";
  else a.status = "failed";
  return a;
}

export async function askQuestion(
  question: string,
  deps: { api: Api; db: Db; ctx: AskContext; serialize?: Serialize; onStep?: (s: Step) => void; previous?: string },
): Promise<Answer> {
  const { api, db, ctx, onStep = () => {} } = deps;
  const serialize = deps.serialize ?? serializeWith(db);
  const a = blank(question.trim());
  onStep("plan");
  let reply = await api.ask(a.question, deps.previous);
  if (reply.guard !== undefined) a.guard_score = reply.guard;
  if (reply.follow_up) a.follow_up = true;
  if (reply.ticket) a.ticket = reply.ticket;
  const done = stop(a, reply);
  if (done) return done;

  let result: Awaited<ReturnType<typeof run>> | null = null;
  for (const round of [1, 2]) {
    const ticket = reply.ticket!;
    const sql = reply.sql!;
    a.sql = sql;
    onStep("check");
    let t0 = performance.now();
    const verdict = await guard(serialize, sql, ctx);
    a.trace.push({ step: "guard", ok: verdict.ok, ms: ms(t0), detail: verdict.ok ? verdict.tables.join(", ") : verdict.problems.join("; ") });
    let kind: "error" | "empty" | "guard" | null = null;
    let detail = "";
    if (!verdict.ok) {
      kind = "guard";
      detail = verdict.problems.join("; ");
      a.reason = `The query was refused by the SQL guard: ${detail}`;
    } else {
      a.tables = verdict.tables;
      onStep("run");
      try {
        t0 = performance.now();
        result = await run(db, sql, ctx.max_rows);
        a.trace.push({ step: "run", ok: true, ms: ms(t0), detail: `${result.rows.length} rows` });
        if (result.rows.length || round === 2) break;
        kind = "empty";
      } catch (e) {
        detail = String((e as Error).message ?? e).split("\n")[0].slice(0, 300);
        a.trace.push({ step: "run", ok: false, ms: ms(t0), detail });
        a.reason = `Query failed: ${detail}`;
        kind = "error";
      }
    }
    if (round === 2) return a;
    onStep("replan");
    a.trace.push({ step: "replan", ok: true, ms: 0, detail: kind! });
    reply = await api.replan(ticket, kind!, detail);
    const stopped = stop(a, reply);
    if (stopped) return stopped;
    result = null;
  }
  if (!result) return a;

  a.status = "answered";
  a.reason = "";
  a.columns = result.columns;
  a.rows = result.rows;
  a.truncated = result.truncated;
  a.n = result.rows.length;
  const facts = factsFrom(result.columns, result.rows, ctx.max_fact_rows);
  a.answer = render("The query returned {row_count} row(s).", facts);
  if (result.rows.length) {
    onStep("narrate");
    const nr = await api.narrate(reply.ticket!, result.columns, facts);
    a.attempts.push(...(nr.attempts ?? []));
    if (nr.status === "narrated" && nr.text) {
      a.answer = render(nr.text, facts);
      a.narrated = true;
      if (nr.model) a.models.push(nr.model);
    }
  }
  const caveats: string[] = [];
  for (const t of a.tables) for (const c of ctx.tables[t]?.caveats ?? []) if (!caveats.includes(c)) caveats.push(c);
  a.caveats = caveats;
  return a;
}
