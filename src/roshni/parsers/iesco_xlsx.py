"""IESCO load-management XLSX (one workbook per circle).

Row 1 is a title, row 2 the header (serial, grid, feeder, code, then 2/4/6/8/10/12-hour levels),
data from row 3. Cells look like "00--01, 12--13" (start--end, 24-hour clock; 23--24 ends at
midnight). At level N a feeder should have N one-hour slots. Anomalies are flagged, not fixed.
"""

import re
from pathlib import Path

import openpyxl
from pydantic import BaseModel

from roshni.parsers.common import ParseResult, Provenance, provenance

LEVELS = (2, 4, 6, 8, 10, 12)
SLOT_RE = re.compile(r"^(\d{1,2})\s*-{1,3}\s*(\d{1,2})$")
FILE_RE = re.compile(r"iesco-(?P<circle>[a-z]+)-")


class IescoFeeder(Provenance):
    circle: str
    sheet_row: int
    serial: str | None
    grid_name: str | None
    feeder_name: str
    feeder_code_raw: str
    feeder_code: str | None  # 6-digit zero-padded text; None when not numeric
    flags: str  # ";"-separated, empty when clean
    sheet_title: str


class IescoSlot(BaseModel):
    circle: str
    sheet_row: int
    feeder_code: str | None
    level_hours: int
    slot_start_hour: int  # 0..23, Asia/Karachi local
    slot_end_hour: int  # 1..24


def normalise_code(raw: object) -> str | None:
    """89201 -> '089201'. Non-numeric codes (e.g. 'NOT ALLOTED') -> None."""
    s = str(raw).strip()
    if isinstance(raw, float) and raw.is_integer():
        s = str(int(raw))
    return s.zfill(6) if s.isdigit() and len(s) <= 6 else None


def parse_slots(cell: object) -> list[tuple[int, int]]:
    """Parse '00--01, 12--13'. Raises ValueError on any token that is not a one-hour slot."""
    if cell is None or str(cell).strip() == "":
        return []
    out = []
    for tok in re.split(r"[,\n]+", str(cell)):
        tok = tok.strip()
        if not tok:
            continue
        m = SLOT_RE.match(tok)
        if not m:
            raise ValueError(f"unparseable slot {tok!r}")
        start, end = int(m[1]), int(m[2])
        if not (0 <= start <= 23 and end == start + 1):
            raise ValueError(f"slot is not one hour within a day: {tok!r}")
        out.append((start, end))
    return out


def _clean(v: object) -> str | None:
    if v is None:
        return None
    s = re.sub(r"\s+", " ", str(v)).strip()
    if isinstance(v, float) and v.is_integer():
        s = str(int(v))
    return s or None


def parse_iesco_xlsx(path: Path, circle: str | None = None) -> tuple[ParseResult, ParseResult]:
    """Return (feeders, slots) results for one circle workbook."""
    if circle is None:
        m = FILE_RE.search(path.name)
        if not m:
            raise ValueError(f"cannot infer circle from {path.name}")
        circle = m["circle"]
    prov = provenance(path)
    feeders: ParseResult[IescoFeeder] = ParseResult("iesco_feeder")
    slots: ParseResult[IescoSlot] = ParseResult("iesco_schedule_slot")

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.worksheets[0]
    rows = list(ws.iter_rows(values_only=True))
    wb.close()
    title = _clean(rows[0][0]) or ""
    header = [(_clean(c) or "").upper() for c in rows[1]]
    level_cols = {}
    for i, h in enumerate(header):
        m = re.match(r"^(\d+)\s*HR", h)
        if m and int(m[1]) in LEVELS:
            level_cols[int(m[1])] = i
    if sorted(level_cols) != list(LEVELS) or "FEEDER CODE" not in header:
        raise ValueError(f"{path.name}: unexpected header {header}")
    i_code = header.index("FEEDER CODE")

    for r, row in enumerate(rows[2:], start=3):
        cells = list(row) + [None] * (len(header) - len(row))
        if all(_clean(c) is None for c in cells):
            continue
        raw = " | ".join(_clean(c) or "" for c in cells)
        serial, grid, name = _clean(cells[0]), _clean(cells[1]), _clean(cells[2])
        code_raw = _clean(cells[i_code])
        if not name or code_raw is None:
            feeders.reject(prov, f"row {r}", raw, "missing feeder name or code")
            continue
        try:
            parsed = {lvl: parse_slots(cells[col]) for lvl, col in level_cols.items()}
        except ValueError as e:
            feeders.reject(prov, f"row {r}", raw, str(e))
            continue

        code = normalise_code(cells[i_code])
        flags = []
        if code is None:
            flags.append(f"non_numeric_code:{code_raw}")
        for lvl, sl in parsed.items():
            if len(sl) != lvl:
                flags.append(f"slot_count_mismatch:L{lvl}={len(sl)}")
            if len({s for s, _ in sl}) != len(sl):
                flags.append(f"duplicate_slot:L{lvl}")
        feeders.rows.append(
            IescoFeeder(
                **prov.model_dump(),
                circle=circle,
                sheet_row=r,
                serial=serial,
                grid_name=grid,
                feeder_name=name,
                feeder_code_raw=code_raw,
                feeder_code=code,
                flags=";".join(flags),
                sheet_title=title,
            )
        )
        for lvl, sl in parsed.items():
            slots.rows.extend(
                IescoSlot(
                    circle=circle,
                    sheet_row=r,
                    feeder_code=code,
                    level_hours=lvl,
                    slot_start_hour=s,
                    slot_end_hour=e,
                )
                for s, e in sl
            )
    return feeders, slots
