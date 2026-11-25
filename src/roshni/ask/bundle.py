"""Ask Roshni on the website: the static bundle the browser and the Worker read (export ask/).

- `<table>.parquet` per semantic-layer table, allowlisted columns only: the browser runs the
  planner's SQL on these with DuckDB-WASM, so no server ever runs a query.
- `context.json`: the planner and narrator prompts (the same text `roshni ask` uses, built here
  so there is one source), the feedback texts, the allowlist and caveats for the browser's SQL
  guard, and the limits. The Worker fetches it from the site; it never takes a prompt from the
  browser.
"""

import json
from pathlib import Path

import duckdb

from roshni.ask import engine, semantic, sqlguard

BUNDLE_VERSION = 1


def build_bundle(
    con: duckdb.DuckDBPyConnection, out: Path, layer: semantic.SemanticLayer | None = None
) -> dict:
    layer = layer or semantic.load()
    out.mkdir(parents=True, exist_ok=True)
    tables = {}
    for t in layer.tables.values():
        cols = ", ".join(f'"{c}"' for c in t.columns)  # allowlisted names only
        path = out / f"{t.name}.parquet"
        con.execute(
            f"copy (select {cols} from {t.name}) to '{path.as_posix()}' "
            "(format parquet, compression zstd)"
        )
        (rows,) = con.execute(f"select count(*) from {t.name}").fetchone()
        tables[t.name] = {
            "file": path.name,
            "rows": rows,
            "columns": list(t.columns),
            "caveats": t.caveats,
        }
    context = {
        "bundle_version": BUNDLE_VERSION,
        "built_at": engine.built_at(con),
        "planner_system": engine.PLANNER.format(context=layer.prompt_context(con)),
        "narrator_system": engine.NARRATOR,
        "feedback": {
            "error": engine.FEEDBACK_ERROR,
            "empty": engine.FEEDBACK_EMPTY,
            "guard": engine.FEEDBACK_GUARD,
        },
        "tables": tables,
        "blocked_function_prefixes": list(sqlguard.BLOCKED_FUNC_PREFIXES),
        "max_rows": sqlguard.MAX_ROWS,
        "max_fact_rows": engine.MAX_FACT_ROWS,
        "max_question_chars": 500,
    }
    (out / "context.json").write_text(json.dumps(context, ensure_ascii=False), encoding="utf-8")
    return context
