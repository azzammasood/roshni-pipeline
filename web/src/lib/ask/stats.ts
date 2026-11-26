// Daily usage counts from the Ask Roshni Worker (GET /v1/stats; worker/src/stats.ts). Counts
// only: no question text, no visitor ids.
import { ASK_URL } from "./api";

export type StatsDay = {
  date: string;
  questions: number;
  visitors: number;
  capped: Record<string, number>;
  blocked: number;
  planned: number;
  refused: number;
  failed: number;
  replans: { error: number; empty: number; guard: number };
  narrated: number;
  template: number;
  tokens: number;
  plan_latency: number[];
  narrate_latency: number[];
};

export type Stats = {
  status: "ok";
  window_days: number;
  buckets_s: number[];
  caps: {
    visitor_per_minute: number;
    visitor_per_day: number;
    site_per_minute: number;
    site_per_day: number;
    site_tokens_per_day: number;
  };
  days: StatsDay[];
};

export async function fetchStats(): Promise<Stats | null> {
  if (!ASK_URL) return null;
  try {
    const r = await fetch(`${ASK_URL}/v1/stats`);
    const body = (await r.json()) as Stats;
    return body.status === "ok" && Array.isArray(body.days) ? body : null;
  } catch {
    return null;
  }
}

export const sum = (xs: number[]) => xs.reduce((a, b) => a + b, 0);

/** Adds histograms bucket by bucket. */
export const addHist = (hs: number[][]) =>
  hs.reduce((acc, h) => acc.map((v, i) => v + (h[i] ?? 0)), Array(hs[0]?.length ?? 0).fill(0));

/** The bucket holding the q-quantile: index into buckets_s, or buckets_s.length for "over the
 *  last bound"; null when the histogram is empty. */
export function quantileBucket(hist: number[], q: number): number | null {
  const n = sum(hist);
  if (!n) return null;
  let seen = 0;
  for (let i = 0; i < hist.length; i++) {
    seen += hist[i];
    if (seen >= q * n) return i;
  }
  return hist.length - 1;
}

export type Totals = {
  questions: number;
  visitors: number;
  blocked: number;
  refused: number;
  capped: number;
  corrected: number;
  tokens: number;
  medianBucket: number | null;
};

export function totals(days: StatsDay[]): Totals {
  return {
    questions: sum(days.map((d) => d.questions)),
    visitors: sum(days.map((d) => d.visitors)),
    blocked: sum(days.map((d) => d.blocked)),
    refused: sum(days.map((d) => d.refused)),
    capped: sum(days.map((d) => sum(Object.values(d.capped)))),
    corrected: sum(days.map((d) => d.replans.guard + d.replans.error + d.replans.empty)),
    tokens: sum(days.map((d) => d.tokens)),
    medianBucket: quantileBucket(addHist(days.map((d) => d.plan_latency)), 0.5),
  };
}
