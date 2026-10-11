// Build-time loader for the static export copied into public/data/v1 by scripts/sync-data.mjs.
// Server components only: reads the file system during `next build`.
import { readFile } from "node:fs/promises";
import path from "node:path";
import { cache } from "react";
import type {
  AreasDocument,
  DarkProfilesDocument,
  EquityDocument,
  FeedersDocument,
  MetaDocument,
  PlannedShutdownsDocument,
} from "@/types/v1";

type Documents = {
  meta: MetaDocument;
  feeders: FeedersDocument;
  dark_profiles: DarkProfilesDocument;
  planned_shutdowns: PlannedShutdownsDocument;
  areas: AreasDocument;
  equity: EquityDocument;
};

const DATA_DIR = path.join(process.cwd(), "public", "data", "v1");

export const loadDocument = cache(async <K extends keyof Documents>(doc: K): Promise<Documents[K]> => {
  const file = path.join(DATA_DIR, `${doc}.json`);
  const env = JSON.parse(await readFile(file, "utf8")) as Documents[K];
  if (env.schema_id !== `roshni/${doc}/v1` || !env.schema_version.startsWith("1.")) {
    throw new Error(`${file}: unexpected ${env.schema_id} ${env.schema_version}; run npm run sync-data`);
  }
  return env;
});

/** Public URL of a document for client-side fetches (respects basePath). */
export function documentUrl(doc: keyof Documents): string {
  return `${process.env.NEXT_PUBLIC_BASE_PATH ?? ""}/data/v1/${doc}.json`;
}
