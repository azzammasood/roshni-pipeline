"""Warehouse golden tests: build dbt into a temporary DuckDB from data/parsed and check counts.

Needs the parsed Parquet layer (`roshni parse`), so it is marked needs_data_sources.
"""

import duckdb
import pytest
from typer.testing import CliRunner

from roshni.cli import app
from roshni.paths import DATA_DIR

pytestmark = pytest.mark.needs_data_sources
PARSED = DATA_DIR / "parsed"


@pytest.fixture(scope="module")
def wh(tmp_path_factory):
    if not (PARSED / "iesco_feeder.parquet").exists():
        pytest.skip("run `roshni parse` first")
    db = tmp_path_factory.mktemp("wh") / "roshni.duckdb"
    result = CliRunner().invoke(app, ["build", "--parsed", str(PARSED), "--db", str(db)])
    assert result.exit_code == 0, result.output
    con = duckdb.connect(str(db))  # same config as dbt's in-process connection
    yield lambda sql: con.sql(sql).fetchall()
    con.close()


def test_dim_feeder_counts(wh) -> None:
    assert wh("select source, count(*) from dim_feeder group by 1 order by 1") == [
        ("iesco", 1101),
        ("kelectric", 624),
    ]
    # 616 exact + 1 truncated name = 617 joined (audit section 3).
    assert wh(
        "select schedule_match_method, count(*) from dim_feeder "
        "where schedule_match_method is not null group by 1 order by 1"
    ) == [("exact", 616), ("truncated_name", 1)]


def test_known_bad_rows_quarantined_with_reasons(wh) -> None:
    assert wh("select reason, count(*) from quarantine_feeder group by 1 order by 1") == [
        ("non_numeric_code", 3),
        ("other_disco_feeder_sharing_code", 1),
    ]
    assert wh(
        "select feeder_name, level_hours, count(*) from quarantine_schedule_window "
        "where reason = 'slot_count_mismatch' group by 1, 2"
    ) == [("KOHALA", 10, 11)]


def test_ke_category_vs_hours(wh) -> None:
    assert wh(
        "select category, scheduled_hours_per_day, count(*) from mart_ke_feeder_hours "
        "group by 1, 2 order by 1, 2"
    ) == [("High", 12.0, 163), ("Medium", 6.0, 125), ("Medium", 12.0, 2), ("Very High", 12.0, 327)]


def test_schedule_windows_carry_effective_dates(wh) -> None:
    rows = wh(
        "select schedule_kind, count(*), count(distinct feeder_id), "
        "cast(min(effective_from) as varchar) from fct_schedule_window group by 1 order by 1"
    )
    assert rows == [
        ("daily_cycle", 2472, 618, "2026-08-05"),
        ("scenario_level", 46232, 1101, "2026-01-14"),
    ]


def test_area_indicators(wh) -> None:
    (row,) = wh(
        "select pop_total, round(literacy_pct, 1) from dim_area_indicators "
        "where area_name = 'ORANGI SUB-DIVISION'"
    )
    assert row == (596919.0, 60.8)
    assert wh(
        "select count(*) from dim_area_indicators where area_type = 'urban' and area_level = 'circle'"
    ) == [(75 + 4268 + 3690,)]
