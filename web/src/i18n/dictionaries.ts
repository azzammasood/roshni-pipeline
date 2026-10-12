import "server-only";
import type { Locale } from "./config";
import type en from "./en.json";
import exportTextUr from "./export-text.ur.json";

export type Dictionary = typeof en;
export { fill } from "./fill";

const dictionaries: Record<Locale, () => Promise<Dictionary>> = {
  en: () => import("./en.json").then((m) => m.default),
  ur: () => import("./ur.json").then((m) => m.default as Dictionary),
};

export const getDictionary = (locale: Locale) => dictionaries[locale]();

const exportText: Partial<Record<Locale, Record<string, string>>> = { ur: exportTextUr };

/** Fixed English text from the export, translated when a translation exists. `lang` is set when
 *  the text stays English, so the page can mark it (lang/dir) for screen readers and layout. */
export function fromExport(text: string, locale: Locale): { text: string; lang?: "en" } {
  if (locale === "en") return { text };
  const translated = exportText[locale]?.[text];
  return translated ? { text: translated } : { text, lang: "en" };
}
