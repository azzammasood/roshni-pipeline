// Translation checks (CI, after sync-data):
//  1. every dictionary has exactly the keys of en.json, with the same {placeholders};
//  2. no leftover English words in non-English dictionaries (allow-list below);
//  3. safety text from the export (labels, disclaimer, scope note, NEPRA basis and caveat) has a
//     translation, and every other fixed export string is reported if it would show in English.
import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const webDir = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const read = async (p) => JSON.parse(await readFile(path.join(webDir, p), "utf8"));
const en = await read("src/i18n/en.json");
const LOCALES = ["ur"];
const ALLOWED_LATIN = new Set(["UTC", "HTTP", "English", "rho", "Last-Modified", "iesco.com.pk", "ke.com.pk"]);

const leaves = (obj, prefix = "") =>
  Object.entries(obj).flatMap(([k, v]) =>
    v && typeof v === "object" ? leaves(v, `${prefix}${k}.`) : [[`${prefix}${k}`, String(v)]],
  );
const placeholders = (s) => [...s.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort().join(",");
const problems = [];
const warnings = [];

const enLeaves = new Map(leaves(en));
for (const locale of LOCALES) {
  const dict = new Map(leaves(await read(`src/i18n/${locale}.json`)));
  for (const k of enLeaves.keys()) if (!dict.has(k)) problems.push(`${locale}: missing key ${k}`);
  for (const [k, v] of dict) {
    if (!enLeaves.has(k)) problems.push(`${locale}: extra key ${k}`);
    else if (placeholders(v) !== placeholders(enLeaves.get(k)))
      problems.push(`${locale}: ${k} placeholders {${placeholders(v)}} differ from en {${placeholders(enLeaves.get(k))}}`);
    const words = v.replace(/\{\w+\}/g, " ").match(/[A-Za-z][A-Za-z.&-]+/g) ?? [];
    for (const w of words) if (w.length > 1 && !ALLOWED_LATIN.has(w)) problems.push(`${locale}: ${k} has English "${w}"`);
  }

  // Fixed English text that the export puts on pages.
  const exportText = await read(`src/i18n/export-text.${locale}.json`);
  const data = async (doc) => read(`public/data/v1/${doc}.json`);
  const meta = await data("meta");
  const equity = await data("equity");
  const national = await data("national");
  const news = await data("news");
  const required = [
    meta.label,
    meta.data.disclaimer,
    equity.data.scope_note,
    // NEPRA figures: what they are and the regulator's own caveat (reported, not measured).
    national.label,
    news.label,
    // NEPRA's order on K-Electric: what the figures are (regulator's analysis, period not stated).
    ...(equity.data.regulator_review ? [equity.data.regulator_review.basis] : []),
    national.data.basis,
    national.data.caveat,
    ...national.data.gaps,
  ];
  const optional = [...meta.data.attribution, ...meta.data.sources.map((s) => s.effective_basis)];
  for (const s of new Set(required)) if (!exportText[s]) problems.push(`${locale}: no translation for required export text "${s}"`);
  for (const s of new Set(optional)) if (!exportText[s]) warnings.push(`${locale}: export text shown in English: "${s}"`);
}

for (const w of warnings) console.warn(`warning: ${w}`);
if (problems.length) {
  console.error(problems.map((p) => `  - ${p}`).join("\n"));
  process.exit(1);
}
console.log(`i18n ok: ${enLeaves.size} keys x ${LOCALES.length + 1} locales, export text covered`);
