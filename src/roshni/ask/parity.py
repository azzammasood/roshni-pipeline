"""Parity cases for the TypeScript ports of the answer checks (Worker) and formatting (site).

`tests/fixtures/ask_parity.json` holds inputs with the outcome Python gives; the Worker's and
the site's tests assert the same outcomes, and `test_parity_file_matches_python` fails when the
Python rules change without regenerating it (`uv run python -m roshni.ask.parity`).
"""

import json
from decimal import Decimal
from pathlib import Path

from roshni.ask import engine, evaluate, semantic, sqlguard
from roshni.paths import REPO_ROOT

PARITY_FILE = REPO_ROOT / "tests" / "fixtures" / "ask_parity.json"

FACTS = {"row_count": "2", "r1_ibc": "IBC - A", "r1_share_12h_pct": "90.0", "r2_n": "1,234"}
PROSE = [
    ("{r1_ibc} has the highest share at {r1_share_12h_pct}%.", ""),
    ("{r1_ibc} has 90% of feeders on the long schedule.", ""),
    ("{r1_ibc} is high because of losses.", ""),
    ("{r1_ibc} actually lost power most often.", ""),
    ("These are schedules, not measured outages: {r1_ibc}.", ""),
    ("{r1_ibc} is not actually dark.", ""),
    ("Feeders in {r1_ibc} were without power.", ""),
    ("Feeders in {r1_ibc} went dark at night.", ""),
    ("{r1_ibc} loses electricity daily.", ""),
    ("{r9_ibc} leads.", ""),
    ("Three areas lead, starting with {r1_ibc}.", ""),
    ("Twenty-one feeders, led by {r1_ibc}.", ""),
    ("A dozen feeders, led by {r1_ibc}.", ""),
    ("No values here.", ""),
    ("In 2024-25, the top five start with {r1_ibc}.",
     "Which five areas had the most hours in 2024-25?"),
    ("Six or twelve hours: {r1_ibc} has {r2_n}.", ""),
    ("- {r1_ibc}\n- {r2_n}", ""),
    ("1. {r1_ibc} leads", ""),
    ("## {r1_ibc}", ""),
    ("{r1_ibc} is unfair to the poor.", ""),
    ("{r1_ibc} is targeted.", ""),
    ("Schedules are driven by losses in {r1_ibc}.", ""),
    ("The result shows {r1_ibc} at {r1_share_12h_pct} and {r2_n} feeders.", ""),
    ("{r1_ibc} had 1,234.5 hours and {row_count} rows.", ""),
    ("{r1_ibc} REALLY leads.", ""),
]  # fmt: skip
FMT = [
    10.25, 2452.0, 0.125, 0.0, 1234, None, -3.45, 0.004, 99.95, 1_000_000, 0.5, -0.0, "IBC - A",
    True,
]  # fmt: skip
# SQL guard: the site checks DuckDB's own AST (json_serialize_sql); Python uses sqlglot. Only the
# verdict must agree; the golden reference queries are all included.
SQL = [
    "select ibc, share_12h_pct from mart_ke_ibc_equity order by 2 desc",
    "select count(*) as n from dim_feeder",
    "with x as (select ibc, share_12h_pct s from mart_ke_ibc_equity) select ibc, s from x",
    "select f.ibc, count(*) as n from dim_feeder f where f.source = 'kelectric' group by 1",
    "select company, avg(reported_hours_per_day) as h, count(*) n "
    "from mart_nepra_load_shedding group by 1",
    "drop table dim_feeder",
    "delete from dim_feeder",
    "select 1; select 2",
    "select * from dim_feeder",
    "select f.* from dim_feeder f",
    "select source_file from dim_feeder",
    "select ibc from raw.secrets",
    "select ibc from other.main.dim_feeder",
    "select x from stg_secret_table",
    "select * from read_csv('C:/data.csv')",
    "select ibc from read_parquet('https://example.com/x.parquet')",
    "select getenv('GROQ_API_KEY')",
    "select ibc from mart_ke_ibc_equity union all select current_setting('a')",
    "select ibc from mart_ke_ibc_equity where ibc in (select feeder_name from dim_feeder)",
    "select ibc from mart_ke_ibc_equity where ibc in (select secret from dim_feeder)",
    "attach 'x.db' as x",
    "select from where",
    "copy (select 1) to 'x.csv'",
    "pragma version",
    # used by the site's flow tests (web/src/lib/ask/ask.test.ts)
    "select ibc, share_12h_pct from mart_ke_ibc_equity order by 2 desc limit 1",
    "select source_file from mart_ke_ibc_equity",
    "select ibc from mart_ke_ibc_equity order by 1 limit 1",
    "select ibc from mart_ke_ibc_equity where ibc > 1::date",
    "select ibc from mart_ke_ibc_equity where ibc = 'nowhere'",
]  # fmt: skip
SLUG = ["share_12h_pct", "Share (12h) %", "n", "COUNT(*)", "  ", "Feeder-Name"]


def serialize(sql: str) -> str:
    """DuckDB's parse tree, as the site gets it from json_serialize_sql (DuckDB-WASM cannot load
    the json extension under Node, so the site's tests check the guard on these trees)."""
    import duckdb

    return duckdb.connect().execute("select json_serialize_sql(?::varchar)", [sql]).fetchone()[0]


def cases() -> dict:
    layer = semantic.load()
    golden = [it["sql"] for it in evaluate.load_items() if it["expect"] == "answer"]
    return {
        "facts": FACTS,
        "prose": [
            {"text": t, "question": q, "problems": engine.check_prose(t, FACTS, q)}
            for t, q in PROSE
        ],
        "fmt": [
            {
                "value": v,
                "decimal": isinstance(v, float),
                "shown": engine.fmt(Decimal(str(v)) if isinstance(v, float) else v),
            }
            for v in FMT
        ],
        "slug": [{"text": s, "slug": engine._slug(s)} for s in SLUG],
        "sql": [
            {"sql": q, "ok": sqlguard.check(q, layer).ok, "ast": serialize(q)}
            for q in [*SQL, *golden]
        ],
    }


def write(path: Path = PARITY_FILE) -> Path:
    path.write_text(json.dumps(cases(), indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def oracle(db: Path | None = None) -> Path:
    """Golden reference queries run on the warehouse and formatted by engine.fmt: the site's
    test runs them on the published ask/ Parquet and must get the same rows (local only)."""
    from roshni.paths import DATA_DIR

    con = sqlguard.connect(db or DATA_DIR / "roshni.duckdb")
    out = []
    for it in evaluate.load_items():
        if it["expect"] != "answer":
            continue
        res = sqlguard.run(con, it["sql"])
        out.append({"id": it["id"], "sql": it["sql"], "ast": serialize(it["sql"]),
                    "columns": res.columns,
                    "rows": [[engine.fmt(v) for v in r] for r in res.rows]})  # fmt: skip
    path = DATA_DIR / "oracle" / "ask_golden.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return path


if __name__ == "__main__":
    import sys

    print(oracle() if "--oracle" in sys.argv else write())
