// Provider chain (port of src/roshni/llm/chain.py; models and order from llm.json, which a
// Python test keeps equal to config/llm.yml). The first reply that `check` accepts wins; a
// provider without a key is skipped; HTTP 429 is retried once after Retry-After (5 s if
// missing) when that is at most max_wait_s; network errors move on to the next model.
import llm from "./llm.json";

export type Msg = { role: "system" | "user" | "assistant"; content: string };
export type Attempt = {
  provider: string;
  model: string;
  outcome: string;
  tokens_in: number;
  tokens_out: number;
  latency_s: number;
};
export type Completion = { text: string | null; attempts: Attempt[]; model: string | null };
export type Keys = Record<string, string | undefined>;
export type Fetcher = (url: string, init: RequestInit) => Promise<Response>;

type Provider = {
  name: string;
  base_url: string;
  key_env: string;
  headers?: Record<string, string>;
  models: { id: string; params?: Record<string, unknown> }[];
};
export type ChainConfig = {
  providers: Provider[];
  max_tokens: number;
  temperature: number;
  max_wait_s: number;
  guard: { provider: string; model: string; threshold: number };
};

export const CONFIG = llm as ChainConfig;

export type ChainDeps = {
  keys: Keys;
  fetcher?: Fetcher;
  sleep?: (ms: number) => Promise<void>;
  now?: () => number;
  config?: ChainConfig;
};

const realSleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

function post(p: Provider, key: string, body: unknown, fetcher: Fetcher): Promise<Response> {
  return fetcher(`${p.base_url}/chat/completions`, {
    method: "POST",
    headers: { Authorization: `Bearer ${key}`, "Content-Type": "application/json", ...(p.headers ?? {}) },
    body: JSON.stringify(body),
  });
}

export async function complete(
  messages: Msg[],
  check: (text: string) => string[],
  deps: ChainDeps,
  jsonMode = false,
): Promise<Completion> {
  const cfg = deps.config ?? CONFIG;
  const fetcher = deps.fetcher ?? fetch;
  const sleep = deps.sleep ?? realSleep;
  const now = deps.now ?? (() => performance.now());
  const attempts: Attempt[] = [];
  for (const p of cfg.providers) {
    const key = deps.keys[p.key_env];
    if (!key) {
      attempts.push({ provider: p.name, model: "*", outcome: `skipped: ${p.key_env} not set`, tokens_in: 0, tokens_out: 0, latency_s: 0 });
      continue;
    }
    for (const m of p.models) {
      const body: Record<string, unknown> = {
        model: m.id,
        messages,
        max_tokens: cfg.max_tokens,
        temperature: cfg.temperature,
        ...(m.params ?? {}),
      };
      if (jsonMode) body.response_format = { type: "json_object" };
      let t0 = now();
      let resp: Response;
      try {
        resp = await post(p, key, body, fetcher);
        if (resp.status === 429) {
          const wait = Number(resp.headers.get("retry-after") || 5);
          if (wait <= cfg.max_wait_s) {
            await sleep(wait * 1000);
            t0 = now();
            resp = await post(p, key, body, fetcher);
          }
        }
      } catch (e) {
        attempts.push({ provider: p.name, model: m.id, outcome: `network error: ${(e as Error).name}`, tokens_in: 0, tokens_out: 0, latency_s: 0 });
        continue;
      }
      const att: Attempt = { provider: p.name, model: m.id, outcome: "", tokens_in: 0, tokens_out: 0, latency_s: Math.round(now() - t0) / 1000 };
      attempts.push(att);
      if (resp.status !== 200) {
        const ra = resp.headers.get("retry-after");
        att.outcome = `HTTP ${resp.status}` + (ra ? ` (retry-after ${ra}s)` : "");
        continue;
      }
      let data: { usage?: { prompt_tokens?: number; completion_tokens?: number }; choices?: { message?: { content?: unknown }; finish_reason?: string }[] };
      try {
        data = await resp.json();
      } catch {
        att.outcome = "rejected: body is not JSON";
        continue;
      }
      att.tokens_in = data.usage?.prompt_tokens ?? 0;
      att.tokens_out = data.usage?.completion_tokens ?? 0;
      const choice = data.choices?.[0] ?? {};
      const text = choice.message?.content;
      if (typeof text !== "string" || !text.trim()) {
        att.outcome = `rejected: empty (${choice.finish_reason})`;
        continue;
      }
      if (choice.finish_reason === "length") {
        att.outcome = "rejected: truncated";
        continue;
      }
      const problems = check(text);
      if (problems.length) {
        att.outcome = ("rejected: " + problems.join("; ")).slice(0, 310);
        continue;
      }
      att.outcome = "accepted";
      return { text, attempts, model: `${p.name}/${m.id}` };
    }
  }
  return { text: null, attempts, model: null };
}

/** Prompt-injection probability from the guard model; null when it cannot be reached. */
export async function guardScore(text: string, deps: ChainDeps): Promise<number | null> {
  const cfg = deps.config ?? CONFIG;
  const p = cfg.providers.find((x) => x.name === cfg.guard.provider);
  const key = p && deps.keys[p.key_env];
  if (!p || !key) return null;
  try {
    const resp = await post(p, key, { model: cfg.guard.model, messages: [{ role: "user", content: text }] }, deps.fetcher ?? fetch);
    if (resp.status !== 200) return null;
    const data = (await resp.json()) as { choices?: { message?: { content?: string } }[] };
    const v = Number(String(data.choices?.[0]?.message?.content ?? "").trim());
    return Number.isFinite(v) && String(data.choices?.[0]?.message?.content ?? "").trim() !== "" ? v : null;
  } catch {
    return null;
  }
}

/** JSON object from a reply, tolerating a ```json fence (as chain.parse_json). */
export function parseJson(text: string): Record<string, unknown> {
  let t = text.trim();
  if (t.startsWith("```")) {
    t = t.replace(/^`+|`+$/g, "");
    t = t.slice(t.indexOf("{"));
  }
  const v = JSON.parse(t);
  if (typeof v !== "object" || v === null || Array.isArray(v)) throw new Error("not an object");
  return v as Record<string, unknown>;
}

export const tokens = (atts: Attempt[]) => atts.reduce((s, a) => s + a.tokens_in + a.tokens_out, 0);
