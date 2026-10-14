"""NEPRA order on K-Electric (section 27C, 2026-08-31): the regulator's analysis of outage data
K-Electric supplied for 620 listed feeders, by loss category (via poppler `pdftotext -layout`).

Two tables are read as printed: the category summary (feeders, consumers, average AT&C %,
scheduled hours a day) and, per category, feeders by average daily outage band. These are NEPRA's
figures from K-Electric's data, not Roshni measurements; the order does not state the period.
Bands must add up to their category's totals, or the category is quarantined.
"""

import re
from datetime import date, datetime
from pathlib import Path

from roshni.parsers.common import ParseResult, Provenance, provenance
from roshni.parsers.pdftext import pdf_text

CATEGORIES = ("Very High Loss", "High Loss", "Medium Loss")
INT = r"\d{1,3}(?:,\d{3})*"
SUMMARY_RE = re.compile(
    rf"^\s*(Very High Loss|High Loss|Medium Loss)\s+(\d+)\s+({INT})\s+(\d+)%"
    r"\s+(\d{1,2}):(\d{2})\s*$"
)
SECTION_RE = re.compile(r"^\s*(?:i{1,3})\.\s+(Very High Loss|High Loss|Medium Loss) Feeders:", re.I)
# "Upto 06:00", "06:00-08:00+", "10:00-12:00", "Above 14:00", "14:00-18:00+"
HHMM = r"\d{2}:\d{2}"
BAND_RE = re.compile(
    rf"^\s*(Upto {HHMM}|Above {HHMM}|{HHMM}-{HHMM}\+?)\s+(\d+)\s+({INT})"
    r"\s+([\d.]+)%\s+([\d.]+)%\s*$"
)
TOTAL_RE = re.compile(rf"^\s*(\d+)\s+({INT})\s+100\.0%\s+100\.0%\s*$")
DATE_RE = re.compile(
    r"(January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+(\d{1,2}),\s+(20\d{2})"
)


class KeOrderCategory(Provenance):
    order_date: date
    category: str  # Very High Loss | High Loss | Medium Loss (as printed)
    feeders: int
    consumers: int
    avg_atc_loss_pct: int
    scheduled_minutes_per_day: int  # K-Electric's own AT&C-based schedule for the category


class KeOrderBand(Provenance):
    category: str
    band: str  # as printed, e.g. "10:00-12:00"
    lower_minutes: int  # 0 for "Upto"
    upper_minutes: int | None  # None for "Above" / "...+"
    feeders: int
    consumers: int
    pct_feeders: float  # as printed
    pct_consumers: float


def _hm(s: str) -> int:
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def _band_bounds(band: str) -> tuple[int, int | None]:
    if band.startswith("Upto"):
        return 0, _hm(band.split()[1])
    if band.startswith("Above"):
        return _hm(band.split()[1]), None
    lo, hi = band.rstrip("+").split("-")
    return _hm(lo), None if band.endswith("+") else _hm(hi)


def parse_text(
    text: str, prov: Provenance
) -> tuple[ParseResult[KeOrderCategory], ParseResult[KeOrderBand]]:
    cats: ParseResult[KeOrderCategory] = ParseResult("nepra_ke_order_category")
    bands: ParseResult[KeOrderBand] = ParseResult("nepra_ke_order_band")
    lines = text.splitlines()
    m = DATE_RE.search("\n".join(lines[:30]))
    if not m:
        cats.reject(prov, "first 30 lines", "", "no order date")
        return cats, bands
    when = datetime.strptime(f"{m.group(1)} {m.group(2)} {m.group(3)}", "%B %d %Y").date()

    summary = {}
    for ln in lines:
        if s := SUMMARY_RE.match(ln):
            name, feeders, consumers, atc, h, mi = s.groups()
            summary[name] = KeOrderCategory(
                **prov.model_dump(), order_date=when, category=name, feeders=int(feeders),
                consumers=int(consumers.replace(",", "")), avg_atc_loss_pct=int(atc),
                scheduled_minutes_per_day=int(h) * 60 + int(mi),
            )  # fmt: skip

    section = None
    found: dict[str, list[KeOrderBand]] = {}
    totals: dict[str, tuple[int, int]] = {}
    for ln in lines:
        if s := SECTION_RE.match(ln):
            section = next(c for c in CATEGORIES if c.lower() == s.group(1).lower())
            continue
        if section is None:
            continue
        if b := BAND_RE.match(ln):
            band, feeders, consumers, pf, pc = b.groups()
            lo, hi = _band_bounds(band)
            found.setdefault(section, []).append(
                KeOrderBand(
                    **prov.model_dump(), category=section, band=band, lower_minutes=lo,
                    upper_minutes=hi, feeders=int(feeders),
                    consumers=int(consumers.replace(",", "")),
                    pct_feeders=float(pf), pct_consumers=float(pc),
                )
            )  # fmt: skip
        elif (t := TOTAL_RE.match(ln)) and section in found and section not in totals:
            totals[section] = (int(t.group(1)), int(t.group(2).replace(",", "")))

    for name in CATEGORIES:
        cat, rows = summary.get(name), found.get(name, [])
        if cat is None:
            cats.reject(prov, name, "", "category missing from the summary table")
            continue
        sums = (sum(r.feeders for r in rows), sum(r.consumers for r in rows))
        if not rows or sums != (cat.feeders, cat.consumers) or totals.get(name) != sums:
            raw = (
                f"bands {sums}, total row {totals.get(name)}, summary {cat.feeders, cat.consumers}"
            )
            cats.reject(prov, name, raw, "outage bands do not add up to the category totals")
            continue
        cats.rows.append(cat)
        bands.rows.extend(rows)
    return cats, bands


def parse_order(path: Path):
    return parse_text(pdf_text(path), provenance(path))
