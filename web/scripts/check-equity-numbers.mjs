// F3 gate, kept as a CI check: every number shown in the main content of the built equity page
// must come from equity.json (a value, or a number inside one of its strings), from a sum of its
// rows listed below, or from a named UI constant. Dates must be dates present in the export.
// Usage (after `npm run build`): node scripts/check-equity-numbers.mjs [--locale en]
import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const webDir = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const args = process.argv.slice(2);
const locale = args.includes("--locale") ? args[args.indexOf("--locale") + 1] : "en";
const html = await readFile(path.join(webDir, "out", locale, "karachi-equity", "index.html"), "utf8");
const load = async (doc) =>
  JSON.parse(await readFile(path.join(webDir, "public", "data", "v1", `${doc}.json`), "utf8"));
const equity = (await load("equity")).data;
const meta = (await load("meta")).data;

const DATE = /\b\d{4}-\d{2}-\d{2}\b|\b\d{4}-W\d{2}\b/g;
const NUMBER = /-?\d[\d,]*(?:\.\d+)?/g;
const toNum = (s) => Number(s.replaceAll(",", ""));

// Allowed values, each with where it comes from.
const allowed = new Map();
const allow = (v, why) => allowed.has(v) || allowed.set(v, why);
const dates = new Set();
(function walk(node, where) {
  if (typeof node === "number") allow(node, where);
  else if (typeof node === "string") {
    for (const d of node.match(DATE) ?? []) dates.add(d);
    for (const m of node.replace(DATE, " ").match(NUMBER) ?? []) allow(toNum(m), `${where} (in text)`);
  } else if (node && typeof node === "object") {
    for (const [k, v] of Object.entries(node)) walk(v, Array.isArray(node) ? where : `${where}.${k}`);
  }
})(equity, "equity");
for (const s of meta.sources) if (s.source === "kelectric_schedule") dates.add(s.effective_from);
// The report's ISO week is shown as the date of its Monday ("week of 2026-10-12").
const isoWeekMonday = (week) => {
  const [, y, w] = /^(\d{4})-W(\d{2})$/.exec(week);
  const jan4 = Date.UTC(Number(y), 0, 4);
  const monday = jan4 - ((new Date(jan4).getUTCDay() + 6) % 7) * 86400000;
  return new Date(monday + (Number(w) - 1) * 7 * 86400000).toISOString().slice(0, 10);
};
for (const d of [...dates]) if (/W/.test(d)) dates.add(isoWeekMonday(d));

const sum = (rows, key) => rows.reduce((a, r) => a + r[key], 0);
const derived = {
  "sum ibc.listed_feeders": sum(equity.ibc, "listed_feeders"),
  "sum ibc.scheduled_feeders": sum(equity.ibc, "scheduled_feeders"),
  "sum ibc.feeders_12h": sum(equity.ibc, "feeders_12h"),
  "sum ibc.feeders_6h": sum(equity.ibc, "feeders_6h"),
  "count ibc": equity.ibc.length,
  "sum subdivisions.ibcs": sum(equity.subdivisions, "ibcs"),
  "count subdivisions": equity.subdivisions.length,
};
for (const [why, v] of Object.entries(derived)) allow(v, `derived: ${why}`);
// UI constants, written in the page's own text.
const constants = {
  6: "K-Electric 6-hour schedule band",
  12: "K-Electric 12-hour schedule band",
  10: "small-n threshold (MIN_N, same as the weekly report)",
  1: "rho range -1 to 1",
  [-1]: "rho range -1 to 1",
  50: "skyline chart gridline (50%), axis label only",
  100: "skyline chart gridline (100%), axis label only",
};
for (const [v, why] of Object.entries(constants)) allow(Number(v), `constant: ${why}`);

// Text of <main>, without scripts, tags or entities.
const main = html.slice(html.indexOf("<main"), html.indexOf("</main>"));
const text = main
  .replace(/<script[\s\S]*?<\/script>/g, " ")
  .replace(/<[^>]+>/g, " ")
  .replace(/&amp;/g, "&")
  .replace(/&[a-z#0-9]+;/gi, " ");

const problems = [];
const shownDates = text.match(DATE) ?? [];
for (const d of shownDates) if (!dates.has(d)) problems.push(`date ${d} is not in the export`);
const shown = (text.replace(DATE, " ").match(NUMBER) ?? []).map((s) => [s, toNum(s)]);
const sources = new Map();
for (const [raw, v] of shown) {
  const hit = [...allowed.keys()].find((a) => Math.abs(a - v) < 1e-9);
  if (hit === undefined) problems.push(`number ${raw} is not traceable to equity.json`);
  else {
    const kind = allowed.get(hit).split(":")[0].startsWith("equity") ? "export" : allowed.get(hit).split(":")[0];
    sources.set(kind, (sources.get(kind) ?? 0) + 1);
  }
}

console.log(
  `equity page (${locale}): ${shown.length} numbers, ${new Set(shown.map(([, v]) => v)).size} distinct, ` +
    `${shownDates.length} dates; by origin: ${[...sources].map(([k, n]) => `${k}=${n}`).join(", ")}`,
);
if (shown.length < 100) problems.push(`only ${shown.length} numbers found: is the page empty?`);
if (problems.length) {
  console.error(problems.map((p) => `  - ${p}`).join("\n"));
  process.exit(1);
}
console.log("every number and date is traceable to the export");
