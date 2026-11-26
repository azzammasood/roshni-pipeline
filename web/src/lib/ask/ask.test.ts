import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { beforeAll, describe, expect, it } from "vitest";
import parity from "../../../../tests/fixtures/ask_parity.json";
import { type Kind, factsFrom, fmt, render, slug } from "./format";
import { nodeDb } from "./nodeDb.test-helper";
import { type AskContext, type Db, type Serialize, guard, loadTables, run } from "./runner";
import { type Api, type PlanReply, askQuestion } from "./session";

// Allowlist of the real semantic layer (the same lists build into ask/context.json).
const EXPORT = path.join(__dirname, "..", "..", "..", "..", "data", "export", "v1", "ask");
const SEMANTIC = path.join(__dirname, "..", "..", "..", "..", "config", "semantic_layer.yml");

/** Table -> columns from config/semantic_layer.yml without a YAML dependency (two-space keys). */
function allowlist(): AskContext["tables"] {
  const out: AskContext["tables"] = {};
  let table = "";
  let inCols = false;
  for (const line of readFileSync(SEMANTIC, "utf8").split(/\r?\n/)) {
    const t = /^ {2}([a-z0-9_]+):\s*$/.exec(line);
    if (t) {
      table = t[1];
      out[table] = { file: `${table}.parquet`, rows: 0, columns: [], caveats: [] };
      inCols = false;
      continue;
    }
    if (/^ {4}columns:/.test(line)) inCols = !!table;
    else if (/^ {4}\S/.test(line)) inCols = false;
    const c = /^ {6}([a-z0-9_]+):/.exec(line);
    if (inCols && c) out[table].columns.push(c[1]);
  }
  return out;
}

const BLOCKED = ["read_", "glob", "getenv", "pragma", "duckdb_", "current_setting", "query", "sniff_", "parquet_", "iceberg", "delta_", "http", "load", "install", "attach", "copy", "export", "import", "system", "shell", "set_", "sqlite_", "postgres_", "mysql_"];
const CTX: AskContext = { bundle_version: 1, built_at: null, tables: allowlist(), blocked_function_prefixes: BLOCKED, max_rows: 200, max_fact_rows: 10, max_question_chars: 500 };

let db: Db & { register(name: string, bytes: Uint8Array): void };
beforeAll(async () => {
  db = await nodeDb();
}, 60_000);

describe("format matches Python (parity file)", () => {
  for (const c of parity.fmt) {
    it(`fmt(${JSON.stringify(c.value)})`, () => {
      const kind: Kind = c.value === null ? "text" : typeof c.value === "boolean" ? "bool" : c.decimal ? "decimal" : typeof c.value === "number" ? "int" : "text";
      expect(fmt(c.value === null ? null : String(c.value), kind)).toBe(c.shown);
    });
  }
  for (const c of parity.slug) it(`slug(${JSON.stringify(c.text)})`, () => expect(slug(c.text)).toBe(c.slug));
  it("handles exponents and long carries", () => {
    expect(fmt("1e-05", "decimal")).toBe("0.00");
    expect(fmt("9.995", "decimal")).toBe("10.0");
    expect(fmt("-0.004", "decimal")).toBe("0.00");
    expect(fmt("1234567.85", "decimal")).toBe("1,234,567.9");
    expect(fmt("-1234567", "int")).toBe("-1,234,567");
    expect(fmt(String(Date.parse("2026-11-25T18:59:00Z")), "ts")).toBe("2026-11-25 23:59 PKT");
  });
});

// Parse trees from DuckDB's json_serialize_sql (Python's DuckDB; DuckDB-WASM cannot load the
// json extension under Node). The browser serializes with DuckDB-WASM itself.
const TREES = new Map<string, string>(parity.sql.map((c) => [c.sql, c.ast]));
const fromParity: Serialize = async (sql) => {
  const t = TREES.get(sql);
  if (!t) throw new Error(`no parse tree in the parity file for: ${sql}`);
  return t;
};

describe("SQL guard matches Python on every parity case (DuckDB's own parser)", () => {
  for (const c of parity.sql) {
    it(c.sql.slice(0, 90), async () => {
      const v = await guard(fromParity, c.sql, CTX);
      expect({ ok: v.ok, problems: v.problems }).toEqual({ ok: c.ok, problems: c.ok ? [] : expect.any(Array) });
    });
  }
});

describe("runner", () => {
  beforeAll(async () => {
    await db.query(
      "create or replace table mart_ke_ibc_equity as select * from (values " +
        "('IBC - A', 10, 10, 9, 1, 90.0::decimal(5,1)), ('IBC - B', 20, 20, 5, 15, 25.0), ('IBC - C', 3, 3, 0, 3, 0.0)) " +
        "t(ibc, listed_feeders, scheduled_feeders, feeders_12h, feeders_6h, share_12h_pct)",
    );
  });

  it("keeps order, types and exact decimals; caps rows", async () => {
    const r = await run(db, "select ibc, share_12h_pct, listed_feeders * 1000 as big, share_12h_pct / 7 as d from mart_ke_ibc_equity order by listed_feeders desc", 2);
    expect(r.columns).toEqual(["ibc", "share_12h_pct", "big", "d"]);
    expect(r.kinds).toEqual(["text", "decimal", "int", "decimal"]);
    expect(r.rows).toEqual([
      ["IBC - B", "25.0", "20,000", "3.6"],
      ["IBC - A", "90.0", "10,000", "12.9"],
    ]);
    expect(r.truncated).toBe(true);
  });

  it("facts and placeholders", async () => {
    const r = await run(db, "select ibc, share_12h_pct as share from mart_ke_ibc_equity order by 2 desc", 200);
    const f = factsFrom(r.columns, r.rows, 10);
    expect(f).toMatchObject({ row_count: "3", r1_ibc: "IBC - A", r1_share: "90.0", r3_share: "0.0" });
    expect(render("{r1_ibc} leads at {r1_share}.  ", f)).toBe("IBC - A leads at 90.0.");
  });
});

