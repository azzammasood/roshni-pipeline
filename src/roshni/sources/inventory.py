"""Inventory of the hand-downloaded files in data-sources/ (never tracked in git)."""

import hashlib
from dataclasses import dataclass
from pathlib import Path

IESCO_CIRCLES = ("islamabad", "rawalpindi", "attock", "jhelum", "chakwal", "ajk")

EXPECTED_FILES: tuple[str, ...] = (
    *(f"iesco-{c}-sep26.xlsx" for c in IESCO_CIRCLES),
    "iesco-press-release-eng-oct3.pdf",
    "iesco-press-release-eng-oct5.pdf",
    "iesco-press-release-urdu-oct5.pdf",
    "kelectric-feeder-list.pdf",
    "kelectric-load-shed-schedule.pdf",
    "table_33_punjab_districts.xlsx",
    "table_33_islamabad.xlsx",
    "table_33_sindh_districts.pdf",
    "table_34_punjab_districts.xlsx",
    "table_34_islamabad.xlsx",
    "table_34_sindh_districts.pdf",
    "table_31_punjab_districts.pdf",
    "table_31_islamabad.pdf",
    "table_32_punjab_districts.pdf",
    "table_32_islamabad.pdf",
)


@dataclass(frozen=True)
class FileEntry:
    name: str
    bytes: int
    sha256: str


def sha256_of(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while block := f.read(chunk):
            h.update(block)
    return h.hexdigest()


def inventory(folder: Path) -> tuple[list[FileEntry], list[str]]:
    """Return (entries for expected files that exist, names of expected files missing).

    Only files listed in EXPECTED_FILES are touched; anything else in the folder is ignored.
    """
    entries, missing = [], []
    for name in EXPECTED_FILES:
        p = folder / name
        if p.is_file():
            entries.append(FileEntry(name, p.stat().st_size, sha256_of(p)))
        else:
            missing.append(name)
    return entries, missing
