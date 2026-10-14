// Trim the real export (../data/export/v1) to a few rows per document for CI builds.
// Fixtures hold only public feeder/area names and our own derived numbers.
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const webDir = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const src = path.join(webDir, "..", "data", "export", "v1");
const dst = path.join(webDir, "fixtures", "v1");
const load = async (d) => JSON.parse(await readFile(path.join(src, `${d}.json`), "utf8"));
const save = (d, env) => writeFile(path.join(dst, `${d}.json`), JSON.stringify(env, null, 1) + "\n");

const [meta, feeders, profiles, shutdowns, areas, equity, national, news] = await Promise.all(
  ["meta", "feeders", "dark_profiles", "planned_shutdowns", "areas", "equity", "national", "news"].map(load),
);
const matched = shutdowns.data.filter((s) => s.feeder_match_state === "matched");
const iescoIds = [...new Set(matched.map((s) => s.feeder_id))].sort().slice(0, 3);
const keIds = feeders.data
  .filter((f) => f.source === "kelectric" && f.has_schedule)
  .slice(0, 3)
  .map((f) => f.feeder_id);
const withLocality = feeders.data.find((f) => f.source === "iesco" && f.localities.length);
const ids = new Set([...iescoIds, ...keIds, withLocality.feeder_id]);

const keepFeeders = feeders.data.filter((f) => ids.has(f.feeder_id));
const keepShutdowns = [
  ...shutdowns.data.filter((s) => ids.has(s.feeder_id)).slice(0, 6),
  ...["unmatched", "out_of_scope"].map((st) => shutdowns.data.find((s) => s.feeder_match_state === st)),
];
const areaIds = new Set(keepFeeders.flatMap((f) => f.localities.map((l) => l.area_id)));
const keepAreas = areas.data.filter((a) => areaIds.has(a.area_id) || a.level.endsWith("district")).slice(0, 12);

await mkdir(dst, { recursive: true });
await save("meta", meta);
await save("feeders", { ...feeders, data: keepFeeders });
await save("dark_profiles", { ...profiles, data: profiles.data.filter((p) => ids.has(p.feeder_id)) });
await save("planned_shutdowns", { ...shutdowns, data: keepShutdowns });
await save("areas", { ...areas, data: keepAreas });
await save("equity", equity);
await save("national", national); // 130 rows of NEPRA-reported hours: small, kept whole
await save("news", { ...news, data: news.data.slice(0, 3) });
console.log(`fixtures: ${keepFeeders.length} feeders, ${keepShutdowns.length} shutdowns, ${keepAreas.length} areas`);
