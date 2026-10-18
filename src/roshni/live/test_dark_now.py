from datetime import UTC, date, datetime, timedelta, timezone

import duckdb
import pytest

from roshni.live.dark_now import (
    LABEL,
    MAINTENANCE_LABEL,
    dark_now,
    minute_of_day,
    to_pkt,
    window_active,
)


def m(hhmm: str) -> int:
    return int(hhmm[:2]) * 60 + int(hhmm[2:])


@pytest.mark.parametrize(
    "at,expected",
    [
        ("2234", False),
        ("2235", True),  # start inclusive
        ("2359", True),
        ("0000", True),  # after midnight, still inside the wrapped window
        ("0204", True),
        ("0205", False),  # end exclusive
        ("1200", False),
    ],
)
def test_window_wrapping_midnight(at: str, expected: bool) -> None:
    assert window_active(m("2235"), m("0205"), m(at)) is expected


def test_window_ending_at_midnight_and_plain_windows() -> None:
    assert window_active(23 * 60, 1440, m("2359"))  # IESCO "23--24"
    assert not window_active(23 * 60, 1440, m("0000"))
    assert window_active(0, 60, m("0000")) and not window_active(0, 60, m("0100"))


def test_time_zone_handling() -> None:
    assert minute_of_day(datetime(2026, 10, 5, 18, 30, tzinfo=UTC)) == m("2330")  # UTC+5
    naive = datetime(2026, 10, 5, 23, 30)
    assert to_pkt(naive).utcoffset() == timedelta(hours=5)
    other = datetime(2026, 10, 5, 20, 30, tzinfo=timezone(timedelta(hours=2)))
    assert minute_of_day(other) == m("2330")


@pytest.fixture
def con():
    c = duckdb.connect()
    c.execute(
        "create table mart_build_info as select timestamptz '2026-10-10 00:00:00+00' as built_at"
    )
    c.execute("""
        create table dim_feeder as select * from (values
          ('ke:A', 'NIGHT FEEDER', 'IBC - Orangi - I', null, null, timestamptz '2026-10-06 17:31:00+00'),
          ('ke:B', 'NOON FEEDER', 'IBC - Clifton', null, null, null),
          ('iesco:islamabad:000001', 'SCENARIO FEEDER', null, 'islamabad', null, null)
        ) t(feeder_id, feeder_name, ibc, circle, grid_name, fetched_at)
    """)
    c.execute("""
        create table fct_schedule_window as select * from (values
          ('ke:A', 'kelectric', 'daily_cycle', null, 1355, 125, date '2026-08-05'),
          ('ke:B', 'kelectric', 'daily_cycle', null, 720, 900, date '2026-08-05'),
          ('iesco:islamabad:000001', 'iesco', 'scenario_level', 2, 1380, 1440, date '2026-01-14'),
          ('iesco:islamabad:000001', 'iesco', 'scenario_level', 12, 0, 60, date '2026-01-14')
        ) t(feeder_id, source, schedule_kind, scenario_level_hours,
            start_minute_local, end_minute_local, effective_from)
    """)
    c.execute("""
        create table fct_planned_shutdown_feeder as select * from (values
          ('iesco:islamabad:000001', 'Scenario Feeder', 'Islamabad',
           timestamptz '2026-10-05 03:00:00+00', timestamptz '2026-10-05 09:00:00+00', '08:00', '14:00',
           date '2026-10-05', null::timestamptz, 'matched'),
          (null, 'KRL', 'Rawalpindi City',
           timestamptz '2026-10-05 02:00:00+00', timestamptz '2026-10-05 09:00:00+00', '07:00', '14:00',
           date '2026-10-05', null::timestamptz, 'unmatched')
        ) t(feeder_id, feeder_name_as_printed, circle_as_printed, start_utc, end_utc,
            start_local, end_local, outage_date, fetched_at, feeder_match_state)
    """)
    c.execute("""
        create table fct_maintenance_window as select * from (values
          ('iesco:islamabad:000001', '000001', 'SCENARIO FEEDER', 'islamabad',
           timestamptz '2026-10-20 04:00:00+00', timestamptz '2026-10-20 08:00:00+00', '09:00', '13:00',
           date '2026-10-20', false, null::timestamptz),
          ('iesco:islamabad:000001', '000001', 'SCENARIO FEEDER', 'gso',
           timestamptz '2026-10-20 04:00:00+00', timestamptz '2026-10-20 08:00:00+00', '09:00', '13:00',
           date '2026-10-20', true, null::timestamptz),
          (null, null, 'NEW COLONY', 'construction',
           timestamptz '2026-10-20 05:00:00+00', timestamptz '2026-10-20 07:00:00+00', '10:00', '12:00',
           date '2026-10-20', false, null::timestamptz)
        ) t(feeder_id, feeder_code, feeder_name_as_printed, item, start_utc, end_utc,
            start_local, end_local, outage_date, repeats_circle_window, fetched_at)
    """)
    yield c
    c.close()


