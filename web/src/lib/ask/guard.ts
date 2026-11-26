// SQL guard for the browser: the same rules as sqlguard.check (Python, sqlglot), applied to
// DuckDB's own parse tree (json_serialize_sql). Only SELECT statements serialize, so DDL, DML,
// PRAGMA, ATTACH and COPY fail before these checks. Verdicts are pinned against Python in
// tests/fixtures/ask_parity.json (every golden reference query included).

export type Allow = { tables: Record<string, { columns: string[] }>; blocked: string[] };
export type Verdict = { ok: boolean; problems: string[]; tables: string[] };

type Node = Record<string, unknown>;
const isNode = (v: unknown): v is Node => typeof v === "object" && v !== null && !Array.isArray(v);

function walk(v: unknown, visit: (n: Node) => void) {
  if (Array.isArray(v)) v.forEach((x) => walk(x, visit));
  else if (isNode(v)) {
    visit(v);
    for (const x of Object.values(v)) walk(x, visit);
  }
}

export function checkAst(serialized: string, allow: Allow): Verdict {
  let tree: Node;
  try {
    tree = JSON.parse(serialized);
  } catch {
    return { ok: false, problems: ["does not parse"], tables: [] };
  }
  if (tree.error) {
    const msg = String(tree.error_message ?? "");
    return { ok: false, problems: [/only select/i.test(msg) ? "only SELECT queries are allowed" : `does not parse: ${msg.slice(0, 150)}`], tables: [] };
  }
  const statements = Array.isArray(tree.statements) ? tree.statements : [];
  if (statements.length !== 1) return { ok: false, problems: [`expected exactly one statement, got ${statements.length}`], tables: [] };

  const problems: string[] = [];
  const ctes = new Set<string>();
  const aliases = new Set<string>();
  const used = new Set<string>();
  const columns: string[] = [];

  walk(statements, (n) => {
    const map = isNode(n.cte_map) && Array.isArray(n.cte_map.map) ? n.cte_map.map : [];
    for (const e of map) {
      if (!isNode(e)) continue;
      ctes.add(String(e.key).toLowerCase());
      const v = e.value;
      if (isNode(v) && Array.isArray(v.aliases)) v.aliases.forEach((a) => aliases.add(String(a).toLowerCase()));
    }
    if (n.class !== undefined && typeof n.alias === "string" && n.alias) aliases.add(n.alias.toLowerCase());
    if (Array.isArray(n.column_name_alias)) n.column_name_alias.forEach((a) => aliases.add(String(a).toLowerCase()));
  });

  walk(statements, (n) => {
    if (n.type === "BASE_TABLE") {
      const name = String(n.table_name).toLowerCase();
      const schema = String(n.schema_name ?? "").toLowerCase();
      if (n.catalog_name || (schema && schema !== "main")) problems.push(`schema-qualified table not allowed: ${name}`);
      else if (ctes.has(name)) return;
      else if (!(name in allow.tables)) problems.push(`table not in semantic layer: ${name}`);
      else used.add(name);
    } else if (n.type === "TABLE_FUNCTION") {
      problems.push("table functions are not allowed");
    } else if (n.class === "FUNCTION" || n.class === "AGGREGATE" || n.class === "WINDOW") {
      const f = String(n.function_name ?? "").toLowerCase();
      if (allow.blocked.some((p) => f.startsWith(p))) problems.push(`function not allowed: ${f}`);
    } else if (n.class === "STAR") {
      problems.push("SELECT * is not allowed; name the columns");
    } else if (n.class === "COLUMN_REF" && Array.isArray(n.column_names) && n.column_names.length) {
      columns.push(String(n.column_names.at(-1)).toLowerCase());
    }
  });

  const allowed = new Set([...used].flatMap((t) => allow.tables[t].columns.map((c) => c.toLowerCase())));
  const scope = used.size ? JSON.stringify([...used].sort()) : "these tables";
  for (const c of columns) if (!allowed.has(c) && !aliases.has(c)) problems.push(`column not allowed for ${scope}: ${c}`);

  const unique = [...new Set(problems)];
  return { ok: unique.length === 0, problems: unique, tables: [...used].sort() };
}
