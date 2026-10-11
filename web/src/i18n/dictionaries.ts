import "server-only";
import type { Locale } from "./config";
import type en from "./en.json";

export type Dictionary = typeof en;

const dictionaries: Record<Locale, () => Promise<Dictionary>> = {
  en: () => import("./en.json").then((m) => m.default),
};

export const getDictionary = (locale: Locale) => dictionaries[locale]();

/** Replace {name} placeholders. Numbers are formatted for the locale. */
export function fill(template: string, values: Record<string, string | number>, locale: Locale) {
  return template.replace(/\{(\w+)\}/g, (_, key: string) => {
    const v = values[key];
    if (v === undefined) throw new Error(`missing value for {${key}} in "${template}"`);
    return typeof v === "number" ? v.toLocaleString(locale) : v;
  });
}
