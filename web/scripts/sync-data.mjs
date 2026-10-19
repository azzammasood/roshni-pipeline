// Copy the static export into public/data/v1 (git-ignored) after checking each envelope.
// Usage: node scripts/sync-data.mjs [--from DIR]   (default ../data/export/v1; CI uses fixtures/v1)
import { copyFile, mkdir, readFile, rm } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const webDir = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const args = process.argv.slice(2);
const fromArg = args.includes("--from") ? args[args.indexOf("--from") + 1] : null;
const from = path.resolve(webDir, fromArg ?? path.join("..", "data", "export", "v1"));
const to = path.join(webDir, "public", "data", "v1");
const DOCS = ["meta", "feeders", "dark_profiles", "planned_shutdowns", "areas", "equity", "national", "news", "maintenance"];

await rm(to, { recursive: true, force: true });
await mkdir(to, { recursive: true });
for (const doc of DOCS) {
  const src = path.join(from, `${doc}.json`);
  const env = JSON.parse(await readFile(src, "utf8"));
  if (env.schema_id !== `roshni/${doc}/v1` || !String(env.schema_version).startsWith("1.")) {
    throw new Error(`${src}: expected roshni/${doc}/v1 1.x, got ${env.schema_id} ${env.schema_version}`);
  }
  await copyFile(src, path.join(to, `${doc}.json`));
  const n = Array.isArray(env.data) ? env.data.length : "-";
  console.log(`${doc.padEnd(18)} ${env.schema_version}  rows=${n}`);
}
console.log(`synced ${path.relative(webDir, from)} -> ${path.relative(webDir, to)}`);
