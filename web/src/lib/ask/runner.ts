// Runs the planner's SQL in the visitor's browser over the published ask/ Parquet files.
// `Db` is the one method this needs, so tests use DuckDB-WASM's Node build and the page uses
// the browser build (duckdb.ts). After the tables are loaded, external access is switched off
// and the configuration locked, so a query cannot read any other file or URL.
import { type Allow, type Verdict, checkAst } from "./guard";
import { type Kind, fmt } from "./format";

export interface Db {
  /** Rows as plain objects; `param` binds the single `?` when given. */
  query(sql: string, param?: string): Promise<Record<string, unknown>[]>;
}

export type AskContext = {
  bundle_version: number;
  built_at: string | null;
  tables: Record<string, { file: string; rows: number; columns: string[]; caveats: string[] }>;
  blocked_function_prefixes: string[];
  max_rows: number;
  max_fact_rows: number;
  max_question_chars: number;
};

export type Result = { columns: string[]; kinds: Kind[]; raw: (string | null)[][]; rows: string[][]; truncated: boolean };

export const allowOf = (ctx: AskContext): Allow => ({ tables: ctx.tables, blocked: ctx.blocked_function_prefixes });

const ident = (s: string) => `"${s.replace(/"/g, '""')}"`;

/** Load every table (bytes already fetched) and lock the database down. */
export async function loadTables(db: Db, ctx: AskContext, register: (file: string) => Promise<void>) {
  for (const [name, t] of Object.entries(ctx.tables)) {
    await register(t.file);
    await db.query(`create or replace table ${ident(name)} as select * from read_parquet('${t.file.replace(/'/g, "")}')`);
  }
  await db.query("set enable_external_access = false");
  await db.query("set lock_configuration = true");
}

/** DuckDB's parse tree as JSON (the `json` extension, loaded from this site in duckdb.ts). */
export type Serialize = (sql: string) => Promise<string>;

export const serializeWith = (db: Db): Serialize => async (sql) => {
  const [row] = await db.query("select json_serialize_sql(?::varchar) as j", sql);
  return String(row?.j ?? "");
};

export async function guard(serialize: Serialize, sql: string, ctx: AskContext): Promise<Verdict> {
  return checkAst(await serialize(sql), allowOf(ctx));
}

function kindOf(type: string): Kind {
  const t = type.toUpperCase();
  if (/^(DECIMAL|NUMERIC|DOUBLE|FLOAT|REAL)/.test(t)) return "decimal";
  if (/^U?(TINYINT|SMALLINT|INTEGER|BIGINT|HUGEINT|INT)/.test(t)) return "int";
  if (t === "BOOLEAN") return "bool";
  if (t.startsWith("TIMESTAMP")) return "ts";
  return "text";
}

/** Run a guarded query: at most max_rows rows (one more is fetched to know it was capped);
 *  every value comes back as DuckDB's own text so DECIMAL stays exact. */
export async function run(db: Db, sql: string, maxRows: number): Promise<Result> {
  const body = sql.trim().replace(/;\s*$/, "");
  const desc = await db.query(`describe ${body}`);
  const columns = desc.map((d) => String(d.column_name));
  const kinds = desc.map((d) => kindOf(String(d.column_type)));
  const names = columns.map((_, i) => `c${i}`);
  const exprs = kinds.map((k, i) =>
    k === "ts" ? `cast(epoch_ms(q.c${i}) as varchar) as c${i}` : `cast(q.c${i} as varchar) as c${i}`,
  );
  const rows = await db.query(`select ${exprs.join(", ")} from (${body}) as q(${names.join(", ")}) limit ${maxRows + 1}`);
  const raw = rows.slice(0, maxRows).map((r) => names.map((n) => (r[n] === null || r[n] === undefined ? null : String(r[n]))));
  return {
    columns,
    kinds,
    raw,
    rows: raw.map((r) => r.map((v, i) => fmt(v, kinds[i]))),
    truncated: rows.length > maxRows,
  };
}
