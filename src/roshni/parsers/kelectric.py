"""K-Electric feeder list and load-shed schedule PDFs (via poppler `pdftotext -layout`)."""

import re
from pathlib import Path

from pydantic import BaseModel

from roshni.parsers.common import ParseResult, Provenance, provenance
from roshni.parsers.pdftext import pdf_text

CATEGORIES = ("Medium", "High", "Very High")

LIST_RE = re.compile(
    r"^\s*(?P<sno>\d+)\s+(?P<name>.+?)\s{2,}(?P<ibc>IBC\s*-\s*.+?)\s{2,}"
    r"(?P<atc>\d+(?:\.\d+)?%|-)\s+(?P<cat>Very High|High|Medium) Loss\s*$"
)
CYCLE = r"(\d{4})\s*~\s*(\d{4})"
# Name and grid are separated by 2+ spaces; a grid may contain single spaces ("ELENDER RD").
# finditer (not match) so two rows glued onto one line are both recovered.
SCHED_RE = re.compile(
    rf"(?P<name>\S.*?)\s{{2,}}(?P<grid>\S+(?: \S+)*)\s{{2,}}{CYCLE}\s+{CYCLE}\s+{CYCLE}\s+{CYCLE}"
)
GLUE_RE = re.compile(r"(\d{4}~\d{4})(?=[A-Z])")


def normalise_name(name: str) -> str:
    """Join key between list and schedule: uppercase, alphanumerics only."""
    return re.sub(r"[^A-Z0-9]", "", name.upper())


class KeFeederListRow(Provenance):
    serial: int
    feeder_name: str
    feeder_name_norm: str
    ibc: str
    atc_loss_pct: float | None  # ATC(OI) %, None when printed as "-"
    category: str  # Medium | High | Very High
    page: int


class KeScheduleRow(Provenance):
    feeder_name: str
    feeder_name_norm: str
    grid: str
    page: int
    total_minutes: int
    flags: str


class KeCycle(BaseModel):
    feeder_name_norm: str
    grid: str
    cycle_no: int  # 1..4
    start_hhmm: str  # Asia/Karachi local, "HHMM"
    end_hhmm: str
    wraps_midnight: bool
    minutes: int


def _hhmm_to_min(s: str) -> int:
    h, m = int(s[:2]), int(s[2:])
    if not (0 <= h <= 24 and 0 <= m <= 59) or (h == 24 and m):
        raise ValueError(f"bad time {s}")
    return h * 60 + m


def cycle_minutes(start: str, end: str) -> tuple[int, bool]:
    a, b = _hhmm_to_min(start), _hhmm_to_min(end)
    if b > a:
        return b - a, False
    return b + 1440 - a, True


def _pages(path: Path) -> list[list[str]]:
    return [p.splitlines() for p in pdf_text(path).split("\f")]


def parse_feeder_list(path: Path) -> ParseResult[KeFeederListRow]:
    prov = provenance(path)
    res: ParseResult[KeFeederListRow] = ParseResult("kelectric_feeder_list")
    for pno, lines in enumerate(_pages(path), start=1):
        for lno, line in enumerate(lines, start=1):
            s = line.strip()
            if not s or s.startswith(("List of Feeders", "S. No.")):
                continue
            m = LIST_RE.match(line)
            if not m:
                res.reject(prov, f"page {pno} line {lno}", line, "unrecognised feeder-list line")
                continue
            name = re.sub(r"\s+", " ", m["name"]).strip()
            res.rows.append(
                KeFeederListRow(
                    **prov.model_dump(),
                    serial=int(m["sno"]),
                    feeder_name=name,
                    feeder_name_norm=normalise_name(name),
                    ibc=re.sub(r"\s+", " ", m["ibc"]).strip(),
                    atc_loss_pct=None if m["atc"] == "-" else float(m["atc"].rstrip("%")),
                    category=m["cat"],
                    page=pno,
                )
            )
    return res


def parse_schedule(path: Path) -> tuple[ParseResult, ParseResult]:
    """Return (feeders, cycles). Every feeder must total exactly 6 h or 12 h, else quarantine."""
    prov = provenance(path)
    feeders: ParseResult[KeScheduleRow] = ParseResult("kelectric_schedule")
    cycles: ParseResult[KeCycle] = ParseResult("kelectric_schedule_cycle")
    for pno, lines in enumerate(_pages(path), start=1):
        for lno, line in enumerate(lines, start=1):
            if "~" not in line:
                continue
            text = GLUE_RE.sub(r"\1   ", line)
            matches = list(SCHED_RE.finditer(text))
            n_cycles = len(re.findall(CYCLE, text))
            if not matches or n_cycles != 4 * len(matches):
                feeders.reject(prov, f"page {pno} line {lno}", line, "unrecognised schedule line")
                continue
            for m in matches:
                name = re.sub(r"\s+", " ", m["name"]).strip()
                grid = re.sub(r"\s+", " ", m["grid"]).strip()
                times = m.groups()[2:]
                try:
                    parts = [cycle_minutes(times[i], times[i + 1]) for i in range(0, 8, 2)]
                except ValueError as e:
                    feeders.reject(prov, f"page {pno} line {lno}", line, str(e))
                    continue
                total = sum(p[0] for p in parts)
                if total not in (360, 720):
                    feeders.reject(
                        prov,
                        f"page {pno} line {lno}",
                        line,
                        f"total {total} min is not 6 h or 12 h",
                    )
                    continue
                norm = normalise_name(name)
                flags = "glued_line" if len(matches) > 1 else ""
                feeders.rows.append(
                    KeScheduleRow(
                        **prov.model_dump(),
                        feeder_name=name,
                        feeder_name_norm=norm,
                        grid=grid,
                        page=pno,
                        total_minutes=total,
                        flags=flags,
                    )
                )
                for i, (mins, wrap) in enumerate(parts):
                    cycles.rows.append(
                        KeCycle(
                            feeder_name_norm=norm,
                            grid=grid,
                            cycle_no=i + 1,
                            start_hhmm=times[2 * i],
                            end_hhmm=times[2 * i + 1],
                            wraps_midnight=wrap,
                            minutes=mins,
                        )
                    )
    return feeders, cycles


class KeScheduleVersion(Provenance):
    """One stored version of K-Electric's schedule PDF, summarised (its effective date comes from
    the source_documents seed by SHA-256). Every version is kept, so a month keeps the schedule
    that was in force then after K-Electric publishes a new one."""

    feeders: int
    avg_scheduled_minutes: float  # mean daily scheduled minutes across the feeders in the file
    quarantined: int  # schedule lines this version could not parse


def summarize_version(sched: ParseResult) -> list[KeScheduleVersion]:
    """Summary of one parsed schedule file (empty if no rows parsed)."""
    if not sched.rows:
        return []
    first = sched.rows[0]
    return [
        KeScheduleVersion(
            source_file=first.source_file,
            source_sha256=first.source_sha256,
            fetched_at=first.fetched_at,
            feeders=len(sched.rows),
            avg_scheduled_minutes=sum(r.total_minutes for r in sched.rows) / len(sched.rows),
            quarantined=len(sched.quarantine),
        )
    ]
