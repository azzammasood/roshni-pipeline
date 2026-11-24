"""stg_pbs_urban joins census tables 33 and 34 only where the key is unique on both sides.

Runs dbt on DuckDB against small Parquet files built here (no data-sources folder needed). The
cases pin the join rules, so the join can be rewritten for speed (docs/benchmarks.md) without
changing a value.
"""

from pathlib import Path

import duckdb
from typer.testing import CliRunner

from roshni.cli import app

POP_COLS = (
    "source_file, source_sha256, province, area_key, level, name, district, tehsil, body, "
    "charge, circle, pop_total, literacy_pct_total, edu_degree_above_male, "
    "edu_degree_above_female, edu_degree_above_transgender, flags"
)
HOU_COLS = (
    "source_sha256, province, area_key, housing_units_total, structure_pacca, electricity, "
    "avg_household_size, flags"
)


def write(parsed: Path, name: str, cols: str, rows: list[str]) -> None:
    out = (parsed / f"{name}.parquet").as_posix()
    duckdb.sql(
        f"copy (select * from (values {', '.join(rows)}) as t({cols})) to '{out}' (format parquet)"
    )


def pop(province: str, key: str, total: int) -> str:
    return (
        f"('t33.pdf', 'p', '{province}', '{key}', 'charge', 'n{key}', 'd', 't', 'b', 'c', 'ci', "
        f"{total}, 50.0, 1, 2, 0, '')"
    )


def hou(province: str, key: str, units: int) -> str:
    return f"('h', '{province}', '{key}', {units}, 5, 8, 6.5, '')"


def test_join_only_on_keys_unique_on_both_sides(tmp_path: Path) -> None:
    parsed = tmp_path / "parsed"
    parsed.mkdir()
    write(parsed, "pbs_urban_population", POP_COLS, [
        pop("Punjab", "A", 100),  # unique on both sides: joined
        pop("Sindh", "B", 200),   # ambiguous population key (twice): never joined
        pop("Sindh", "B", 201),
        pop("Sindh", "C", 300),   # ambiguous housing key: not joined
        pop("Punjab", "D", 400),  # no housing row
        pop("Khyber Pakhtunkhwa", "A", 500),  # same key, other province: not joined
    ])  # fmt: skip
    write(parsed, "pbs_urban_housing", HOU_COLS, [
        hou("Punjab", "A", 10),
        hou("Sindh", "B", 20),
        hou("Sindh", "C", 30),
        hou("Sindh", "C", 31),
    ])  # fmt: skip
    db = tmp_path / "w.duckdb"
    result = CliRunner().invoke(
        app,
        ["build", "--command", "run", "--select", "stg_pbs_urban",
         "--parsed", str(parsed), "--db", str(db)],
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    with duckdb.connect(str(db)) as con:
        rows = con.sql(
            "select province, area_key, pop_total, degree_above_total, housing_units_total, "
            "population_key_ambiguous, housing_missing, housing_source_sha256 "
            "from stg_pbs_urban order by province, area_key, pop_total"
        ).fetchall()
    assert rows == [
        ("Khyber Pakhtunkhwa", "A", 500, 3, None, False, True, None),
        ("Punjab", "A", 100, 3, 10, False, False, "h"),
        ("Punjab", "D", 400, 3, None, False, True, None),
        ("Sindh", "B", 200, 3, None, True, True, None),
        ("Sindh", "B", 201, 3, None, True, True, None),
        ("Sindh", "C", 300, 3, None, False, True, None),
    ]
