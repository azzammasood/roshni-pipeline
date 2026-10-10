"""Upload data/parsed/*.parquet to Databricks as tables in <catalog>.roshni_raw (Phase 3b).

Loads by upload (no internet access needed on the Databricks side): each file is PUT into a
Unity Catalog volume, then a table is created from it. Credentials come from environment
variables only: DATABRICKS_HOST, DATABRICKS_HTTP_PATH, DATABRICKS_TOKEN
(optional ROSHNI_DATABRICKS_CATALOG, default "workspace").

Usage: uv run --group databricks python scripts/databricks_load.py
"""

import os
import sys

from databricks import sql

from roshni.paths import DATA_DIR

SCHEMA = "roshni_raw"
VOLUME = "uploads"


def main() -> int:
    missing = [v for v in ("DATABRICKS_HOST", "DATABRICKS_HTTP_PATH", "DATABRICKS_TOKEN")
               if not os.environ.get(v)]  # fmt: skip
    if missing:
        print(f"set these environment variables first: {', '.join(missing)}", file=sys.stderr)
        return 2
    host = os.environ["DATABRICKS_HOST"].removeprefix("https://").rstrip("/")
    catalog = os.environ.get("ROSHNI_DATABRICKS_CATALOG", "workspace")
    parsed = DATA_DIR / "parsed"
    files = sorted(parsed.glob("*.parquet"))
    if not files:
        print("no parsed files: run `uv run roshni parse` first", file=sys.stderr)
        return 2

    with (
        sql.connect(
            server_hostname=host,
            http_path=os.environ["DATABRICKS_HTTP_PATH"],
            access_token=os.environ["DATABRICKS_TOKEN"],
            staging_allowed_local_path=str(parsed),
        ) as conn,
        conn.cursor() as cur,
    ):
        cur.execute(f"CREATE SCHEMA IF NOT EXISTS {catalog}.{SCHEMA}")
        cur.execute(f"CREATE VOLUME IF NOT EXISTS {catalog}.{SCHEMA}.{VOLUME}")
        for f in files:
            table = f.stem
            remote = f"/Volumes/{catalog}/{SCHEMA}/{VOLUME}/{f.name}"
            cur.execute(f"PUT '{f.as_posix()}' INTO '{remote}' OVERWRITE")
            cur.execute(
                f"CREATE OR REPLACE TABLE {catalog}.{SCHEMA}.{table} AS "
                f"SELECT * FROM parquet.`{remote}`"
            )
            cur.execute(f"SELECT count(*) FROM {catalog}.{SCHEMA}.{table}")
            print(f"{table:30} rows={cur.fetchone()[0]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
