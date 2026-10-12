import { NUMBER_OPTS } from "@/i18n/config";

/** Numbers as exported (up to 3 decimals, trailing zeros dropped), grouped for the locale.
 *  The equity gate (scripts/check-equity-numbers.mjs) relies on numbers not being re-rounded. */
export function num(value: number, locale: string): string {
  return value.toLocaleString(locale, { ...NUMBER_OPTS, maximumFractionDigits: 3 });
}

export function pct(value: number | null, locale: string): string {
  return value === null ? "–" : `${num(value, locale)}%`;
}
