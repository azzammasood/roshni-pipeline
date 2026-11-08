"""Effective dates for new schedule file versions, decided automatically (owner, 2026-11-08).

`dbt/seeds/source_documents.csv` gives each schedule file version (by SHA-256) the date it
applies from. A new version used to stop the daily build until someone added its row by hand,
which left the site 17 days out of date in October 2026. Now the publish job adds the row:

- K-Electric's schedule PDF prints its own date ("The schedule below is applicable from 23rd
  October, 2026."): that date is used when the first page states it.
- Otherwise (IESCO XLSX, K-Electric's feeder list, a schedule that states no date) the date is the
  file's HTTP Last-Modified in Asia/Karachi, the basis used for every hand-made row so far.

Every automatic row says so in `effective_basis` ("automatic: ..."). Rows already in the seed,
whoever wrote them, are never changed.
"""

import csv
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path

from roshni.parsers.pdftext import PdfTextUnavailable, pdf_text
from roshni.parsers.run import SCHEDULE_FILES

SOURCES = ("iesco_schedule_xlsx", "kelectric_schedule", "kelectric_feeder_list")
FIELDS = [
    "source",
    "source_file",
    "source_sha256",
    "effective_from",
    "effective_basis",
    "published_label",
]
KARACHI = timedelta(hours=5)
MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august", "september",
     "october", "november", "december"], start=1)}  # fmt: skip
APPLIES = re.compile(
    r"applicable\s+from\s+(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+),?\s+(\d{4})", re.I
)
CANONICAL = {key: name for name, key in SCHEDULE_FILES.items()}


@dataclass(frozen=True)
class NewVersion:
    source: str
    item_key: str
    sha256: str
    path: Path
    url: str
    label: str
    last_modified: str
    fetched_at: str


def stated_date(text: str) -> date | None:
    """The date a K-Electric schedule says it applies from, if its text states one."""
    m = APPLIES.search(text)
    if not m or m.group(2).lower() not in MONTHS:
        return None
    try:
        return date(int(m.group(3)), MONTHS[m.group(2).lower()], int(m.group(1)))
    except ValueError:
        return None


def karachi_date(last_modified: str, fetched_at: str) -> date:
    """HTTP Last-Modified as an Asia/Karachi date; the fetch time when the header is missing."""
    try:
        at = parsedate_to_datetime(last_modified)
    except (TypeError, ValueError):
        at = datetime.fromisoformat(fetched_at.replace("Z", "+00:00"))
    return (at.astimezone(UTC) + KARACHI).date()


def new_versions(store: Path, known: set[str]) -> list[NewVersion]:
    """Stored schedule versions with no seed row, first fetch of each SHA-256 only."""
    out: dict[str, NewVersion] = {}
    with (store / "raw_snapshots.csv").open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            sha = r["sha256"]
            if r["source"] not in SOURCES or r["changed"] != "true" or not r["path"]:
                continue
            if sha in known or sha in out:
                continue
            out[sha] = NewVersion(
                r["source"], r["item_key"], sha, store / r["path"], r["url"], r["label"],
                r["last_modified"], r["fetched_at"],
            )  # fmt: skip
    return list(out.values())


def decide(v: NewVersion) -> dict[str, str]:
    when, basis = None, ""
    if v.source == "kelectric_schedule":
        try:
            when = stated_date(pdf_text(v.path, 1, 1))
        except PdfTextUnavailable:
            when = None
        if when:
            basis = f"automatic: the PDF says it is applicable from {when.isoformat()}"
    if when is None:
        when = karachi_date(v.last_modified, v.fetched_at)
        basis = "automatic: HTTP Last-Modified (file states no date)"
    stem = Path(v.url.split("?")[0]).stem
    return {
        "source": v.source,
        "source_file": CANONICAL.get((v.source, v.item_key), f"{v.source}-{v.item_key}"),
        "source_sha256": v.sha256,
        "effective_from": when.isoformat(),
        "effective_basis": basis,
        "published_label": v.label or (stem if v.source == "kelectric_schedule" else ""),
    }


def fill_seed(store: Path, seed: Path) -> list[dict[str, str]]:
    """Append a row for every new schedule version in the store; return the rows added."""
    with seed.open(encoding="utf-8", newline="") as f:
        known = {r["source_sha256"] for r in csv.DictReader(f)}
    added = [decide(v) for v in new_versions(store, known)]
    if added:
        with seed.open("a", encoding="utf-8", newline="") as f:
            csv.DictWriter(f, FIELDS, lineterminator="\n").writerows(added)
    return added
