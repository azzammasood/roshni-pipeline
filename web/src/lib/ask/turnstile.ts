// Cloudflare Turnstile on Ask Roshni (on when NEXT_PUBLIC_TURNSTILE_SITE_KEY is set at build):
// before a question costs anything, the Worker checks a single-use token from the widget, so a
// script cannot spend the day's free questions. The widget is "interaction-only": most visitors
// never see it; when Cloudflare wants a check, it appears in the console. Prepared answers and
// personal schedule questions never need it (they do not reach the Worker).
export const SITE_KEY = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY ?? "";
const SCRIPT = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";

type Api = {
  render(el: HTMLElement, o: Record<string, unknown>): string;
  execute(id: string): void;
  reset(id: string): void;
};
declare global {
  interface Window {
    turnstile?: Api;
  }
}

let loading: Promise<Api> | null = null;
function load(): Promise<Api> {
  loading ??= new Promise((resolve, reject) => {
    if (window.turnstile) return resolve(window.turnstile);
    const s = document.createElement("script");
    s.src = SCRIPT;
    s.async = true;
    s.onload = () => (window.turnstile ? resolve(window.turnstile) : reject(new Error("turnstile")));
    s.onerror = () => {
      loading = null;
      reject(new Error("turnstile"));
    };
    document.head.appendChild(s);
  });
  return loading;
}

let widget: { id: string; el: HTMLElement } | null = null;
let pending: ((t: string | null) => void) | null = null;

/** Start loading the widget script early (same moments as the query engine warm-up). */
export const warmTurnstile = () => {
  if (SITE_KEY) void load().catch(() => {});
};

/** A fresh single-use token; null when Turnstile is off. Rejects when the check cannot run. */
export async function turnstileToken(el: HTMLElement, lang: string): Promise<string | null> {
  if (!SITE_KEY) return null;
  const api = await load();
  if (!widget || widget.el !== el) {
    const id = api.render(el, {
      sitekey: SITE_KEY,
      appearance: "interaction-only",
      execution: "execute",
      language: lang === "ur" ? "ur" : "en",
      callback: (t: string) => pending?.(t),
      "error-callback": () => pending?.(null),
      "expired-callback": () => pending?.(null),
    });
    widget = { id, el };
  } else api.reset(widget.id);
  const token = await new Promise<string | null>((resolve) => {
    pending = resolve;
    api.execute(widget!.id);
    window.setTimeout(() => resolve(null), 60_000);
  });
  pending = null;
  if (!token) throw new Error("turnstile");
  return token;
}
