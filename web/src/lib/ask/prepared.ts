// Answers prepared once a day by the publish job (`roshni ask-prepared`, export ask/prepared.json):
// the same engine and checks as a live question, shown without calling the Worker, so examples,
// the equity page's "Explain this" links and the busy fallback cost visitors nothing.
import type { Answer } from "./session";

export type PreparedItem = {
  id: string;
  tag: string;
  question: string;
  answer: string;
  narrated: boolean;
  model: string;
  sql: string | null;
  columns: string[];
  rows: string[][];
  truncated: boolean;
  tables: string[];
  caveats: string[];
  tokens: number;
};
export type Prepared = { generated_at: string; built_at: string | null; items: PreparedItem[] };

const URL_ = `${process.env.NEXT_PUBLIC_BASE_PATH ?? ""}/data/v1/ask/prepared.json`;

let cache: Promise<Prepared | null> | null = null;

export function loadPrepared(): Promise<Prepared | null> {
  cache ??= fetch(URL_)
    .then((r) => (r.ok ? (r.json() as Promise<Prepared>) : null))
    .catch(() => null);
  return cache;
}

export function toAnswer(p: PreparedItem, builtAt: string | null): Answer {
  return {
    question: p.question,
    status: "answered",
    answer: p.answer,
    narrated: p.narrated,
    sql: p.sql,
    columns: p.columns,
    rows: p.rows,
    truncated: p.truncated,
    tables: p.tables,
    caveats: p.caveats,
    n: p.rows.length,
    reason: "",
    models: p.model ? [p.model] : [],
    attempts: [],
    trace: [],
    prepared: builtAt ?? "",
  };
}
