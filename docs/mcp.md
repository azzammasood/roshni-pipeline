# Roshni over MCP

`roshni mcp` serves Roshni's published tables to any Model Context Protocol client (Claude
Desktop, an IDE, an agent) over stdio. The client brings its own model; the server calls none,
so it costs no Groq tokens and needs no key.

## Tools

| Tool | What it does |
|---|---|
| `list_tables` | Every semantic-layer table with its description, row count, columns and caveats. |
| `schema_notes` | The planner's description of every table, column and rule, from the bundle. |
| `query(sql)` | One read-only SELECT, checked by the same SQL guard as Ask Roshni (allowlisted tables and columns, no table functions, no `SELECT *`, 200 rows). Returns columns, rows, the tables' caveats, the data build time and the label "Scheduled (published schedule data), not measured outages." |

## Data

By default the server downloads the site's Ask Roshni bundle
(`https://azzammasood.github.io/roshni-site/data/v1/ask/`: `context.json` and one Parquet file per
table) once a day into `data/mcp-cache/<date>/`, with the pipeline's polite client (fixed
User-Agent, robots.txt, one request a second). `--bundle DIR` uses a local export instead. The
tables are loaded into an in-memory DuckDB and then file and network access is switched off, so a
query can only read those tables.

## Use it

Without cloning (uv installs it in a throwaway environment; the allowlist then comes from the
bundle itself, and the cache is `~/.cache/roshni-mcp`):

```
uvx --from git+https://github.com/azzammasood/roshni-pipeline --with "mcp>=1.20" roshni mcp
```

In a checkout:

```
uv sync --group mcp
uv run --group mcp roshni mcp
```

Claude Desktop (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "roshni": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/roshni-pipeline", "--group", "mcp", "roshni", "mcp"]
    }
  }
}
```

The same rules apply as on the site: these are schedules and reported figures, never measured
outages; describe them without causal claims and give n. The server's instructions tell the
client so.

Tests: `src/roshni/test_mcp_server.py` (guard, caveats, file access off, the bundle-only
allowlist). A stdio smoke run (initialize, tools/list, tools/call) was checked on 2026-11-27 with
mcp 2.3.0, and on 2026-11-28 through `uvx` from outside the checkout.

Not hosted: the queries need DuckDB, which does not fit a free Cloudflare Worker, and Roshni has
no paid hosting. Every MCP client can start a local stdio server, so `uvx` is the install.
