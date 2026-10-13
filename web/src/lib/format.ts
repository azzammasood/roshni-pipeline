import { NUMBER_OPTS } from "@/i18n/config";

/** Numbers as exported (up to 3 decimals, trailing zeros dropped), grouped for the locale.
 *  The equity gate (scripts/check-equity-numbers.mjs) relies on numbers not being re-rounded. */
export function num(value: number, locale: string): string {
  return value.toLocaleString(locale, { ...NUMBER_OPTS, maximumFractionDigits: 3 });
}

export function pct(value: number | null, locale: string): string {
  return value === null ? "–" : `${num(value, locale)}%`;
}

const decimals = (v: number) => {
  const s = String(v);
  return s.includes("e") ? 3 : (s.split(".")[1]?.length ?? 0);
};

/** One column, one number of decimals: pads every value to the most decimals in the column
 *  (never rounds, so each value still equals the exported number). */
export function columnFormat(values: (number | null)[], locale: string, suffix = "") {
  const digits = Math.min(3, Math.max(0, ...values.filter((v) => v !== null).map(decimals)));
  return (value: number | null) =>
    value === null
      ? "–"
      : `${value.toLocaleString(locale, {
          ...NUMBER_OPTS,
          minimumFractionDigits: digits,
          maximumFractionDigits: digits,
        })}${suffix}`;
}
