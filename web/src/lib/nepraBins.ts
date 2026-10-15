// Stepped colours for NEPRA's reported hours, day to night: each passes WCAG AA with its text
// colour (5.3:1 or better). [upper bound in hours (exclusive), background, text]
export const BINS: [number, string, string][] = [
  [1, "#f5c518", "#14213d"],
  [3, "#f29a3a", "#14213d"],
  [6, "#b03a3a", "#f4f1ea"],
  [9, "#6b2d5c", "#f4f1ea"],
  [Infinity, "#14213d", "#f4f1ea"],
];
export const BIN_LABELS = ["< 1", "1–3", "3–6", "6–9", "9+"];

export function cellStyle(hours: number) {
  const [, background, color] = BINS.find(([max]) => hours < max)!;
  return { background, color };
}
