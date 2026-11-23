import json
from datetime import UTC, date, datetime
from pathlib import Path

import duckdb
import httpx
import pytest

from roshni.export import health
from roshni.export.health import build_health, dbt_results, fetch_days, parsed_quality

HEADER = "source,item_key,label,url,fetched_at,http_status,etag,last_modified,sha256,bytes,path,changed,note\n"


def test_fetch_days_counts_by_karachi_day(tmp_path: Path) -> None:
    (tmp_path / "raw_snapshots.csv").write_text(
        HEADER
        # 20:00 UTC is already the next day in Karachi (UTC+5).
        + "a,x,,u,2026-11-08T20:00:00Z,200,,,s,1,f,true,\n"
        + "a,y,,u,2026-11-09T01:00:00Z,304,,,s,1,f,false,not modified\n"
        + "b,z,,u,2026-11-09T02:00:00Z,404,,,,0,,false,known broken link (data-audit.md)\n"
        + "c,w,,u,2026-11-09T03:00:00Z,,,,,0,,false,ConnectTimeout: timed out\n",
        encoding="utf-8",
    )
    assert [(d.date, d.fetches, d.new_files, d.errors) for d in fetch_days(tmp_path)] == [
        (date(2026, 11, 9), 4, 1, 1)
    ]
    assert fetch_days(None) == [] and fetch_days(tmp_path / "missing") == []


def test_dbt_results_groups_statuses(tmp_path: Path) -> None:
    p = tmp_path / "run_results.json"
    statuses = ["pass", "pass", "success", "warn", "error", "fail", "skipped"]
    p.write_text(json.dumps({"results": [{"status": s} for s in statuses]}), encoding="utf-8")
    r = dbt_results(p)
    assert (r.passed, r.warned, r.failed, r.skipped) == (3, 1, 2, 1)
    assert dbt_results(tmp_path / "none.json").passed == 0


def test_parsed_quality_reports_top_reasons(tmp_path: Path) -> None:
    (tmp_path / "quarantine").mkdir()
    con = duckdb.connect()
    con.execute(f"copy (select 1 as x from range(5)) to '{(tmp_path / 't.parquet').as_posix()}'")
    con.execute(
        "copy (select * from (values ('time not readable: 7'), ('time not readable: 8'), "
        "('no feeder name or code'), ('a'), ('b')) v(reason)) "
        f"to '{(tmp_path / 'quarantine' / 't.parquet').as_posix()}'"
    )
    con.execute(f"copy (select 1 as x) to '{(tmp_path / 'clean.parquet').as_posix()}'")
    clean, t = parsed_quality(tmp_path)
    assert (clean.table, clean.rows, clean.quarantined, clean.top_reasons) == ("clean", 1, 0, [])
    assert (t.rows, t.quarantined) == (5, 5)
    assert [(r.reason, r.rows) for r in t.top_reasons] == [
        ("time not readable", 2),
        ("a", 1),
        ("b", 1),
    ]


class _Resp:
    def __init__(self, payload: dict, status: int = 200) -> None:
        self._payload, self.status_code = payload, status

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("x", request=httpx.Request("GET", "u"), response=None)

    def json(self) -> dict:
        return self._payload


def test_build_health_carries_sizes_and_runs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    previous = {"data": {"sizes": [
        {"date": "2026-11-21", "rows": {"feeders": 1700}},
        {"date": "2026-11-22", "rows": {"feeders": 1710}},  # same day as now: replaced
    ]}}  # fmt: skip
    runs = {"workflow_runs": [
        {"status": "completed", "conclusion": "success", "event": "workflow_run",
         "run_started_at": "2026-11-21T07:00:00Z", "updated_at": "2026-11-21T07:03:30Z",
         "html_url": "https://github.com/r/actions/runs/1"},
        {"status": "in_progress", "conclusion": None, "event": "workflow_dispatch",
         "run_started_at": "2026-11-22T07:00:00Z", "updated_at": "2026-11-22T07:01:00Z",
         "html_url": "https://github.com/r/actions/runs/2"},
    ]}  # fmt: skip

    def fake_get(url: str, **_: object) -> _Resp:
        return _Resp(runs if "api.github.com" in url else previous)

    monkeypatch.setattr(health.httpx, "get", fake_get)
    con = duckdb.connect()
    for table in (
        "dim_feeder",
        "fct_schedule_window",
        "fct_planned_shutdown",
        "fct_maintenance_window",
    ):
        con.execute(f"create table {table} as select 1 as x from range(3)")
    h = build_health(
        con,
        tmp_path,
        tmp_path / "run_results.json",
        repo="o/r",
        previous_url="https://example/health.json",
        now=datetime(2026, 11, 22, 3, 0, tzinfo=UTC),  # 08:00 in Karachi
    )
    assert [(p.date, p.rows.get("feeders")) for p in h.sizes] == [
        (date(2026, 11, 21), 1700),
        (date(2026, 11, 22), 3),
    ]
    (run,) = h.publish_runs
    assert (run.duration_seconds, run.conclusion, run.trigger) == (210, "success", "workflow_run")
    assert h.freshness_target_hours == 36


def test_build_health_without_network(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def down(*_: object, **__: object) -> _Resp:
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(health.httpx, "get", down)
    con = duckdb.connect()
    for table in (
        "dim_feeder",
        "fct_schedule_window",
        "fct_planned_shutdown",
        "fct_maintenance_window",
    ):
        con.execute(f"create table {table} as select 1 as x")
    h = build_health(con, tmp_path, tmp_path / "r.json", repo="o/r", previous_url="https://x")
    assert h.publish_runs == [] and len(h.sizes) == 1
