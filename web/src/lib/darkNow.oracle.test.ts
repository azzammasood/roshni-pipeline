// F1 gate: the TypeScript port must give the same rows as the Python dark_now() on the real export.
// Needs `uv run python scripts/dark_now_oracle.py` and `npm run sync-data` (full export);
// skipped unless both are present (CI has neither; local fixture syncs skip too).
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import type { DarkProfilesDocument, FeedersDocument, PlannedShutdownsDocument } from "@/types/v1";
import { darkNow, type IescoLevel } from "./darkNow";

const ORACLE = path.join(__dirname, "..", "..", "..", "data", "oracle", "dark_now.json");
const DATA = path.join(__dirname, "..", "..", "public", "data", "v1");

interface Case {
  at_utc: string;
  level: IescoLevel | null;
  rows: [string, string | null, string, string, string | null, string | null][];
  not_yet: number;
  unmatched: number;
}

const read = <T,>(file: string): T => JSON.parse(readFileSync(file, "utf8"));
const load = <T,>(doc: string): T | null => {
  const file = path.join(DATA, `${doc}.json`);
  return existsSync(file) ? read<T>(file) : null;
};
const profiles = load<DarkProfilesDocument>("dark_profiles")?.data ?? [];
const ready = existsSync(ORACLE) && profiles.length > 1000; // fixtures hold a handful of feeders

describe.skipIf(!ready)("darkNow matches the Python oracle", () => {
  const cases: Case[] = ready ? read(ORACLE) : [];
  const data = {
    feeders: load<FeedersDocument>("feeders")?.data ?? [],
    profiles,
    shutdowns: load<PlannedShutdownsDocument>("planned_shutdowns")?.data ?? [],
  };

  it.each(cases.map((c) => [c.at_utc, c.level ?? "none", c] as const))(
    "%s level %s",
    (_at, _level, c) => {
      const r = darkNow(data, new Date(c.at_utc), c.level);
      const rows = r.rows.map((x) => [
        x.kind, x.feederId, x.feederName, x.windowLocal, x.area, x.effectiveFrom,
      ]);
      expect(rows).toEqual(c.rows);
      expect(r.notes.filter((n) => n.kind === "not_yet_effective").length).toBe(c.not_yet);
      const unmatched = r.notes.find((n) => n.kind === "unmatched_shutdowns");
      expect(unmatched?.count ?? 0).toBe(c.unmatched);
    },
  );
});
