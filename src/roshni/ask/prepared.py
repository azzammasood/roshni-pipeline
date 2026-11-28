"""Answers prepared once a day (`roshni ask-prepared`, in publish): the site's example questions
and the equity page's "Explain this" questions, answered by the same engine and checks as a
visitor's question and written to the export as ask/prepared.json. The site shows them without
calling the Worker, so they cost visitors nothing and still work when the free models are busy.
Only answers that match their golden reference are written (every prepared question is a
golden item: its result must equal the reference query's, the eval's execution match). A
mismatch or failure leaves that question to be asked live.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import yaml

from roshni.ask import engine, evaluate, semantic, sqlguard
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
    reference=None,
) -> dict:
    layer = layer or semantic.load()
    golden = {g["question"]: g for g in evaluate.load_items(paraphrases=False)}
    reference = reference or (lambda sql: sqlguard.run(con, sqlguard.check(sql, layer).sql))
    out = []
    for it in items:
        res = ask(it["question"], con, cfg, layer)
        ok = False
        if res.status == "answered":
            g = golden.get(it["question"])
            ref = reference(g["sql"]) if g and g.get("sql") else None
            ok = ref is not None and evaluate.matches(
                ref.columns, ref.rows, res.columns, res.rows, bool(g.get("ordered"))
            )
        log(f"  {res.status:8} {'match' if ok else 'DROPPED'} {res.tokens:5} tok {it['id']}")
        if ok:
            e = entry(it, res)
            if cfg is not None:  # the Urdu page's sentence, under the Urdu check (~500 tokens)
                ur, _model = engine.narrate_ur(res.question, res, cfg)
                if ur:
                    e["answer_ur"] = ur
            out.append(e)
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
