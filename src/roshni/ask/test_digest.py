from datetime import UTC, date, datetime

import duckdb

from roshni.ask import digest


def _warehouse():
    con = duckdb.connect()
    con.execute(
        "create table fct_maintenance_window (feeder_code varchar, outage_date date, repeats_circle_window boolean)"
    )
    con.execute(
        "insert into fct_maintenance_window values ('1','2026-11-27',false),('2','2026-11-27',false),"
        "('2','2026-11-27',true),('3','2026-11-30',false),('4','2026-12-10',false)"
    )
    con.execute("create table fct_planned_shutdown (outage_date date)")
    con.execute("insert into fct_planned_shutdown values ('2026-11-27'),('2026-11-28')")
    con.execute("create table mart_ke_schedule_history (effective_from date)")
    con.execute("insert into mart_ke_schedule_history values ('2026-09-01'),('2026-11-01')")
    con.execute("create table mart_news_headline (first_seen_at timestamptz)")
    con.execute(
        "insert into mart_news_headline values ('2026-11-27 01:00:00+00'),('2026-11-20 01:00:00+00')"
    )
    return con


def test_facts_count_today_and_the_week():
    f = digest.facts(_warehouse(), date(2026, 11, 27), datetime(2026, 11, 27, 6, tzinfo=UTC))
    assert f == {
        "maint_today": "2",
        "maint_feeders": "2",
        "maint_week": "3",
        "shutdowns_today": "1",
        "ke_effective": "2026-11-01",
        "news_day": "1",
    }


def test_template_without_a_model():
    d = digest.build(
        _warehouse(),
        None,
        date(2026, 11, 27),
        datetime(2026, 11, 27, 6, tzinfo=UTC),
        log=lambda *_: None,
    )
    assert d["narrated_by"] == "" and "2 announced maintenance windows on 2 feeders" in d["text"]
    assert "{" not in d["text"]
