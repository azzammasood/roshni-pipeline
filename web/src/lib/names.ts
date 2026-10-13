// Display-only name tidying. Stored and exported names stay exactly as published; feeder and grid
// names are shown as published (they are full of acronyms such as RMU, KDA, PECHS and are what
// people match against posted lists), so only these two kinds of name are re-cased.

/** IESCO circle ids (as exported) -> circle names. */
const CIRCLES: Record<string, string> = {
  ajk: "AJK",
  attock: "Attock",
  chakwal: "Chakwal",
  islamabad: "Islamabad",
  jhelum: "Jhelum",
  rawalpindi: "Rawalpindi",
};

export function circleName(id: string | null | undefined): string | null {
  if (!id) return null;
  return CIRCLES[id] ?? id;
}

// Census names are plain words in capitals; these are the acronyms among them.
const KEEP = new Set(["SITE", "AJK", "ICT", "II", "III", "IV"]);

/** "NORTH NAZIMABAD SUB-DIVISION" -> "North Nazimabad Sub-division" (census names only). */
export function censusName(name: string): string {
  if (name !== name.toUpperCase()) return name;
  return name.replace(/[A-Z]+/g, (word, offset: number) => {
    if (KEEP.has(word)) return word;
    const afterHyphen = offset > 0 && name[offset - 1] === "-";
    return afterHyphen ? word.toLowerCase() : word[0] + word.slice(1).toLowerCase();
  });
}

/** K-Electric IBC names are published as "IBC - Clifton"; the column or label already says IBC. */
export function ibcName(name: string): string {
  return name.replace(/^IBC\s*-\s*/, "");
}
