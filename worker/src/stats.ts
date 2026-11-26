// Daily usage counters for /health/ (GET /v1/stats). Counts only: no question text, no visitor
// id, no IP. One record per Pakistan day under "s:<day>", kept for STATS_DAYS days.
import { type Reason, type Store, pktDay } from "./quota";

export const STATS_DAYS = 30;
/** Upper bounds (seconds) of the latency histogram; the last bucket is everything above. */
export const BUCKETS_S = [0.5, 1, 2, 4, 8, 16] as const;

export type Day = {
  questions: number; // admitted by the caps
  visitors: number; // distinct (hashed) visitors who asked
  capped: Partial<Record<Reason, number>>;
  blocked: number; // prompt guard
  planned: number; // a query was written (first try)
  refused: number; // the planner said not answerable
  failed: number; // no model produced a valid plan
  replans: { error: number; empty: number; guard: number }; // the browser's reason to re-plan
  narrated: number;
  template: number; // narration fell back to the template
  tokens: number;
  plan_latency: number[]; // histogram over BUCKETS_S (+1 overflow)
  narrate_latency: number[];
};

export type Event =
  | { kind: "question"; newVisitor: boolean }
  | { kind: "capped"; reason: Reason }
  | { kind: "blocked" }
  | { kind: "plan"; outcome: "planned" | "refused" | "failed"; replan?: "error" | "empty" | "guard"; latency_s: number; tokens: number }
  | { kind: "narrate"; outcome: "narrated" | "template"; latency_s: number; tokens: number };

const empty = (): Day => ({
  questions: 0,
  visitors: 0,
  capped: {},
  blocked: 0,
  planned: 0,
  refused: 0,
  failed: 0,
  replans: { error: 0, empty: 0, guard: 0 },
  narrated: 0,
  template: 0,
  tokens: 0,
  plan_latency: Array(BUCKETS_S.length + 1).fill(0),
  narrate_latency: Array(BUCKETS_S.length + 1).fill(0),
});

export const bucket = (s: number) => {
  const i = BUCKETS_S.findIndex((b) => s <= b);
  return i < 0 ? BUCKETS_S.length : i;
};

export function apply(d: Day, e: Event): Day {
  switch (e.kind) {
    case "question":
      d.questions++;
      if (e.newVisitor) d.visitors++;
      break;
    case "capped":
      d.capped[e.reason] = (d.capped[e.reason] ?? 0) + 1;
      break;
    case "blocked":
      d.blocked++;
      break;
    case "plan":
      if (e.replan) d.replans[e.replan]++;
      else d[e.outcome]++;
      d.tokens += e.tokens;
      d.plan_latency[bucket(e.latency_s)]++;
      break;
    case "narrate":
      d[e.outcome]++;
      d.tokens += e.tokens;
      d.narrate_latency[bucket(e.latency_s)]++;
      break;
  }
  return d;
}

export class Stats {
  constructor(private store: Store) {}

  async record(e: Event, now: number): Promise<void> {
    const key = `s:${pktDay(now)}`;
    const d = (await this.store.get<Day>(key)) ?? empty();
    await this.store.put(key, apply(d, e));
  }

  /** The last STATS_DAYS days that have counts, oldest first. */
  async days(now: number) {
    const oldest = pktDay(now - (STATS_DAYS - 1) * 86_400_000);
    const all = await this.store.list<Day>({ prefix: "s:" });
    return [...all]
      .map(([k, d]) => ({ date: k.slice(2), ...d }))
      .filter((d) => d.date >= oldest)
      .sort((a, b) => a.date.localeCompare(b.date));
  }

  /** Delete days older than the window. */
  async sweep(now: number): Promise<number> {
    const oldest = pktDay(now - (STATS_DAYS - 1) * 86_400_000);
    let n = 0;
    for (const key of (await this.store.list({ prefix: "s:" })).keys()) {
      if (key.slice(2) < oldest) n += Number(await this.store.delete(key));
    }
    return n;
  }
}
