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
    query = lambda sql: con.sql(sql).fetchall()  # noqa: E731
    query.con = con
    yield query
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


def test_press_release_03_matching(wh) -> None:
    # Audit 7.2: of the 15 Oct 5 names, 8 match confidently, 3 plausibly, 4 not at all.
    rows = dict(
        wh(
            "select s.feeder_name_as_printed, s.feeder_match_state from fct_planned_shutdown_feeder s "
            "where s.release_no = '03' and s.outage_date = date '2026-10-05'"
        )
    )
    # After the delegated review (2026-10-10): the confident and plausible names are matched;
    # Qadeer Road's wrong suggestion (HAIDER ROAD) was rejected.
    assert {n for n, st in rows.items() if st == "matched"} == {
        "Islamabad Club-1", "Islamabad Club-2", "Mehfooz Shaheed / Shahzad Town", "Orchard Scheme",
        "Pindorian", "Scheme-2", "Askari-XI", "Millatabad", "Dhoke Chaudhrian", "Coblane",
        "Peshawar Road",
    }  # fmt: skip
    assert {n for n, st in rows.items() if st == "unmatched"} == {
        "Qadeer Road", "KRL", "Filtration Plant", "CDA Pump",
    }  # fmt: skip


def test_dark_now_on_real_schedules(wh) -> None:
    from datetime import datetime

    from roshni.live.dark_now import dark_now

    # Release No. 03 windows (07:00/08:00 to 12:00/14:00 on Oct 5) are all active at 09:00.
    r = dark_now(wh.con, datetime(2026, 10, 5, 9, 0))
    assert r.counts()["planned_shutdown"] == 15
    # Level 12 darkens half the day for every IESCO feeder: two cohorts, about half at any hour.
    r = dark_now(wh.con, datetime(2026, 10, 5, 23, 30), iesco_level=12)
    assert r.counts()["scenario_level_12"] == 545
    # K-Electric cycles wrapping midnight are dark just after midnight.
    r = dark_now(wh.con, datetime(2026, 10, 6, 0, 30))
    assert any(x.window_local.startswith("23:05") for x in r.rows if x.kind == "daily_cycle")


def test_equity_report_numbers_trace_to_queries(wh) -> None:
    import re

    from roshni.narrate.facts import QUERIES
    from roshni.narrate.report import build_report

    rep = build_report(wh.con, engine="template")
    facts = {f["id"]: f for f in rep.data["facts"]}
    # Audit oracles that appear in the report.
    assert facts["coverage_listed_feeders"]["value"] == 623
    assert facts["overlap_medium"]["value"] == 112 and facts["overlap_high"]["value"] == 89
    assert facts["medium_12h"]["value"] == 2
    # Every number in the narrative is the rendered value of some fact ...
    allowed = set()
    for f in rep.data["facts"]:
        allowed |= set(re.findall(r"\d+(?:[.,]\d+)*", str(f["value"])))
    assert set(re.findall(r"\d+(?:[.,]\d+)*", rep.data["narrative"])) <= allowed
    # ... and every fact is reproduced by re-running its named query.
    for f in rep.data["facts"]:
        cur = wh.con.execute(QUERIES[f["query_id"]])
        row = dict(zip([d[0] for d in cur.description], cur.fetchone(), strict=True))
        assert f["value"] in [v if not isinstance(v, float) or not v.is_integer() else int(v)
                              for v in row.values()]  # fmt: skip


def test_static_export_validates(wh, tmp_path) -> None:
    import json

    from roshni.export.build import build_export, validate_export

    counts = build_export(wh.con, tmp_path)
    assert counts["feeders"] == 1725 and counts["planned_shutdowns"] == 1853
    assert counts["dark_profiles"] == 1101 + 618  # IESCO feeders + K-Electric scheduled
    assert set(validate_export(tmp_path).values()) == {"valid"}
    profiles = {
        p["feeder_id"]: p for p in json.loads((tmp_path / "dark_profiles.json").read_text())["data"]
    }
    # Every K-Electric profile sums to its 6 or 12 daily hours; every IESCO level N to N hours.
    for p in profiles.values():
        if p["daily"] is not None:
            assert sum(p["daily"]) in (360, 720)
        for level, minutes in (p["scenario_levels"] or {}).items():
            assert sum(minutes) == int(level) * 60
