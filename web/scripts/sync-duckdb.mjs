// Self-host DuckDB-WASM for Ask Roshni: copy the engine (eh build) from node_modules into
// public/duckdb/ and the extensions the WASM build lacks (`json` for json_serialize_sql, used by
// the SQL guard; `parquet` to read the published tables) into
// public/duckdb/ext/<duckdb version>/wasm_eh/. The extension is downloaded once from DuckDB's
// official extension repository and must match the pinned SHA-256; visitors' browsers then load
// everything from this site and never contact a third party. Cached in node_modules/.cache.
import { createHash } from "node:crypto";
import { copyFile, mkdir, readFile, writeFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const webDir = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const dist = path.join(webDir, "node_modules", "@duckdb", "duckdb-wasm", "dist");
const out = path.join(webDir, "public", "duckdb");

// DuckDB core version inside @duckdb/duckdb-wasm 1.33.1-dev57.0 (select version() -> v1.5.4).
export const DUCKDB_VERSION = "v1.5.4";
const EXTENSIONS = {
  json: "993b19f7929cc305b2529c548f2842e8e7a5b112d1c88f31c84798b51901ca16",
  parquet: "4845705bbd69fc9ad52878d96a505c73cae4a6c509822079cc2413e5eb437f95",
};

await mkdir(out, { recursive: true });
for (const f of ["duckdb-eh.wasm", "duckdb-browser-eh.worker.js"]) {
  await copyFile(path.join(dist, f), path.join(out, f));
}

const cache = path.join(webDir, "node_modules", ".cache", "duckdb-ext", DUCKDB_VERSION);
await mkdir(cache, { recursive: true });
const extDir = path.join(out, "ext", DUCKDB_VERSION, "wasm_eh");
await mkdir(extDir, { recursive: true });
for (const [name, sha] of Object.entries(EXTENSIONS)) {
  const file = `${name}.duckdb_extension.wasm`;
  const cached = path.join(cache, file);
  if (!existsSync(cached)) {
    const url = `https://extensions.duckdb.org/${DUCKDB_VERSION}/wasm_eh/${file}`;
    const res = await fetch(url, { headers: { "User-Agent": "roshni-pipeline/0.1 (+https://github.com/azzammasood/roshni-pipeline)" } });
    if (!res.ok) throw new Error(`${url}: HTTP ${res.status}`);
    await writeFile(cached, Buffer.from(await res.arrayBuffer()));
  }
  const bytes = await readFile(cached);
  const got = createHash("sha256").update(bytes).digest("hex");
  if (got !== sha) throw new Error(`${file}: SHA-256 ${got}, expected ${sha} (refusing to ship it)`);
  await writeFile(path.join(extDir, file), bytes);
}
console.log(`duckdb: engine + ${Object.keys(EXTENSIONS).join(", ")} extension (${DUCKDB_VERSION}) -> public/duckdb`);
