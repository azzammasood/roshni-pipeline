/** Replace {name} placeholders. Numbers are formatted for the locale. Safe on client and server. */
export function fill(template: string, values: Record<string, string | number>, locale: string) {
  return template.replace(/\{(\w+)\}/g, (_, key: string) => {
    const v = values[key];
    if (v === undefined) throw new Error(`missing value for {${key}} in "${template}"`);
    return typeof v === "number" ? v.toLocaleString(locale) : v;
  });
}
