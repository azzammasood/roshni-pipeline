// English first; Urdu ("ur", RTL) is added in phase F5 with owner review (DECISIONS.md 2026-10-11).
export const locales = ["en"] as const;
export type Locale = (typeof locales)[number];
export const defaultLocale: Locale = "en";

const rtl = new Set<string>(["ur"]);
export const dirOf = (locale: string): "rtl" | "ltr" => (rtl.has(locale) ? "rtl" : "ltr");
export const hasLocale = (value: string): value is Locale =>
  (locales as readonly string[]).includes(value);
