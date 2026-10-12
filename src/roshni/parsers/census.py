"""Committed census tables (owner decision 2026-10-12, option a).

The PBS Census 2023 files are hand-downloaded and never committed, so a GitHub-hosted job cannot
parse them. `freeze` writes the parsed census tables, trimmed to the columns that dbt, the Great
Expectations suites and provenance need, to `census/` (committed). `restore` copies them into a
parsed folder so the daily job can build without `data-sources/`. Census 2023 is static; refreeze
only after a parser change, and the warehouse golden tests decide whether the result is right.
Gas is never kept (no gas-connection wealth proxy).
"""

import json
import shutil
from pathlib import Path

import duckdb

from roshni.paths import REPO_ROOT

CENSUS_DIR = REPO_ROOT / "census"
PROVENANCE = ["source_file", "source_sha256", "fetched_at", "table_no", "location", "flags"]
URBAN_KEYS = [
    "province", "level", "name", "district", "tehsil", "body", "charge", "circle", "area_key",
]  # fmt: skip
RURAL_KEYS = ["province", "level", "name", "hadbast", "district", "tehsil", "qh", "pc", "area_key"]
POPULATION = [
    "pop_total", "pop_male", "pop_female", "literacy_pct_total",
    "edu_degree_above_male", "edu_degree_above_female", "edu_degree_above_transgender",
]  # fmt: skip
HOUSING = ["housing_units_total", "structure_pacca", "electricity", "avg_household_size"]
TABLES: dict[str, list[str]] = {
    "pbs_urban_population": PROVENANCE + URBAN_KEYS + POPULATION,
    "pbs_urban_housing": PROVENANCE + URBAN_KEYS + HOUSING,
    "pbs_rural_population": PROVENANCE + RURAL_KEYS + POPULATION + ["area_acres"],
    "pbs_rural_housing": PROVENANCE + RURAL_KEYS + HOUSING,
}
MANIFEST = "manifest.json"


def freeze(parsed_dir: Path, out_dir: Path = CENSUS_DIR) -> dict[str, int]:
    """Write trimmed census tables plus a manifest (rows, columns, source SHA-256s)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, dict] = {}
    for table, cols in TABLES.items():
        src = (parsed_dir / f"{table}.parquet").as_posix()
        dst = (out_dir / f"{table}.parquet").as_posix()
        assert "gas" not in cols
        con = duckdb.connect()
        con.execute(
            f"copy (select {', '.join(cols)} from read_parquet('{src}') order by area_key, name) "
            f"to '{dst}' (format parquet, compression zstd)"
        )
        rows = con.sql(f"select count(*) from read_parquet('{dst}')").fetchone()[0]
        shas = [r[0] for r in con.sql(
            f"select distinct source_sha256 from read_parquet('{dst}') order by 1"
        ).fetchall()]  # fmt: skip
        con.close()
        manifest[table] = {"rows": rows, "columns": cols, "source_sha256": shas}
    (out_dir / MANIFEST).write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    return {t: m["rows"] for t, m in manifest.items()}


def restore(census_dir: Path, parsed_dir: Path) -> dict[str, int]:
    """Copy committed census tables into a parsed folder, checking them against the manifest."""
    manifest = json.loads((census_dir / MANIFEST).read_text(encoding="utf-8"))
    parsed_dir.mkdir(parents=True, exist_ok=True)
    counts = {}
    for table, meta in manifest.items():
        src = census_dir / f"{table}.parquet"
        rows = duckdb.sql(f"select count(*) from read_parquet('{src.as_posix()}')").fetchone()[0]
        if rows != meta["rows"]:
            raise ValueError(f"{src}: {rows} rows, manifest says {meta['rows']}")
        shutil.copyfile(src, parsed_dir / f"{table}.parquet")
        counts[table] = rows
    return counts
