// Which chart a result gets, decided by code from its shape, never by a model: one label column
// and one numeric column, 2 to 24 rows, values not all equal. Anything else gets the table only.
export type Bars = { label: string; value: string; bars: { label: string; value: number; text: string }[] };

const NUMBER = /^-?\d+(?:\.\d+)?$/;
export const MAX_BARS = 24;

export function chartOf(columns: string[], rows: string[][]): Bars | null {
  if (columns.length !== 2 || rows.length < 2 || rows.length > MAX_BARS) return null;
  const [labelAt, valueAt] = rows.every((r) => NUMBER.test(r[1] ?? ""))
    ? [0, 1]
    : rows.every((r) => NUMBER.test(r[0] ?? ""))
      ? [1, 0]
      : [-1, -1];
  if (labelAt < 0) return null;
  const bars = rows.map((r) => ({ label: r[labelAt], value: Number(r[valueAt]), text: r[valueAt] }));
  if (new Set(bars.map((b) => b.value)).size < 2) return null;
  return { label: columns[labelAt], value: columns[valueAt], bars };
}