// --- the whole flow, with a scripted Worker -------------------------------------------------

function script(replies: PlanReply[], narrate = "{r1_ibc} has the highest share.") {
  const calls: string[] = [];
  const api: Api = {
    ask: async (q) => (calls.push(`ask ${q}`), replies.shift()!),
    replan: async (_t, kind, detail) => (calls.push(`replan ${kind}: ${detail}`), replies.shift()!),
    narrate: async () => (calls.push("narrate"), { status: "narrated", text: narrate, model: "groq/m" }),
  };
  return { api, calls };
}
const planned = (sql: string): PlanReply => ({ status: "planned", ticket: "t", sql, model: "groq/m", attempts: [], remaining: { visitor_today: 9, site_today: 149 } });

describe("askQuestion", () => {
  const ctx: AskContext = { ...CTX, tables: { ...CTX.tables, mart_ke_ibc_equity: { ...CTX.tables.mart_ke_ibc_equity, caveats: ["Among listed feeders only."] } } };

  it("answers with numbers from the query, caveats from code", async () => {
    const { api, calls } = script([planned("select ibc, share_12h_pct from mart_ke_ibc_equity order by 2 desc limit 1")]);
    const a = await askQuestion("Which IBC has the highest share?", { api, db, ctx, serialize: fromParity });
    expect(a).toMatchObject({ status: "answered", answer: "IBC - A has the highest share.", narrated: true, n: 1, tables: ["mart_ke_ibc_equity"], caveats: ["Among listed feeders only."] });
    expect(calls).toEqual(["ask Which IBC has the highest share?", "narrate"]);
  });

  it("sends a guard refusal back for one corrected try, which never runs the bad SQL", async () => {
    const { api, calls } = script([planned("select source_file from mart_ke_ibc_equity"), planned("select ibc from mart_ke_ibc_equity order by 1 limit 1")]);
    const a = await askQuestion("q", { api, db, ctx, serialize: fromParity });
    expect(a.status).toBe("answered");
    expect(calls[1]).toMatch(/^replan guard: column not allowed/);
  });

  it("retries once after a DuckDB error, then gives up", async () => {
    const { api, calls } = script([planned("select ibc from mart_ke_ibc_equity where ibc > 1::date"), planned("select ibc from mart_ke_ibc_equity where ibc > 1::date")]);
    const a = await askQuestion("q", { api, db, ctx, serialize: fromParity });
    expect(a.status).toBe("failed");
    expect(a.reason).toMatch(/^Query failed:/);
    expect(calls.filter((c) => c.startsWith("replan error"))).toHaveLength(1);
  });

  it("retries an empty first result; an empty second result is an answer", async () => {
    const empty = "select ibc from mart_ke_ibc_equity where ibc = 'nowhere'";
    const { api, calls } = script([planned(empty), planned(empty)]);
    const a = await askQuestion("q", { api, db, ctx, serialize: fromParity });
    expect(a).toMatchObject({ status: "answered", n: 0, answer: "The query returned 0 row(s).", narrated: false });
    expect(calls).toEqual(["ask q", "replan empty: "]);
  });

  it("passes refusals, blocks and caps through without running anything", async () => {
    for (const status of ["refused", "blocked", "capped"] as const) {
      const { api } = script([{ status, reason: "why", retry_after_s: 30 }]);
      expect(await askQuestion("q", { api, db, ctx, serialize: fromParity })).toMatchObject({ status, reason: "why", sql: null });
    }
  });
});

// --- real data: the golden reference queries on the published Parquet give Python's rows ----
// Needs `uv run roshni export` and `uv run python -m roshni.ask.parity --oracle` (local only).
const ORACLE = path.join(__dirname, "..", "..", "..", "..", "data", "oracle", "ask_golden.json");
describe.skipIf(!existsSync(ORACLE) || !existsSync(path.join(EXPORT, "context.json")))("golden queries on the ask/ bundle", () => {
  it("every reference query returns the rows Python formats from the warehouse", async () => {
    const ctx = JSON.parse(readFileSync(path.join(EXPORT, "context.json"), "utf8")) as AskContext;
    const real = await nodeDb();
    await loadTables(real, ctx, async (file) => real.register(file, readFileSync(path.join(EXPORT, file))));
    const oracle = JSON.parse(readFileSync(ORACLE, "utf8")) as { id: string; sql: string; ast: string; columns: string[]; rows: string[][] }[];
    expect(oracle.length).toBeGreaterThan(10);
    for (const o of oracle) {
      expect((await guard(async () => o.ast, o.sql, ctx)).ok, o.id).toBe(true);
      const r = await run(real, o.sql, ctx.max_rows);
      // Without ORDER BY any row order is right (the eval scores such answers as multisets).
      if (!/\border\s+by\b/i.test(o.sql)) {
        const key = (row: string[]) => JSON.stringify(row);
        r.rows.sort((a, b) => key(a).localeCompare(key(b)));
        o.rows.sort((a, b) => key(a).localeCompare(key(b)));
      }
      expect({ id: o.id, columns: r.columns, rows: r.rows }).toEqual({ id: o.id, columns: o.columns, rows: o.rows });
    }
    await expect(real.query("select count(*) from read_csv('x.csv')")).rejects.toThrow();
  }, 120_000);
});
