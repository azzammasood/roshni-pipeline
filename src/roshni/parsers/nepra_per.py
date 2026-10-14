"""NEPRA Performance Evaluation Reports (distribution companies): section 3.6 "Load Shedding
(Hours)", a five-year comparison of the average daily load-shedding hours each company reported
to NEPRA (via poppler `pdftotext -layout`).

These are the companies' own reported figures as compiled by the regulator, not measurements;
NEPRA says several are under-reported. Reports without the comparison table (older layouts) are
quarantined with a reason; their years appear in later reports' comparison tables.
"""

import re
from pathlib import Path

from roshni.parsers.common import ParseResult, Provenance, provenance
from roshni.parsers.pdftext import pdf_text

COMPANIES = (
    "PESCO", "IESCO", "GEPCO", "FESCO", "LESCO", "MEPCO", "QESCO", "SEPCO", "HESCO", "TESCO",
    "K-Electric",
)  # fmt: skip

# Body heading of the section, not the contents page (which has dot leaders or a page number).
HEADING_RE = re.compile(r"^\s*3\.6\s+load\s*shedding\b(?!.*(\.{4}|\s\d+\s*$))", re.I)
YEAR_RE = re.compile(r"\b(20\d{2})\s*[-–]\s*(\d{2})\b")
ROW_RE = re.compile(rf"(?<![A-Za-z])({'|'.join(map(re.escape, COMPANIES))})(?![A-Za-z])\s+(.*)$")
NUM_RE = re.compile(r"(?<![\w.])\d+(?:\.\d+)?(?![\w.])")
TABLE_RE = re.compile(r"^\s*table\s*\d+", re.I)
WINDOW = 60  # lines after the heading that may hold the table


class NepraLoadShedding(Provenance):
    report_year: str  # fiscal year the report covers, e.g. "2024-25" (its newest column)
    fiscal_year: str  # the column's fiscal year
    company: str  # as printed: PESCO ... K-Electric
    reported_hours_per_day: float  # average daily load-shedding hours reported to NEPRA
    line: int  # line of the row in the extracted text (1-based)


def _year(m: re.Match) -> str:
    return f"{m.group(1)}-{m.group(2)}"


def _consecutive(years: list[str]) -> bool:
    """2016-17, 2017-18, ...: each start year follows the last and each suffix is start + 1."""
    starts = [int(y[:4]) for y in years]
    suffixes_ok = all(y[5:] == f"{(s + 1) % 100:02d}" for y, s in zip(years, starts, strict=True))
    return suffixes_ok and all(b == a + 1 for a, b in zip(starts, starts[1:], strict=False))


def parse_text(text: str, prov: Provenance) -> ParseResult[NepraLoadShedding]:
    res: ParseResult[NepraLoadShedding] = ParseResult("nepra_load_shedding")
    lines = text.splitlines()
    starts = [i for i, ln in enumerate(lines) if HEADING_RE.search(ln)]
    if not starts:
        res.reject(prov, "whole file", "", "no section 3.6 load-shedding heading (older layout)")
        return res
    start = starts[-1]
    years: list[str] = []
    seen: set[str] = set()
    for i in range(start + 1, min(start + WINDOW, len(lines))):
        ln = lines[i]
        if not years:
            found = [_year(m) for m in YEAR_RE.finditer(ln)]
            if len(found) >= 3:
                if not _consecutive(found):
                    res.reject(prov, f"line {i + 1}", ln, "header years are not consecutive")
                    return res
                years = found
            continue
        if TABLE_RE.search(ln) and seen:
            break
        m = ROW_RE.search(ln)
        if not m:
            continue
        company, rest = m.group(1), m.group(2)
        nums = NUM_RE.findall(rest)
        if len(nums) != len(years):
            res.reject(prov, f"line {i + 1}", ln, f"{len(nums)} values for {len(years)} years")
            continue
        if company in seen:
            res.reject(prov, f"line {i + 1}", ln, f"{company} appears twice in the table")
            continue
        seen.add(company)
        for fy, v in zip(years, nums, strict=True):
            hours = float(v)
            if not 0 <= hours <= 24:
                res.reject(prov, f"line {i + 1}", ln, f"{company} {fy}: {v} h/day out of range")
                continue
            res.rows.append(
                NepraLoadShedding(
                    **prov.model_dump(),
                    report_year=years[-1],
                    fiscal_year=fy,
                    company=company,
                    reported_hours_per_day=hours,
                    line=i + 1,
                )
            )
    if not years:
        res.reject(prov, f"line {start + 1}", lines[start], "no fiscal-year header after 3.6")
    elif not seen:
        res.reject(prov, f"line {start + 1}", lines[start], "no company rows after the header")
    return res


def parse_report(path: Path) -> ParseResult[NepraLoadShedding]:
    return parse_text(pdf_text(path), provenance(path))
