"""Answers prepared once a day (`roshni ask-prepared`, in publish): the site's example questions
and the equity page's "Explain this" questions, answered by the same engine and checks as a
visitor's question and written to the export as ask/prepared.json. The site shows them without
calling the Worker, so they cost visitors nothing and still work when the free models are busy.
Only answered questions are written; a failure leaves that question to be asked live.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import yaml

from roshni.ask import engine, semantic
from roshni.llm.chain import ChainConfig
from roshni.paths import CONFIG_DIR

PREPARED = CONFIG_DIR / "ask_prepared.yml"


def load(path: Path = PREPARED) -> list[dict]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))["items"]


def entry(item: dict, res: engine.AskResult) -> dict:
    return {
        "id": item["id"],
        "tag": item.get("tag", ""),
        "question": res.question,
        "answer": res.answer,
        "narrated": res.narrated_by != "template",
        "model": res.narrated_by if res.narrated_by != "template" else "",
        "sql": res.sql,
        "columns": res.columns,
        "rows": [[engine.fmt(v) for v in r] for r in res.rows],
        "truncated": res.truncated,
        "tables": res.tables,
        "caveats": res.caveats,
        "tokens": res.tokens,
    }


def prepare(
    con: duckdb.DuckDBPyConnection,
    cfg: ChainConfig,
    items: list[dict],
    layer: semantic.SemanticLayer | None = None,
    ask=engine.ask,
    log=print,
) -> dict:
    layer = layer or semantic.load()
    out = []
    for it in items:
        res = ask(it["question"], con, cfg, layer)
        log(f"  {res.status:8} {res.tokens:5} tok {it['id']}")
        if res.status == "answered":
            out.append(entry(it, res))
    return {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "built_at": engine.built_at(con),
        "items": out,
    }


def write(doc: dict, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "prepared.json"
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    return path
