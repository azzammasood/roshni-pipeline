// English first; Urdu ("ur", RTL) added in F5. NEXT_PUBLIC_LOCALES limits which locales are built
// (comma list, default all): the publish workflow builds "en" until the owner approves the Urdu text.
export const locales = ["en", "ur"] as const;
export type Locale = (typeof locales)[number];
export const defaultLocale: Locale = "en";

const requested = process.env.NEXT_PUBLIC_LOCALES?.split(",").map((s) => s.trim()).filter(Boolean);
export const builtLocales: readonly Locale[] = requested?.length
  ? locales.filter((l) => requested.includes(l))
  : locales;

const rtl = new Set<string>(["ur"]);
export const dirOf = (locale: string): "rtl" | "ltr" => (rtl.has(locale) ? "rtl" : "ltr");
export const hasLocale = (value: string): value is Locale =>
  (builtLocales as readonly string[]).includes(value);

/** Western digits in every locale (Pakistan's usual digital convention; schedules print them). */
export const NUMBER_OPTS = { numberingSystem: "latn" } as const;
