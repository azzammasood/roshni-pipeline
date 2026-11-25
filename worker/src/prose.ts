// Narration check: port of engine.check_prose (and the regexes in narrate/validate.py). The
// parity cases in tests/fixtures/ask_parity.json are generated from Python; test/prose.test.ts
// asserts this port gives the same problems for every case.

export const PLACEHOLDER = /\{([a-z0-9_]+)\}/g;
const NUMBER = /\d+(?:[.,]\d+)*/g;
const CAUSAL =
  /\b(because|caus(e|es|ed|ing)|due to|result(s|ed)? (in|from)|leads? to|driv(e|es|en|ing) by|discriminat\w*|unfair\w*|punish\w*|deliberate\w*|target(s|ed|ing)?)\b/i;
const NOT_MEASURED =
  /(?<!not )\b(actual(ly)?|really|measured|real)\b|\b(lost|losing|loses|lose)\s+(power|electricity|supply)\b|\b(was|were|went|been)\s+(without power|dark|off)\b/i;
const UNITS = [
  "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
  "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen",
  "nineteen",
];
const TENS = ["twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"];
const WORD = [...UNITS, ...TENS, "hundred", "thousand", "million"].join("|");
const NUMBER_WORDS = new RegExp(
  `\\b(?:(?:${WORD})(?:[\\s-]+(?:and[\\s-]+)?(?:${WORD}))*|half|dozen)\\b`,
  "gi",
);
const LISTS = /^\s*([#|*-]|\d+\.)/m;

const all = (re: RegExp, s: string) => [...s.matchAll(re)].map((m) => m[0]);

/** Python's repr of a list of strings, as in the problem text "unknown placeholders [...]". */
const pyList = (xs: string[]) => `[${xs.map((x) => `'${x}'`).join(", ")}]`;

export function checkProse(text: string, facts: Record<string, string>, question = ""): string[] {
  const problems: string[] = [];
  const ids = [...text.matchAll(PLACEHOLDER)].map((m) => m[1]);
  const unknown = [...new Set(ids.filter((i) => !(i in facts)))].sort();
  if (unknown.length) problems.push(`unknown placeholders ${pyList(unknown.slice(0, 5))}`);
  let bare = text.replace(PLACEHOLDER, "");
  const quoted = [...new Set(all(NUMBER, question))].sort((a, b) => b.length - a.length);
  for (const q of quoted) bare = bare.replaceAll(q, "");
  if (new RegExp(NUMBER.source).test(bare)) problems.push("contains a number not taken from the result");
  const allowed = new Set([...all(NUMBER_WORDS, question).map((w) => w.toLowerCase()), "six", "twelve"]);
  if (all(NUMBER_WORDS, bare).some((w) => !allowed.has(w.toLowerCase())))
    problems.push("contains a number word not in the question");
  if (CAUSAL.test(text)) problems.push("causal or accusatory wording");
  if (NOT_MEASURED.test(text)) problems.push("calls a schedule an actual/measured outage");
  if (LISTS.test(text)) problems.push("lists, headings or tables are not allowed");
  if (!ids.length) problems.push("no values from the result");
  return problems;
}

/** Python's repr of a list of column names, as the narrator prompt shows them. */
export const pyColumns = (cols: string[]) =>
  `[${cols.map((c) => (c.includes("'") && !c.includes('"') ? `"${c}"` : `'${c.replace(/\\/g, "\\\\").replace(/'/g, "\\'")}'`)).join(", ")}]`;
