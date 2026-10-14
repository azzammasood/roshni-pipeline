// Build-time loader for the static export copied into public/data/v1 by scripts/sync-data.mjs.
// Server components only: reads the file system during `next build`.
import { readFile } from "node:fs/promises";
import path from "node:path";
import { slugIndex } from "./slug";
import type {
  AreasDocument,
  DarkProfile,
  Feeder,
  PlannedShutdown,
  DarkProfilesDocument,
  EquityDocument,
  FeedersDocument,
  MetaDocument,
  NationalDocument,
  NewsDocument,
  PlannedShutdownsDocument,
} from "@/types/v1";

type Documents = {
  meta: MetaDocument;
  feeders: FeedersDocument;
  dark_profiles: DarkProfilesDocument;
  planned_shutdowns: PlannedShutdownsDocument;
  areas: AreasDocument;
  equity: EquityDocument;
  national: NationalDocument;
  news: NewsDocument;
};

const DATA_DIR = path.join(process.cwd(), "public", "data", "v1");

// Module-level memo: React's cache() is per render, which re-parsed ~2 MB per feeder page.
// The files do not change during a build, so each worker parses each document once.
const memo = new Map<string, Promise<unknown>>();

export function loadDocument<K extends keyof Documents>(doc: K): Promise<Documents[K]> {
  if (!memo.has(doc)) memo.set(doc, readDocument(doc));
  return memo.get(doc) as Promise<Documents[K]>;
}

async function readDocument<K extends keyof Documents>(doc: K): Promise<Documents[K]> {
  const file = path.join(DATA_DIR, `${doc}.json`);
  const env = JSON.parse(await readFile(file, "utf8")) as Documents[K];
  if (env.schema_id !== `roshni/${doc}/v1` || !env.schema_version.startsWith("1.")) {
    throw new Error(`${file}: unexpected ${env.schema_id} ${env.schema_version}; run npm run sync-data`);
  }
  return env;
}

let feederIndex: Promise<FeederIndex> | null = null;
type FeederIndex = {
  bySlug: Map<string, Feeder>;
  profiles: Map<string, DarkProfile>;
  shutdowns: Map<string, PlannedShutdown[]>;
};

/** Per-feeder lookups for the ~1,700 feeder pages, built once per worker. */
export function loadFeederIndex(): Promise<FeederIndex> {
  feederIndex ??= (async () => {
    const [feeders, profiles, shutdowns] = await Promise.all([
      loadDocument("feeders"),
      loadDocument("dark_profiles"),
      loadDocument("planned_shutdowns"),
    ]);
    const byFeeder = new Map<string, PlannedShutdown[]>();
    for (const s of shutdowns.data) {
      if (!s.feeder_id || s.feeder_match_state !== "matched") continue;
      byFeeder.set(s.feeder_id, [...(byFeeder.get(s.feeder_id) ?? []), s]);
    }
    for (const list of byFeeder.values()) list.sort((a, b) => (a.start_utc < b.start_utc ? 1 : -1));
    return {
      bySlug: slugIndex(feeders.data),
      profiles: new Map(profiles.data.map((p) => [p.feeder_id, p])),
      shutdowns: byFeeder,
    };
  })();
  return feederIndex;
}
