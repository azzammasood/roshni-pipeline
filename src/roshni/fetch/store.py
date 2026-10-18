"""Snapshot store: an append-only raw_snapshots.csv log plus content-addressed files.

Layout (in the store root; in production a checkout of branch `data-snapshots` of the private
repo roshni-snapshots):
    raw_snapshots.csv
    files/<source>/<item_key>/<YYYYMMDDTHHMMSSZ>_<sha12><ext>
"""

import csv
from datetime import datetime
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

from pydantic import BaseModel

LOG_NAME = "raw_snapshots.csv"


class SnapshotRecord(BaseModel):
    source: str
    item_key: str
    label: str = ""
    url: str
    fetched_at: str  # UTC, ISO 8601 with Z
    http_status: int | None = None
    etag: str = ""
    last_modified: str = ""
    sha256: str = ""
    bytes: int | None = None
    path: str = ""  # relative to store root, POSIX separators
    changed: bool = False
    note: str = ""


COLUMNS = list(SnapshotRecord.model_fields)


class SnapshotStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.log_path = root / LOG_NAME
        self.records: list[SnapshotRecord] = self._load()

    def _load(self) -> list[SnapshotRecord]:
        if not self.log_path.exists():
            return []
        with self.log_path.open(newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        out = []
        for r in rows:
            r = {k: v for k, v in r.items() if v != ""}
            if "changed" in r:
                r["changed"] = r["changed"] == "true"
            out.append(SnapshotRecord.model_validate(r))
        return out

    def last_good(self, source: str, item_key: str) -> SnapshotRecord | None:
        """Latest record for this item that has content (sha256 known)."""
        for r in reversed(self.records):
            if r.source == source and r.item_key == item_key and r.sha256:
                return r
        return None

    def has_url(self, url: str) -> bool:
        return any(r.url == url and r.sha256 for r in self.records)

    def write_file(
        self,
        source: str,
        item_key: str,
        url: str,
        content: bytes,
        sha256: str,
        at: datetime,
        ext: str | None = None,
    ) -> str:
        """`ext` overrides the URL's suffix (trimmed news feeds are stored as .json)."""
        ext = ext if ext is not None else PurePosixPath(urlsplit(url).path).suffix.lower()
        rel = PurePosixPath("files", source, item_key, f"{at:%Y%m%dT%H%M%SZ}_{sha256[:12]}{ext}")
        dest = self.root.joinpath(*rel.parts)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content)
        return rel.as_posix()

    def append(self, rec: SnapshotRecord) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        new = not self.log_path.exists()
        with self.log_path.open("a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=COLUMNS, lineterminator="\n")
            if new:
                w.writeheader()
            row = rec.model_dump()
            row["changed"] = "true" if rec.changed else "false"
            w.writerow({k: "" if v is None else v for k, v in row.items()})
        self.records.append(rec)
