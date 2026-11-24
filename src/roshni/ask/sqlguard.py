"""SQL guard: an LLM-written query runs only if it is one read-only SELECT over the semantic layer.

Checks (parsed with sqlglot, DuckDB dialect), all must pass:
- exactly one statement, and it is a query (SELECT / UNION / ...), with no DDL/DML anywhere;
- every table is an allowlisted table or a CTE defined in the query; no schema other than main,
  no table functions (read_csv, glob, ...), no blocked functions (getenv, pragma_*, ...);
- every column is allowlisted for the tables used, or an alias/CTE name defined in the query;
- no `SELECT *` (only `count(*)`).
Execution then adds defence in depth: read-only connection, external access disabled, a row cap
and a timeout (see `run`).
"""

import threading
from dataclasses import dataclass, field
from pathlib import Path

import duckdb
import sqlglot
from sqlglot import exp

from roshni.ask.semantic import SemanticLayer

MAX_ROWS = 200
TIMEOUT_S = 10.0
BLOCKED_FUNC_PREFIXES = (
    "read_", "glob", "getenv", "pragma", "duckdb_", "current_setting", "query", "sniff_",
    "parquet_", "iceberg", "delta_", "http", "load", "install", "attach", "copy", "export",
    "import", "system", "shell", "set_", "sqlite_", "postgres_", "mysql_",
)  # fmt: skip
_FORBIDDEN = tuple(
    getattr(exp, n)
    for n in (
        "Insert", "Update", "Delete", "Merge", "Drop", "Create", "Alter", "Command", "Pragma",
        "Set", "Use", "Copy", "Attach", "Detach", "Install", "Export", "Transaction", "Commit",
        "Rollback", "LoadData",
    )
    if hasattr(exp, n)
)  # fmt: skip


@dataclass
class Checked:
    ok: bool
    problems: list[str] = field(default_factory=list)
    tables: set[str] = field(default_factory=set)
    sql: str = ""


def check(sql: str, layer: SemanticLayer) -> Checked:
    try:
        stmts = [s for s in sqlglot.parse(sql, read="duckdb") if s is not None]
    except sqlglot.errors.ParseError as e:
        return Checked(False, [f"does not parse: {str(e).splitlines()[0][:150]}"])
    if len(stmts) != 1:
        return Checked(False, [f"expected exactly one statement, got {len(stmts)}"])
    tree = stmts[0]
    problems: list[str] = []
    if not isinstance(tree, exp.Query):
        problems.append(f"only SELECT queries are allowed, got {tree.key.upper()}")
    for node in tree.walk():
        if isinstance(node, _FORBIDDEN):
            problems.append(f"forbidden statement {node.key.upper()}")

    ctes = {c.alias_or_name.lower() for c in tree.find_all(exp.CTE)}
    used: set[str] = set()
    for t in tree.find_all(exp.Table):
        if not isinstance(t.this, exp.Identifier):
            problems.append(f"table functions are not allowed ({t.sql()[:60]})")
            continue
        name = t.name.lower()
        if t.args.get("catalog") or (t.db and t.db.lower() != "main"):
            problems.append(f"schema-qualified table not allowed: {t.sql()}")
        elif name in ctes:
            continue
        elif name not in layer.tables:
            problems.append(f"table not in semantic layer: {name}")
        else:
            used.add(name)

    for f in tree.find_all(exp.Func):
        fname = (f.name if isinstance(f, exp.Anonymous) else f.sql_name()).lower()
        if fname.startswith(BLOCKED_FUNC_PREFIXES):
            problems.append(f"function not allowed: {fname}")

    aliases = {a.alias.lower() for a in tree.find_all(exp.Alias) if a.alias}
    aliases |= {
        c.name.lower() for ta in tree.find_all(exp.TableAlias) for c in ta.args.get("columns") or []
    }
    allowed = {c.lower() for c in layer.allowed_columns(used)}
    for col in tree.find_all(exp.Column):
        name = col.name.lower()
        if isinstance(col.this, exp.Star):
            problems.append("SELECT * is not allowed; name the columns")
        elif name not in allowed and name not in aliases:
            problems.append(f"column not allowed for {sorted(used) or 'these tables'}: {name}")
    for star in tree.find_all(exp.Star):
        if not isinstance(star.parent, exp.Count | exp.Column):
            problems.append("SELECT * is not allowed; name the columns")

    problems = list(dict.fromkeys(problems))
    return Checked(not problems, problems, used, tree.sql(dialect="duckdb"))


@dataclass
class Result:
    columns: list[str]
    rows: list[tuple]
    truncated: bool


def connect(db_path: Path) -> duckdb.DuckDBPyConnection:
    """Read-only warehouse connection with external file/network access switched off."""
    return duckdb.connect(str(db_path), read_only=True, config={"enable_external_access": False})


def run(con: duckdb.DuckDBPyConnection, sql: str, timeout_s: float = TIMEOUT_S) -> Result:
    timer = threading.Timer(timeout_s, con.interrupt)
    timer.start()
    try:
        cur = con.execute(sql)
        cols = [d[0] for d in cur.description]
        rows = cur.fetchmany(MAX_ROWS + 1)
    finally:
        timer.cancel()
    return Result(cols, rows[:MAX_ROWS], len(rows) > MAX_ROWS)
