from pathlib import Path

import openpyxl
import pytest

from roshni.parsers.iesco_xlsx import normalise_code, parse_iesco_xlsx, parse_slots

HEADER = ["SR.NO", "GRID NAME", "Feeder Name ", "Feeder Code "] + [
    f"{n}HR INTERRUPTIONS   SCHEDULE" for n in (2, 4, 6, 8, 10, 12)
]


def slots(n: int, offset: int = 0) -> str:
    return ", ".join(
        f"{(offset + i * 2) % 24:02d}--{(offset + i * 2) % 24 + 1:02d}" for i in range(n)
    )


def workbook(tmp_path: Path, rows: list[list]) -> Path:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["DIFFERENT INTERRUPTION SCHEDULES ... (implemented according to shortfall)"])
    ws.append(HEADER)
    for r in rows:
        ws.append(r)
    p = tmp_path / "iesco-islamabad-sep26.xlsx"
    wb.save(p)
    return p


def full_row(serial, name, code, override: dict[int, str] | None = None):
    cells = {n: slots(n) for n in (2, 4, 6, 8, 10, 12)} | (override or {})
    return [serial, "F-6", name, code, *(cells[n] for n in (2, 4, 6, 8, 10, 12))]


@pytest.mark.parametrize(
    "raw,expected",
    [(89201, "089201"), (89201.0, "089201"), ("4123", "004123"), ("NOT ALLOTED", None)],
)
def test_normalise_code(raw, expected) -> None:
    assert normalise_code(raw) == expected


def test_parse_slots_midnight_and_errors() -> None:
    assert parse_slots("00--01, 23--24") == [(0, 1), (23, 24)]
    assert parse_slots(None) == []
    with pytest.raises(ValueError):
        parse_slots("00--02")
    with pytest.raises(ValueError):
        parse_slots("noon")


def test_workbook_rows_flags_and_quarantine(tmp_path: Path) -> None:
    p = workbook(
        tmp_path,
        [
            full_row(1, "BHARAKHAU 1", 89201),
            full_row(2, "PHA-2", "NOT ALLOTED"),
            full_row(3, "KOHALA", 120404, {10: slots(11)}),
            full_row(4, "BROKEN", 1234, {2: "00--01, lunch"}),
            [None] * 10,
        ],
    )
    feeders, slot_rows = parse_iesco_xlsx(p)
    by_name = {f.feeder_name: f for f in feeders.rows}
    assert set(by_name) == {"BHARAKHAU 1", "PHA-2", "KOHALA"}
    assert by_name["BHARAKHAU 1"].feeder_code == "089201" and by_name["BHARAKHAU 1"].flags == ""
    assert by_name["PHA-2"].feeder_code is None
    assert by_name["PHA-2"].flags == "non_numeric_code:NOT ALLOTED"
    assert by_name["KOHALA"].flags == "slot_count_mismatch:L10=11"
    assert [q.reason for q in feeders.quarantine] == ["unparseable slot 'lunch'"]
    assert all(f.circle == "islamabad" for f in feeders.rows)
    # 42 slots per clean feeder (2+4+...+12), 43 for Kohala.
    assert len(slot_rows.rows) == 42 + 42 + 43
