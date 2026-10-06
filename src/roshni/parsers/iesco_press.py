"""IESCO English press releases: planned power-shutdown windows.

Grammar (free text): a date ("on Sunday, October 04, 2026" or "On 14th September 2026") starts a
day; a time range ("from 08:00 AM to 02:00 PM", "from 7 am to 11 am") applies to the feeder names
that follow it until the next time range; a circle label ("Islamabad Circle:" or "Islamabad
Circle,") persists until the next one. Time and circle may come in either order. A new date resets
both, so nothing carries across days by guesswork: feeders seen without a date, circle and time in
scope are quarantined, as are phrases that are not feeder names.

Two formats are known: development-project notices ("Temporary Power Shutdown Schedule ...") and
system-maintenance notices ("POWER SUSPENSION SCHEDULES FOR ..."). GSO entries in maintenance
notices can be transmission assets ("132KV ..."): kept as printed and flagged `transmission_asset`.
"""

import re
from datetime import UTC, date, datetime, time, timedelta, timezone
from pathlib import Path

from roshni.parsers.common import ParseResult, Provenance, provenance
from roshni.parsers.pdftext import pdf_text

PKT = timezone(timedelta(hours=5), "Asia/Karachi")  # no DST

MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
DAYS = "Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday"
ORD = r"(?:st|nd|rd|th)?"
# "on" is required so a headline date ("SCHEDULES FOR 14th September 2026") does not open the body.
DATE_P = (
    rf"(?i:on)\s+(?:(?P<dow>{DAYS}),?\s+)?"
    rf"(?:(?P<mon>{MONTHS})\s+(?P<day>\d{{1,2}}){ORD}|(?P<day2>\d{{1,2}}){ORD}\s+(?P<mon2>{MONTHS}))"
    r",?\s+(?P<year>\d{4})"
)
AMPM = r"[AaPp]\.?[Mm]\.?"
TIME_P = (
    rf"from\s+(?P<h1>\d{{1,2}})(?::(?P<m1>\d{{2}}))?\s*(?P<ap1>{AMPM})\s+to\s+"
    rf"(?P<h2>\d{{1,2}})(?::(?P<m2>\d{{2}}))?\s*(?P<ap2>{AMPM})"
)
# A circle label starts after ", ", ". ", ": " or " in " so it never swallows a preceding feeder
# name, and its words may not be "Feeder(s)".
CIRCLE_WORD = r"(?!Feeders?\b)[A-Z][A-Za-z&]*\.?"
CIRCLE_P = (
    r"(?:(?<=[,.:] )|(?<= in ))"
    rf"(?P<circle>{CIRCLE_WORD}(?:\s+{CIRCLE_WORD}){{0,3}})\s+Circle\s*[:,.]"
)
TOKEN_RE = re.compile(rf"(?P<date>{DATE_P})|(?P<time>{TIME_P})|(?P<circ>{CIRCLE_P})")
# "X, Y feeders and adjoining areas in Islamabad Circle": the circle follows the list.
TRAILING_CIRCLE_RE = re.compile(r"(?i)\s*feeders?\s+(?:and adjoining areas\s+)?in\s*$")
NOT_A_FEEDER_RE = re.compile(r"(?i)\b(will|remain|closed|along with|surrounding areas)\b")
ASSET_RE = re.compile(r"(?i)\b\d+\s*kv\b")
END_RE = re.compile(r"IESCO management apologizes", re.I)
RELEASE_RE = re.compile(r"Press Release No\s*:?\s*(?P<no>\d+)\s*:\s*(?P<period>\d{1,2}/\d{4})")
FILLER_RE = re.compile(
    r"(?i)^(?:in this regard,?\s*)?(?:there will be a temporary interruption in electricity "
    r"supply in\s*)|^and\s+"
)
SUFFIX_RE = re.compile(r"(?i)\s+feeders?\.?$")
MAX_NAME_WORDS = 6


class PressReleaseWindow(Provenance):
    release_no: str | None
    release_period: str | None  # "10/2026"
    seq: int  # order of appearance within the release
    outage_date: date
    circle: str  # as printed, e.g. "Islamabad", "Rawalpindi City", "GSO"
    feeder_name: str
    start_local: str  # "HH:MM" Asia/Karachi
    end_local: str
    start_utc: datetime
    end_utc: datetime
    flags: str


