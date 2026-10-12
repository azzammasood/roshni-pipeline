import "server-only";
import type { Locale } from "./config";
import type en from "./en.json";

export type Dictionary = typeof en;
export { fill } from "./fill";

const dictionaries: Record<Locale, () => Promise<Dictionary>> = {
  en: () => import("./en.json").then((m) => m.default),
};

export const getDictionary = (locale: Locale) => dictionaries[locale]();
