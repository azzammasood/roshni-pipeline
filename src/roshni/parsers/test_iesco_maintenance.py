"""IESCO maintenance-schedule parser on small generated workbooks in the circles' layouts."""

from datetime import UTC, date, datetime
from pathlib import Path

import openpyxl
import pytest

from roshni.parsers.iesco_maintenance import parse_date, parse_dates, parse_time, parse_workbook


def save(tmp_path: Path, rows: list[list], merge: str | None = None, name: str = "m.xlsx") -> Path:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "ISLAMABAD"
    for r in rows:
        ws.append(r)
    if merge:
        ws.merge_cells(merge)
    p = tmp_path / name
    wb.save(p)
    return p


# Islamabad layout: header in row 1 with a merged "TIME" over From/To, sub-header in row 2.
ISB_HEADER = [
    "Sr No.", "DISCO", "CIRCLE", "DIVISION", "S/DIVISION", "Name of 132 KV \nGrid Station ",
    "NAME OF FEEDERS", "FEEDER CODE", "DATE", "TIME", None, "PURPOSE", "Area Affected",
]  # fmt: skip
ISB_SUB = [None] * 9 + ["From", "To", None, None]


def isb_row(
    sr, code, when, start="09:00", end="14:00", circle="ISLAMABAD", purpose="Annual Maintenance"
):
    return [
        sr,
        None,
        circle,
        None,
        None,
        None,
        f"Feeder {sr}",
        code,
        when,
        start,
        end,
        purpose,
        None,
    ]


def test_islamabad_layout(tmp_path: Path) -> None:
    rows = [
        ISB_HEADER,
        ISB_SUB,
        isb_row(1, 90009, "15.10.2026  "),
        isb_row(2, 17416, datetime(2026, 11, 21, 8, 0)),  # date cell carries a stray time
        isb_row(3, 22333, datetime(2026, 11, 22, 9, 0), circle="ISLAMABAD/PESCO"),
        isb_row(4, 22314, "16.10.2026", start="14:00", end="09:00"),  # ends before it starts
        isb_row(5, None, "17.10.2026"),  # code missing but a name is present: kept
        ["`"],  # stray mark at the end of the sheet
    ]
    res = parse_workbook(save(tmp_path, rows, merge="J1:K1"), "islamabad")
    assert [w.serial for w in res.rows] == ["1", "2", "3", "5"]
    first = res.rows[0]
    assert (first.feeder_code, first.outage_date, first.start_local, first.end_local) == (
        "090009",
        date(2026, 10, 15),
        "09:00",
        "14:00",
    )
    assert first.start_utc == datetime(2026, 10, 15, 4, 0, tzinfo=UTC)  # 09:00 PKT
    assert first.flags == ""
    assert res.rows[1].flags == "date_cell_time_0800"
    assert res.rows[2].flags == "circle_shared"  # 09:00 in the date cell matches the start
    assert res.rows[3].feeder_code is None and res.rows[3].feeder_name == "Feeder 5"
    reasons = sorted(q.reason.split(":")[0] for q in res.quarantine)
    assert reasons == ["date not readable", "window does not end after it starts"]


def test_titled_layout_with_from_to_columns(tmp_path: Path) -> None:
    """Attock/Jhelum: a title row, then the header; date before the feeder name; times as cells."""
    rows = [
        ["Shut Down Schedule on 15.10.2026 to 08.02.2027"],
        ["Sr. No", "CIRCLE", "Division", "Sub Division", "Grid", "FEEDER CODE", "DATE",
         "NAME OF FEEDERS", "FROM", "TO", "PURPOSE", "Area Effected"],
        [1, "Attock", "Attock", "City", "Attock", "105201", datetime(2026, 10, 18),
         "Hattian", datetime(1900, 1, 1, 9, 0).time(), "14:00:00", "Annual Maintenance", "Hattian"],
        [2, "Attock", "Attock", "City", "Attock", "105202", datetime(2026, 10, 19),
         "Saidan", "08:00:00", None, "Annual Maintenance", "Saidan"],
    ]  # fmt: skip
    res = parse_workbook(save(tmp_path, rows), "attock")
    (w,) = res.rows
    assert (w.grid, w.subdivision, w.area_affected) == ("Attock", "City", "Hattian")
    assert (w.outage_date, w.start_local, w.end_local) == (date(2026, 10, 18), "09:00", "14:00")
    assert [q.reason for q in res.quarantine] == ["time not readable: '08:00:00' to None"]


def test_multi_date_cell_is_one_window_per_listed_date(tmp_path: Path) -> None:
    rows = [
        ["S #", "DISCO", "Circle", "Division", "Sub Division", "Name of 132 KV Grid Station",
         "Name of Feeder", "Feeder Code", "Date", "Time From", "Time To", "Purpose of Shut Down",
         "Affected Area", "Remarks"],
        [19, "IESCO", "City", "Westridge", "Westridge", "KTM", "Millatabad", 8616,
         "28-09-2026\n01-10-2026 05-10-2026", "08:00", "12:00", "Emergency", "Gulshan", None],
    ]  # fmt: skip
    res = parse_workbook(save(tmp_path, rows), "construction")
    assert [w.outage_date for w in res.rows] == [
        date(2026, 9, 28),
        date(2026, 10, 1),
        date(2026, 10, 5),
    ]
    assert {w.flags for w in res.rows} == {"multi_date_cell"}
    assert {w.feeder_code for w in res.rows} == {"008616"}


def test_no_header_is_one_quarantined_sheet(tmp_path: Path) -> None:
    res = parse_workbook(save(tmp_path, [["just", "a", "table"], [1, 2, 3]]), "gso")
    assert res.rows == [] and len(res.quarantine) == 1
    assert res.quarantine[0].reason.startswith("no header row")


@pytest.mark.parametrize(
    "cell,expected",
    [
        ("15.10.2026", date(2026, 10, 15)),
        ("15-10-2026", date(2026, 10, 15)),
        ("2026-10-15", date(2026, 10, 15)),
        ("2026-10-15 08:00:00", date(2026, 10, 15)),
        ("31.02.2026", None),
        ("10", None),
        (None, None),
    ],
)
def test_parse_date(cell, expected) -> None:
    assert parse_date(cell)[0] == expected


def test_parse_dates_refuses_mixed_text() -> None:
    assert parse_dates("28-09-2026, 01-10-2026") == [
        (date(2026, 9, 28), None),
        (date(2026, 10, 1), None),
    ]
    assert parse_dates("28-09-2026 and later") == []


@pytest.mark.parametrize(
    "cell,expected",
    [("09:00", "09:00"), (" 14:00:00", "14:00"), ("14:00 h", "14:00"), ("9.30", "09:30"),
     ("24:00", "24:00"), ("24:30", None), ("noon", None), (None, None)],
)  # fmt: skip
def test_parse_time(cell, expected) -> None:
    assert parse_time(cell) == expected