def _to_24h(h: str, m: str | None, ap: str) -> time:
    hh = int(h) % 12 + (12 if ap.upper().startswith("P") else 0)
    return time(hh, int(m or 0))


def _clean_names(chunk: str) -> list[str]:
    names = []
    for piece in chunk.split(","):
        p = re.sub(r"\s+", " ", piece).strip(" .;")
        p = FILLER_RE.sub("", p).strip(" .;")
        p = SUFFIX_RE.sub("", p).strip(" .;")
        if p and p.lower() not in ("feeder", "feeders"):
            names.append(p)
    return names


def parse_press_release(path: Path) -> ParseResult[PressReleaseWindow]:
    prov = provenance(path)
    res: ParseResult[PressReleaseWindow] = ParseResult("iesco_press_release_window")
    text = re.sub(r"\s+", " ", pdf_text(path).replace("\f", " ")).strip()
    rel = RELEASE_RE.search(text)
    first = next((m for m in TOKEN_RE.finditer(text) if m["date"]), None)
    start = first.start() if first else -1
    if start < 0:
        res.reject(prov, "body", text[:500], "no outage date found")
        return res
    end_m = END_RE.search(text, start)
    body = text[start : end_m.start() if end_m else len(text)]
    if not end_m:
        res.reject(prov, "body", text[-300:], "end marker not found; parsed to end of text")

    day: date | None = None
    circle: str | None = None
    window: tuple[time, time] | None = None
    flags_day = ""
    seq = 0
    pos = 0

    def emit(chunk: str, at: int, extra_flag: str = "") -> None:
        nonlocal seq
        for name in _clean_names(chunk):
            loc = f"char {at}"
            if len(name.split()) > MAX_NAME_WORDS:
                res.reject(prov, loc, name, "suspicious feeder token (too many words)")
                continue
            if NOT_A_FEEDER_RE.search(name):
                res.reject(prov, loc, name, "phrase is not a feeder name")
                continue
            if day is None or circle is None or window is None:
                res.reject(prov, loc, name, "feeder without date, circle and time in scope")
                continue
            t1, t2 = window
            s_local = datetime.combine(day, t1, PKT)
            e_local = datetime.combine(day, t2, PKT)
            flags = [f for f in (flags_day, extra_flag) if f]
            if ASSET_RE.search(name):
                flags.append("transmission_asset")
            if e_local <= s_local:
                e_local += timedelta(days=1)
                flags.append("ends_next_day")
            seq += 1
            res.rows.append(
                PressReleaseWindow(
                    **prov.model_dump(),
                    release_no=rel["no"] if rel else None,
                    release_period=rel["period"] if rel else None,
                    seq=seq,
                    outage_date=day,
                    circle=circle,
                    feeder_name=name,
                    start_local=t1.strftime("%H:%M"),
                    end_local=t2.strftime("%H:%M"),
                    start_utc=s_local.astimezone(UTC),
                    end_utc=e_local.astimezone(UTC),
                    flags=";".join(flags),
                )
            )

    for m in TOKEN_RE.finditer(body):
        chunk = body[pos : m.start()]
        trail = TRAILING_CIRCLE_RE.search(chunk) if m["circ"] and circle is None else None
        if trail:
            circle = re.sub(r"\s+", " ", m["circle"]).strip().rstrip(".")
            emit(chunk[: trail.start()], pos, "circle_after_list")
        else:
            emit(chunk, pos)
        pos = m.end()
        if m["date"]:
            mon, dd = m["mon"] or m["mon2"], m["day"] or m["day2"]
            d = datetime.strptime(f"{mon} {dd} {m['year']}", "%B %d %Y").date()
            day, circle, window = d, None, None
            mismatch = m["dow"] and d.strftime("%A") != m["dow"]
            flags_day = f"weekday_mismatch:{m['dow']}" if mismatch else ""
        elif m["time"]:
            window = (_to_24h(m["h1"], m["m1"], m["ap1"]), _to_24h(m["h2"], m["m2"], m["ap2"]))
        else:
            circle = re.sub(r"\s+", " ", m["circle"]).strip().rstrip(".")
    emit(body[pos:], pos)
    return res
