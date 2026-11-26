// Browser DuckDB for Ask Roshni, loaded only when a visitor asks: the engine, its worker and the
// json and parquet extensions all come from this site (scripts/sync-duckdb.mjs), the tables from the
// published ask/ bundle. Then external access is switched off and the configuration locked.
import type { AsyncDuckDB, AsyncDuckDBConnection } from "@duckdb/duckdb-wasm";
import { type AskContext, type Db, type Serialize, loadTables, serializeWith } from "./runner";

const BASE = process.env.NEXT_PUBLIC_BASE_PATH ?? "";
const QUERY_TIMEOUT_MS = 10_000; // visitors' queries only; setup may download on a slow line

export const askDataUrl = (file: string) => `${BASE}/data/v1/ask/${file}`;

export type Opened = { db: Db; serialize: Serialize; ctx: AskContext };

let opening: Promise<Opened> | null = null;

/** One database per page load; a failed open can be retried. */
export function openDb(): Promise<Opened> {
  if (!opening) {
    opening = open();
    opening.catch(() => (opening = null));
  }
  return opening;
}

async function open(): Promise<Opened> {
  const ctxResp = await fetch(askDataUrl("context.json"));
  if (!ctxResp.ok) throw new Error(`context.json: HTTP ${ctxResp.status}`);
  const ctx = (await ctxResp.json()) as AskContext;

  const duckdb = await import("@duckdb/duckdb-wasm");
  const origin = window.location.origin;
  const worker = new Worker(`${BASE}/duckdb/duckdb-browser-eh.worker.js`);
  const adb: AsyncDuckDB = new duckdb.AsyncDuckDB(new duckdb.VoidLogger(), worker);
  await adb.instantiate(`${origin}${BASE}/duckdb/duckdb-eh.wasm`);
  const conn: AsyncDuckDBConnection = await adb.connect();
  const rows = (table: { toArray(): { toJSON(): unknown }[] }) =>
    table.toArray().map((r) => r.toJSON() as Record<string, unknown>);

  // Setup (extension downloads, table loads) has no timeout: `install parquet` fetches 3.2 MB,
  // which takes longer than 10 s on a slow mobile connection (owner review 2026-11-26).
  const setup: Db = {
    async query(sql) {
      return rows(await conn.query(sql));
    },
  };

  const db: Db = {
    async query(sql, param) {
      const work = (async () => {
        if (param === undefined) return conn.query(sql);
        const st = await conn.prepare(sql);
        try {
          return await st.query(param);
        } finally {
          await st.close();
        }
      })();
      let timer: ReturnType<typeof setTimeout> | undefined;
      const timeout = new Promise<never>((_, reject) => {
        timer = setTimeout(() => {
          void conn.cancelSent();
          reject(new Error("The query took longer than 10 seconds and was stopped."));
        }, QUERY_TIMEOUT_MS);
      });
      try {
        return rows(await Promise.race([work, timeout]));
      } finally {
        clearTimeout(timer);
      }
    },
  };

  await setup.query("set autoinstall_known_extensions = false");
  await setup.query("set autoload_known_extensions = false");
  await setup.query(`set custom_extension_repository = '${origin}${BASE}/duckdb/ext'`);
  for (const ext of ["json", "parquet"]) {
    await setup.query(`install ${ext}`);
    await setup.query(`load ${ext}`);
  }
  await loadTables(setup, ctx, async (file) => {
    const r = await fetch(askDataUrl(file));
    if (!r.ok) throw new Error(`${file}: HTTP ${r.status}`);
    await adb.registerFileBuffer(file, new Uint8Array(await r.arrayBuffer()));
  });
  return { db, serialize: serializeWith(db), ctx };
}
