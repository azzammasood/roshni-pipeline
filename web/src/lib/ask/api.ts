// Client for the Ask Roshni Worker (worker/). NEXT_PUBLIC_ASK_URL is set at build time; without
// it the page says Ask Roshni is not switched on.
import type { Api, NarrateReply, PlanReply, Remaining } from "./session";

export const ASK_URL = (process.env.NEXT_PUBLIC_ASK_URL ?? "").replace(/\/+$/, "");

async function call<T>(path: string, body?: unknown): Promise<T> {
  try {
    const r = await fetch(`${ASK_URL}${path}`, {
      method: body === undefined ? "GET" : "POST",
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    return (await r.json()) as T;
  } catch {
    return { status: "error" } as T;
  }
}

export const workerApi: Api = {
  ask: (question, previous) => call<PlanReply>("/v1/ask", previous ? { question, previous } : { question }),
  replan: (ticket, kind, detail) => call<PlanReply>("/v1/replan", { ticket, kind, detail }),
  narrate: (ticket, columns, facts) => call<NarrateReply>("/v1/narrate", { ticket, columns, facts }),
};

/** One vote per answer (counts only on the Worker). */
export const feedback = (ticket: string, vote: "up" | "down", reason?: string) =>
  call<{ status: string }>("/v1/feedback", { ticket, vote, reason });

export const quota = () => call<{ status: string; remaining?: Remaining }>("/v1/quota");
