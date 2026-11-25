// Caps and tickets over a key-value store. The Durable Object (do.ts) runs these one request at
// a time, so counts cannot race; tests run them over a Map.
//
// - A question is admitted only if the visitor and the whole site are under their per-minute
//   and per-day limits, and today's token budget is not spent. Days are Pakistan days.
// - Admission issues a ticket: the one corrected re-plan and the one narration of that question
//   need it, so they cost no extra question but cannot be repeated or used by someone else.
// - A visitor is an HMAC of the IP address with a secret and the day (visitorId); the raw IP is
//   never stored, and the id changes every day.

export interface Store {
  get<T>(key: string): Promise<T | undefined>;
  put<T>(key: string, value: T): Promise<void>;
  delete(key: string): Promise<boolean>;
  list<T>(opts: { prefix: string }): Promise<Map<string, T>>;
}

export type Limits = {
  visitorPerMinute: number;
  visitorPerDay: number;
  globalPerMinute: number;
  globalPerDay: number;
  tokensPerDay: number;
};

export type Reason = "visitor_minute" | "visitor_day" | "site_minute" | "site_day" | "site_tokens";
export type Remaining = { visitor_today: number; site_today: number };
export type Admission =
  | { ok: true; remaining: Remaining }
  | { ok: false; reason: Reason; retry_after_s: number; remaining: Remaining };

type Counter = { count: number; recent: number[]; tokens?: number };

export type Msg = { role: "user" | "assistant"; content: string };
export type Ticket = {
  visitor: string;
  question: string;
  created: number;
  replans: number;
  narrated: boolean;
  history: Msg[]; // after the system prompt: the question, replies and feedback, in order
};

export const TICKET_TTL_MS = 10 * 60_000;
export const MAX_REPLANS = 1;
const MINUTE = 60_000;
const PKT_OFFSET = 5 * 3_600_000; // Asia/Karachi, UTC+5, no DST

export const pktDay = (now: number) => new Date(now + PKT_OFFSET).toISOString().slice(0, 10);
export const secondsToPktMidnight = (now: number) => {
  const local = now + PKT_OFFSET;
  return Math.ceil((86_400_000 - (local % 86_400_000)) / 1000);
};

export async function visitorId(ip: string, salt: string, now: number): Promise<string> {
  const key = await crypto.subtle.importKey("raw", new TextEncoder().encode(salt), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const sig = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(`${pktDay(now)}|${ip}`));
  return [...new Uint8Array(sig).slice(0, 12)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

const fresh = (c: Counter | undefined, now: number): Counter => ({
  count: c?.count ?? 0,
  recent: (c?.recent ?? []).filter((t) => now - t < MINUTE),
  tokens: c?.tokens ?? 0,
});
const waitMinute = (recent: number[], now: number) => Math.max(1, Math.ceil((MINUTE - (now - Math.min(...recent))) / 1000));

export class Quota {
  constructor(
    private store: Store,
    private limits: Limits,
  ) {}

  private keys(visitor: string, now: number) {
    const day = pktDay(now);
    return { v: `v:${day}:${visitor}`, g: `g:${day}` };
  }

  async remaining(visitor: string, now: number): Promise<Remaining> {
    const k = this.keys(visitor, now);
    const v = fresh(await this.store.get<Counter>(k.v), now);
    const g = fresh(await this.store.get<Counter>(k.g), now);
    const tokensLeft = (g.tokens ?? 0) < this.limits.tokensPerDay;
    return {
      visitor_today: Math.max(0, this.limits.visitorPerDay - v.count),
      site_today: tokensLeft ? Math.max(0, this.limits.globalPerDay - g.count) : 0,
    };
  }

  async admit(visitor: string, now: number): Promise<Admission> {
    const L = this.limits;
    const k = this.keys(visitor, now);
    const v = fresh(await this.store.get<Counter>(k.v), now);
    const g = fresh(await this.store.get<Counter>(k.g), now);
    const toMidnight = secondsToPktMidnight(now);
    const remaining = await this.remaining(visitor, now);
    const refuse = (reason: Reason, retry_after_s: number): Admission => ({ ok: false, reason, retry_after_s, remaining });
    if (v.count >= L.visitorPerDay) return refuse("visitor_day", toMidnight);
    if (g.count >= L.globalPerDay) return refuse("site_day", toMidnight);
    if ((g.tokens ?? 0) >= L.tokensPerDay) return refuse("site_tokens", toMidnight);
    if (v.recent.length >= L.visitorPerMinute) return refuse("visitor_minute", waitMinute(v.recent, now));
    if (g.recent.length >= L.globalPerMinute) return refuse("site_minute", waitMinute(g.recent, now));
    v.count++;
    v.recent.push(now);
    g.count++;
    g.recent.push(now);
    await this.store.put(k.v, v);
    await this.store.put(k.g, g);
    return { ok: true, remaining: await this.remaining(visitor, now) };
  }

  async addTokens(n: number, now: number): Promise<void> {
    if (!n) return;
    const k = this.keys("", now).g;
    const g = fresh(await this.store.get<Counter>(k), now);
    g.tokens = (g.tokens ?? 0) + n;
    await this.store.put(k, g);
  }

  async putTicket(id: string, t: Ticket): Promise<void> {
    await this.store.put(`t:${id}`, t);
  }

  /** The ticket if it exists, belongs to this visitor and has not expired. */
  async ticket(id: string, visitor: string, now: number): Promise<Ticket | null> {
    const t = await this.store.get<Ticket>(`t:${id}`);
    if (!t || t.visitor !== visitor) return null;
    if (now - t.created > TICKET_TTL_MS) {
      await this.store.delete(`t:${id}`);
      return null;
    }
    return t;
  }

  /** Drop counters of earlier days and expired tickets. */
  async sweep(now: number): Promise<number> {
    const day = pktDay(now);
    let n = 0;
    for (const prefix of ["v:", "g:"]) {
      for (const key of (await this.store.list({ prefix })).keys()) {
        if (key.split(":")[1] !== day) n += Number(await this.store.delete(key));
      }
    }
    for (const [key, t] of await this.store.list<Ticket>({ prefix: "t:" })) {
      if (now - t.created > TICKET_TTL_MS) n += Number(await this.store.delete(key));
    }
    return n;
  }
}

/** In-memory Store for tests and local reasoning. */
export class MapStore implements Store {
  m = new Map<string, unknown>();
  async get<T>(k: string) {
    return structuredClone(this.m.get(k)) as T | undefined;
  }
  async put<T>(k: string, v: T) {
    this.m.set(k, structuredClone(v));
  }
  async delete(k: string) {
    return this.m.delete(k);
  }
  async list<T>({ prefix }: { prefix: string }) {
    return new Map([...this.m].filter(([k]) => k.startsWith(prefix))) as Map<string, T>;
  }
}
