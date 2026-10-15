// Cities = the eleven distribution companies in NEPRA's tables, named by the city each serves.
// Pure helpers (no React), shared by the national grid, its popup and the city pages.

export const CITY_SLUGS: Record<string, string> = {
  PESCO: "peshawar",
  IESCO: "islamabad",
  GEPCO: "gujranwala",
  FESCO: "faisalabad",
  LESCO: "lahore",
  MEPCO: "multan",
  QESCO: "quetta",
  SEPCO: "sukkur",
  HESCO: "hyderabad",
  TESCO: "tribal-districts",
  "K-Electric": "karachi",
};

export const companyOfSlug = (slug: string) =>
  Object.entries(CITY_SLUGS).find(([, s]) => s === slug)?.[0] ?? null;

export const cityHref = (locale: string, company: string) =>
  CITY_SLUGS[company] ? `/${locale}/city/${CITY_SLUGS[company]}/` : null;

type Row = { company: string; fiscal_year: string; reported_hours_per_day: number };

/** Rank 1 = most hours reported that year; equal values share a rank. */
export function rankIn(rows: Row[], company: string, year: string): { rank: number; of: number } | null {
  const year_ = rows.filter((r) => r.fiscal_year === year);
  const own = year_.find((r) => r.company === company);
  if (!own) return null;
  return {
    rank: 1 + year_.filter((r) => r.reported_hours_per_day > own.reported_hours_per_day).length,
    of: year_.length,
  };
}

/** Median of the companies' reported figures for one year (descriptive context only). */
export function medianOf(values: number[]): number | null {
  if (values.length === 0) return null;
  const s = [...values].sort((a, b) => a - b);
  const m = Math.floor(s.length / 2);
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}

/** "A", "A and B", "A, B and C" with the locale's "and" and list comma. */
export function joinList(items: string[], and: string, comma = ", "): string {
  if (items.length <= 1) return items.join("");
  return `${items.slice(0, -1).join(comma)} ${and} ${items.at(-1)}`;
}

/** Rounded for display only where the export has more precision than a chart needs. */
export const round1 = (v: number) => Math.round(v * 10) / 10;
