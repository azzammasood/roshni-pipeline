// Port of engine.fmt / engine._slug / engine.facts_from for answers computed in the browser.
// Values arrive as DuckDB's own text (see runner.ts: every column is cast to VARCHAR, so DECIMAL
// stays exact) plus a kind; tests/fixtures/ask_parity.json pins the Python results.

export type Kind = "decimal" | "int" | "bool" | "ts" | "text";

const PKT_MS = 5 * 3_600_000;

/** Plain digits for a number written with an exponent ("1e-05" -> "0.00001"). */
function plain(text: string): string {
  const m = /^(-?)(\d+)(?:\.(\d*))?e([+-]?\d+)$/i.exec(text);
  if (!m) return text;
  const [, sign, int, frac = "", expText] = m;
  const exp = Number(expText);
  const digits = int + frac;
  let point = int.length + exp;
  let out: string;
  if (point <= 0) out = "0." + "0".repeat(-point) + digits;
  else if (point >= digits.length) out = digits + "0".repeat(point - digits.length);
  else out = digits.slice(0, point) + "." + digits.slice(point);
  point = 0;
  return sign + out.replace(/^0+(?=\d)/, "");
}

const group = (int: string) => int.replace(/\B(?=(\d{3})+(?!\d))/g, ",");

/** Half-up (away from zero) to 1 place when |v| >= 1 or v == 0, else 2 places; then grouped. */
export function roundHalfUp(text: string): string {
  const t = plain(text.trim());
  const m = /^(-?)(\d*)(?:\.(\d*))?$/.exec(t);
  if (!m || (!m[2] && !m[3])) return text; // inf, nan: shown as they are
  const sign = m[1];
  const int = (m[2] || "0").replace(/^0+(?=\d)/, "");
  const frac = m[3] ?? "";
  const zero = /^0*$/.test(int + frac);
  const places = int !== "0" || zero ? 1 : 2;
  const keep = (frac + "0".repeat(places + 1)).slice(0, places);
  const next = (frac + "0".repeat(places + 1))[places];
  let digits = (int + keep).split("").map(Number);
  if (Number(next) >= 5) {
    let i = digits.length - 1;
    while (i >= 0) {
      if (digits[i] < 9) {
        digits[i]++;
        break;
      }
      digits[i] = 0;
      i--;
    }
    if (i < 0) digits = [1, ...digits];
  }
  const all = digits.join("");
  const intOut = all.slice(0, all.length - places) || "0";
  const fracOut = all.slice(all.length - places);
  const isZero = /^0*$/.test(intOut + fracOut);
  return `${sign && !isZero ? "-" : ""}${group(intOut)}.${fracOut}`;
}

const pad = (n: number) => String(n).padStart(2, "0");

export function fmt(text: string | null, kind: Kind): string {
  if (text === null) return "null";
  switch (kind) {
    case "decimal":
      return roundHalfUp(text);
    case "int": {
      const neg = text.startsWith("-");
      return (neg ? "-" : "") + group(neg ? text.slice(1) : text);
    }
    case "ts": {
      const d = new Date(Number(text) + PKT_MS);
      return `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())} ${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())} PKT`;
    }
    default:
      return text;
  }
}

export const slug = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "") || "col";

/** row_count plus r<i>_<column> for the first rows, exactly as engine.facts_from names them. */
export function factsFrom(columns: string[], rows: string[][], maxRows: number): Record<string, string> {
  const facts: Record<string, string> = { row_count: fmt(String(rows.length), "int") };
  rows.slice(0, maxRows).forEach((row, i) => {
    columns.forEach((c, j) => {
      facts[`r${i + 1}_${slug(c)}`] = row[j];
    });
  });
  return facts;
}

const PLACEHOLDER = /\{([a-z0-9_]+)\}/g;
export const render = (text: string, facts: Record<string, string>) =>
  text.replace(PLACEHOLDER, (m, id: string) => facts[id] ?? m).trim().split(/\s+/).join(" ");