def test_dark_now_after_midnight(con) -> None:
    r = dark_now(con, datetime(2026, 10, 6, 1, 0), iesco_level=None)
    assert [(x.feeder_id, x.kind, x.window_local) for x in r.rows] == [
        ("ke:A", "daily_cycle", "22:35-02:05")
    ]
    row = r.rows[0]
    assert row.label == LABEL and row.effective_from == date(2026, 8, 5)
    assert row.last_updated.year == 2026  # from the source fetch time
    assert any("IESCO scenario not shown" in n for n in r.notes)


def test_dark_now_scenario_level_is_opt_in(con) -> None:
    late = datetime(2026, 10, 6, 23, 30)
    assert "scenario_level_2" not in dark_now(con, late).counts()
    assert dark_now(con, late, iesco_level=2).counts() == {
        "daily_cycle": 1,
        "scenario_level_2": 1,
    }
    with pytest.raises(ValueError):
        dark_now(con, late, iesco_level=3)


def test_planned_shutdowns_use_utc_bounds(con) -> None:
    r = dark_now(con, datetime(2026, 10, 5, 7, 30))  # 02:30 UTC: only KRL started
    assert [x.feeder_name for x in r.rows if x.kind == "planned_shutdown"] == ["KRL"]
    assert any("not matched" in n for n in r.notes)
    r = dark_now(con, datetime(2026, 10, 5, 13, 59))
    assert r.counts().get("planned_shutdown") == 2
    assert dark_now(con, datetime(2026, 10, 5, 14, 0)).counts().get("planned_shutdown") is None


def test_schedule_not_applied_before_effective_date(con) -> None:
    r = dark_now(con, datetime(2026, 7, 1, 23, 0))
    assert r.counts().get("daily_cycle") is None
    assert any("effective from 2026-08-05" in n for n in r.notes)


def test_maintenance_counts_a_gso_repeat_once(con) -> None:
    r = dark_now(con, datetime(2026, 10, 20, 11, 0))
    maint = [x for x in r.rows if x.kind == "maintenance"]
    assert [(x.feeder_name, x.area, x.window_local) for x in maint] == [
        ("NEW COLONY", "construction", "10:00-12:00"),
        ("SCENARIO FEEDER", "islamabad", "09:00-13:00"),  # the GSO repeat is left out
    ]
    assert all(
        x.label == MAINTENANCE_LABEL and x.effective_from == date(2026, 10, 20) for x in maint
    )
    assert any("1 announced maintenance window(s)" in n for n in r.notes)


def test_maintenance_uses_utc_bounds(con) -> None:
    assert dark_now(con, datetime(2026, 10, 20, 8, 59)).counts().get("maintenance") is None
    assert dark_now(con, datetime(2026, 10, 20, 9, 0)).counts().get("maintenance") == 1
    assert dark_now(con, datetime(2026, 10, 20, 12, 59)).counts().get("maintenance") == 1
    assert dark_now(con, datetime(2026, 10, 20, 13, 0)).counts().get("maintenance") is None
