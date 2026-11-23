"""fct_planned_shutdown is incremental: a second run loads only release files it has not seen.

Runs dbt on DuckDB against a two-file Parquet built here, so it needs no data-sources folder.
"""

from pathlib import Path

import duckdb
from typer.testing import CliRunner

from roshni.cli import app

MODELS = "stg_iesco_press_release_window fct_planned_shutdown"


def write_releases(parsed: Path, rows: list[tuple[str, int, str]]) -> None:
    """(source_sha256, seq, feeder_name) rows in the parsed press-release layout."""
    values = ", ".join(
        f"('f_{sha[:4]}.pdf', '{sha}', TIMESTAMPTZ '2026-10-10 00:00:00+00', 'No. 01', 'Oct', "
        f"{seq}, DATE '2026-10-12', 'Islamabad', '{name}', '09:00', '14:00', "
        "TIMESTAMPTZ '2026-10-12 04:00:00+00', TIMESTAMPTZ '2026-10-12 09:00:00+00', '')"
        for sha, seq, name in rows
    )
    cols = (
        "source_file, source_sha256, fetched_at, release_no, release_period, seq, outage_date, "
        "circle, feeder_name, start_local, end_local, start_utc, end_utc, flags"
    )
    out = (parsed / "iesco_press_release_window.parquet").as_posix()
    duckdb.sql(f"copy (select * from (values {values}) as t({cols})) to '{out}' (format parquet)")


def run(parsed: Path, db: Path) -> list[tuple[str, str]]:
    result = CliRunner().invoke(
        app,
        ["build", "--command", "run", "--select", MODELS, "--parsed", str(parsed), "--db", str(db)],
    )
    assert result.exit_code == 0, result.output
    with duckdb.connect(str(db)) as con:
        sql = "select shutdown_id, feeder_name_as_printed from fct_planned_shutdown order by 1"
        return con.sql(sql).fetchall()


def test_second_run_loads_only_new_release_files(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ROSHNI_PARSED_DIR", "")  # the CLI sets both; restored after the test
    monkeypatch.setenv("ROSHNI_DUCKDB_PATH", "")
    parsed, db = tmp_path / "parsed", tmp_path / "roshni.duckdb"
    parsed.mkdir()
    a, b = "a" * 64, "b" * 64

    write_releases(parsed, [(a, 1, "Kala Base"), (a, 2, "Sohawa")])
    first = run(parsed, db)  # table does not exist yet: a full build
    assert first == [("aaaaaaaaaaaa:1", "Kala Base"), ("aaaaaaaaaaaa:2", "Sohawa")]
    assert run(parsed, db) == first  # nothing new: no duplicates

    # File a reappears with a changed row (it cannot change in reality: it is keyed by its
    # SHA-256), and a new file b arrives. Only b is read; a's rows stay as first loaded.
    write_releases(parsed, [(a, 1, "CHANGED"), (a, 2, "Sohawa"), (b, 1, "Gulshan")])
    assert run(parsed, db) == [*first, ("bbbbbbbbbbbb:1", "Gulshan")]
