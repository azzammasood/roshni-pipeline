"""Roshni as an MCP server (`roshni mcp`, stdio): any MCP client (Claude Desktop, an IDE, an
agent) can list Roshni's published tables and run read-only SQL on them. The client brings its
own model; this server calls none, so it costs no Groq tokens.

Data: the site's own Ask Roshni bundle (`<site>/data/v1/ask/`: context.json + one Parquet file
per semantic-layer table), downloaded once a day into a cache folder with a fixed User-Agent and
one request a second, or a local export folder (`--bundle`). The tables are loaded into an
in-memory DuckDB, then file and network access is switched off. Every query goes through the
same SQL guard as Ask Roshni (one SELECT, allowlisted tables and columns, no table functions,
200 rows), and every result carries the tables' caveats and the "schedules, not measured
outages" label.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

import duckdb

from roshni.ask import engine, semantic, sqlguard
from roshni.fetch.http import PoliteClient
from roshni.paths import CONFIG_DIR, DATA_DIR, REPO_ROOT

SITE = "https://azzammasood.github.io/roshni-site/data/v1/ask"
UA = "roshni-pipeline/0.1 (+https://github.com/azzammasood/roshni-pipeline)"
LABEL = "Scheduled (published schedule data), not measured outages."


def fetch_bundle(cache: Path, base: str = SITE) -> Path:
    """The site's bundle in `cache/<UTC date>/`, fetched once a day with the pipeline's polite
    client (fixed User-Agent, robots.txt, one request a second)."""
    day = cache / datetime.now(UTC).strftime("%Y-%m-%d")
    if (day / "context.json").exists():
        return day
    day.mkdir(parents=True, exist_ok=True)
    with PoliteClient(UA, 1.0, 60) as c:
        ctx = c.get(f"{base}/context.json").raise_for_status().content
        for t in json.loads(ctx)["tables"].values():
            (day / t["file"]).write_bytes(c.get(f"{base}/{t['file']}").raise_for_status().content)
    (day / "context.json").write_bytes(ctx)  # last, so a partial download is fetched again
    return day


def default_cache() -> Path:
    """data/mcp-cache in a checkout; the user's cache folder when installed with uvx."""
    if (REPO_ROOT / "pyproject.toml").exists():
        return DATA_DIR / "mcp-cache"
    return Path.home() / ".cache" / "roshni-mcp"


def layer_from_context(ctx: dict) -> semantic.SemanticLayer:
    """The allowlist from the bundle itself, for an install without config/ (uvx): the same
    tables and columns the site's guard allows; descriptions are in the schema notes."""
    tables = {
        name: semantic.Table(
            name=name,
            description="",
            note="",
            columns={c: semantic.Column(c) for c in t["columns"]},
            caveats=list(t.get("caveats", [])),
        )
        for name, t in ctx["tables"].items()
    }
    return semantic.SemanticLayer(rules=[], tables=tables)


def open_bundle(folder: Path) -> tuple[duckdb.DuckDBPyConnection, dict]:
    ctx = json.loads((folder / "context.json").read_text(encoding="utf-8"))
    con = duckdb.connect()
    for name, t in ctx["tables"].items():
        path = (folder / t["file"]).as_posix()
        con.execute(f"create table \"{name}\" as select * from read_parquet('{path}')")
    con.execute("set enable_external_access = false")
    return con, ctx


class Roshni:
    """The tools, independent of the MCP library (tested directly)."""

    def __init__(self, con: duckdb.DuckDBPyConnection, ctx: dict, layer=None):
        self.con, self.ctx = con, ctx
        if layer is None:
            have_config = (CONFIG_DIR / "semantic_layer.yml").exists()
            layer = semantic.load() if have_config else layer_from_context(ctx)
        self.layer = layer

    def schema_notes(self) -> str:
        """The planner's description of every table, column and rule (from the bundle)."""
        return self.ctx.get("planner_system", "")

    def list_tables(self) -> list[dict]:
        out = []
        for name, t in self.layer.tables.items():
            if name not in self.ctx["tables"]:
                continue
            out.append({
                "table": name,
                "description": t.description,
                "rows": self.ctx["tables"][name].get("rows"),
                "columns": {c.name: c.description for c in t.columns.values()},
                "caveats": t.caveats,
            })  # fmt: skip
        return out

    def query(self, sql: str) -> dict:
        checked = sqlguard.check(sql, self.layer)
        if not checked.ok:
            return {"ok": False, "problems": checked.problems}
        try:
            res = sqlguard.run(self.con, checked.sql)
        except Exception as e:  # noqa: BLE001 - a DuckDB error is the caller's to fix
            return {"ok": False, "problems": [str(e).splitlines()[0][:300]]}
        return {
            "ok": True,
            "columns": res.columns,
            "rows": [[engine.fmt(v) for v in r] for r in res.rows],
            "truncated": res.truncated,
            "caveats": self.layer.caveats_for(checked.tables),
            "label": LABEL,
            "data_built_at": self.ctx.get("built_at"),
        }


def serve(tools: Roshni) -> None:
    from mcp.server.mcpserver import MCPServer

    server = MCPServer(
        name="roshni",
        title="Roshni: Pakistan load-shedding schedules",
        instructions=(
            "Published load-shedding schedules (IESCO, K-Electric), NEPRA-reported hours and "
            "Karachi census indicators. Call list_tables first, then query with one SELECT. "
            "These are schedules and reported figures, never measured outages; describe them "
            "without causal claims, and give n."
        ),
    )

    @server.tool(description="Roshni's tables: description, rows, columns and caveats.")
    def list_tables() -> list[dict]:
        return tools.list_tables()

    @server.tool(description="Every table and column described, with the rules for using them.")
    def schema_notes() -> str:
        return tools.schema_notes()

    @server.tool(description="Run one read-only SELECT on Roshni's tables (max 200 rows).")
    def query(sql: str) -> dict:
        return tools.query(sql)

    server.run("stdio")
