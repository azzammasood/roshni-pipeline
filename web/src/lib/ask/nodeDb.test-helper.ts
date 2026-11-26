// Test helper: DuckDB-WASM's Node build (the same engine the page loads) behind the Db interface.
import { createRequire } from "node:module";
import path from "node:path";
import type { Db } from "./runner";

const require = createRequire(import.meta.url);

export async function nodeDb(): Promise<Db & { register(name: string, bytes: Uint8Array): void }> {
  const duckdb = require("@duckdb/duckdb-wasm/dist/duckdb-node-blocking.cjs");
  const dist = path.dirname(require.resolve("@duckdb/duckdb-wasm/dist/duckdb-node-blocking.cjs"));
  const db = await duckdb.createDuckDB(
    {
      mvp: { mainModule: path.join(dist, "duckdb-mvp.wasm"), mainWorker: "" },
      eh: { mainModule: path.join(dist, "duckdb-eh.wasm"), mainWorker: "" },
    },
    new duckdb.VoidLogger(),
    duckdb.NODE_RUNTIME,
  );
  await db.instantiate();
  const con = db.connect();
  const plain = (t: { toArray(): { toJSON(): Record<string, unknown> }[] }) => t.toArray().map((r) => r.toJSON());
  return {
    async query(sql: string, param?: string) {
      if (param === undefined) return plain(con.query(sql));
      const st = con.prepare(sql);
      try {
        return plain(st.query(param));
      } finally {
        st.close();
      }
    },
    register(name: string, bytes: Uint8Array) {
      db.registerFileBuffer(name, bytes);
    },
  };
}
