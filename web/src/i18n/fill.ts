import { dirOf, NUMBER_OPTS } from "./config";

// First-strong isolate / pop: keeps an inserted date, time or number as its own run inside
// right-to-left text (e.g. "2026-10-12 کو 12:27 بجے"), so its digits and punctuation never reorder.
const FSI = "⁨";
const PDI = "⁩";

/** Replace {name} placeholders. Numbers are formatted for the locale. Safe on client and server. */
export function fill(template: string, values: Record<string, string | number>, locale: string) {
  const isolate = dirOf(locale) === "rtl";
  return template.replace(/\{(\w+)\}/g, (_, key: string) => {
    const v = values[key];
    if (v === undefined) throw new Error(`missing value for {${key}} in "${template}"`);
    const text = typeof v === "number" ? v.toLocaleString(locale, NUMBER_OPTS) : v;
    return isolate ? `${FSI}${text}${PDI}` : text;
  });
}
