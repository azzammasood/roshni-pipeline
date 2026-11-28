// Cloudflare entry: one Durable Object instance ("site") holds every count and ticket, so caps
// are exact; requests reach it one at a time. CORS allows only the site's origins.
import { DurableObject } from "cloudflare:workers";
import { type Context, type QuotaApi, handle, loadContext } from "./app";
import { type Limits, Quota, type Store, type Ticket, visitorId } from "./quota";
import { type SharedQuestion, Shared } from "./shared";
import { type Event, Stats } from "./stats";

export interface Env {
  QUOTA: DurableObjectNamespace<QuotaDO>;
  GROQ_API_KEY?: string;
  OPENROUTER_API_KEY?: string;
  VISITOR_SALT: string;
  CONTEXT_URL: string;
  ALLOWED_ORIGINS: string;
  VISITOR_PER_MINUTE: string;
  VISITOR_PER_DAY: string;
  SITE_PER_MINUTE: string;
  SITE_PER_DAY: string;
  SITE_TOKENS_PER_DAY: string;
  /** Optional secret: enables GET /v1/shared for the publish job. */
  ASK_ADMIN_TOKEN?: string;
}

const limits = (env: Env): Limits => ({
  visitorPerMinute: Number(env.VISITOR_PER_MINUTE),
  visitorPerDay: Number(env.VISITOR_PER_DAY),
  globalPerMinute: Number(env.SITE_PER_MINUTE),
  globalPerDay: Number(env.SITE_PER_DAY),
  tokensPerDay: Number(env.SITE_TOKENS_PER_DAY),
});

/** Durable Object storage as the Store the caps need. */
function storeOf(storage: DurableObjectStorage): Store {
  return {
    get: (k) => storage.get(k),
    put: (k, v) => storage.put(k, v),
    delete: (k) => storage.delete(k),
    list: (o) => storage.list(o),
  };
}

export class QuotaDO extends DurableObject<Env> implements QuotaApi {
  private q: Quota;
  private s: Stats;
  private sh: Shared;
  constructor(ctx: DurableObjectState, env: Env) {
    super(ctx, env);
    const store = storeOf(ctx.storage);
    this.s = new Stats(store);
    this.sh = new Shared(store);
    this.q = new Quota(store, limits(env), this.s);
  }
  private async tidy() {
    if ((await this.ctx.storage.getAlarm()) === null) await this.ctx.storage.setAlarm(Date.now() + 3_600_000);
  }
  async admit(visitor: string) {
    await this.tidy();
    return this.q.admit(visitor, Date.now());
  }
  remaining(visitor: string) {
    return this.q.remaining(visitor, Date.now());
  }
  addTokens(n: number) {
    return this.q.addTokens(n, Date.now());
  }
  putTicket(id: string, t: Ticket) {
    return this.q.putTicket(id, t);
  }
  ticket(id: string, visitor: string) {
    return this.q.ticket(id, visitor, Date.now());
  }
  record(e: Event) {
    return this.s.record(e, Date.now());
  }
  async stats() {
    return { days: await this.s.days(Date.now()), limits: limits(this.env) };
  }
  share(q: Omit<SharedQuestion, "date">, id: string) {
    return this.sh.add(q, Date.now(), id);
  }
  shared() {
    return this.sh.list(Date.now());
  }
  async alarm() {
    await this.q.sweep(Date.now());
    await this.s.sweep(Date.now());
    await this.sh.sweep(Date.now());
    await this.ctx.storage.setAlarm(Date.now() + 3_600_000);
  }
}

function cors(origin: string | null, env: Env): Record<string, string> | null {
  const allowed = env.ALLOWED_ORIGINS.split(",").map((s) => s.trim()).filter(Boolean);
  if (!origin || !allowed.includes(origin)) return null;
  return {
    "Access-Control-Allow-Origin": origin,
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Max-Age": "86400",
    Vary: "Origin",
  };
}

export default {
  async fetch(req: Request, env: Env): Promise<Response> {
    const headers = cors(req.headers.get("Origin"), env);
    if (!headers) return new Response("Ask Roshni answers requests from the Roshni site only.", { status: 403 });
    if (req.method === "OPTIONS") return new Response(null, { status: 204, headers });
    let res: Response;
    try {
      const stub = env.QUOTA.get(env.QUOTA.idFromName("site"));
      const ip = req.headers.get("CF-Connecting-IP") ?? "unknown";
      res = await handle(req, {
        quota: stub as unknown as QuotaApi,
        chain: { keys: { GROQ_API_KEY: env.GROQ_API_KEY, OPENROUTER_API_KEY: env.OPENROUTER_API_KEY } },
        context: (): Promise<Context> => loadContext(env.CONTEXT_URL),
        visitor: await visitorId(ip, env.VISITOR_SALT, Date.now()),
        newId: () => crypto.randomUUID(),
        now: () => Date.now(),
        adminToken: env.ASK_ADMIN_TOKEN,
        authorization: req.headers.get("Authorization"),
      });
    } catch (e) {
      console.error("ask error", (e as Error).message);
      res = new Response(JSON.stringify({ status: "error", reason: "Ask Roshni is unavailable right now." }), {
        status: 503,
        headers: { "Content-Type": "application/json; charset=utf-8" },
      });
    }
    const out = new Response(res.body, res);
    for (const [k, v] of Object.entries(headers)) out.headers.set(k, v);
    out.headers.set("Cache-Control", "no-store");
    return out;
  },
} satisfies ExportedHandler<Env>;
