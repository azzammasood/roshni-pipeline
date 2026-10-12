"""Run every parser over data-sources/ (and optionally a snapshot store); write Parquet."""

import csv
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from roshni.parsers import census, iesco_press, iesco_xlsx, kelectric, pbs_rural, pbs_urban
from roshni.parsers.common import ParseResult, write_result
from roshni.sources.inventory import IESCO_CIRCLES, sha256_of


@dataclass
class TableSummary:
    table: str
    rows: int
    quarantined: int


def _snapshot_index(store: Path | None) -> dict[str, tuple[Path, datetime | None, str]]:
    """sha256 -> (file path, fetched_at, source) for every stored snapshot file."""
    if store is None or not (store / "raw_snapshots.csv").exists():
        return {}
    out = {}
    with (store / "raw_snapshots.csv").open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if r["changed"] == "true" and r["path"]:
                at = datetime.fromisoformat(r["fetched_at"].replace("Z", "+00:00"))
                out[r["sha256"]] = (store / r["path"], at, r["source"])
    return out


# Canonical file name -> (snapshot source, item key). The daily job has no data-sources/, so a
# missing schedule file is staged from the latest snapshot of its item under its canonical name:
# source_file stays identical to a local run (effective_from is keyed by SHA-256 anyway).
SCHEDULE_FILES: dict[str, tuple[str, str]] = {
    **{f"iesco-{c}-sep26.xlsx": ("iesco_schedule_xlsx", c) for c in IESCO_CIRCLES},
    "kelectric-feeder-list.pdf": ("kelectric_feeder_list", "Feeders-List"),
    "kelectric-load-shed-schedule.pdf": ("kelectric_schedule", "schedule"),
}


def _latest_snapshot_files(store: Path | None) -> dict[tuple[str, str], Path]:
    """(source, item_key) -> newest stored file (the log is append-only, oldest first)."""
    if store is None or not (store / "raw_snapshots.csv").exists():
        return {}
    out = {}
    with (store / "raw_snapshots.csv").open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if r["changed"] == "true" and r["path"]:
                out[(r["source"], r["item_key"])] = store / r["path"]
    return out


def stage_schedule_files(sources_dir: Path, store: Path | None, staging: Path) -> Path:
    """Folder holding every schedule file under its canonical name.

    Files present in `sources_dir` are used as they are; missing ones are copied from the
    snapshot store. Returns `sources_dir` itself when nothing is missing.
    """
    missing = [n for n in SCHEDULE_FILES if not (sources_dir / n).exists()]
    if not missing:
        return sources_dir
    latest = _latest_snapshot_files(store)
    staging.mkdir(parents=True, exist_ok=True)
    for name in SCHEDULE_FILES:
        src = sources_dir / name if name not in missing else latest.get(SCHEDULE_FILES[name])
        if src is None:
            raise FileNotFoundError(f"{name}: not in {sources_dir} and no snapshot in {store}")
        shutil.copyfile(src, staging / name)
    return staging


def _stamp(res: ParseResult, fetched: dict[str, datetime | None]) -> ParseResult:
    for row in res.rows:
        if getattr(row, "fetched_at", "missing") is None and row.source_sha256 in fetched:
            row.fetched_at = fetched[row.source_sha256]
    return res


def run_all(
    sources_dir: Path, out_dir: Path, store: Path | None = None, census_dir: Path | None = None
) -> list[TableSummary]:
    """Parse everything. `census_dir` (committed census tables) replaces parsing the census
    files, which only exist in a local data-sources/ folder."""
    with tempfile.TemporaryDirectory(prefix="roshni-staging-") as tmp:
        files = stage_schedule_files(sources_dir, store, Path(tmp))
        return _run_all(sources_dir, files, out_dir, store, census_dir)


def _run_all(
    sources_dir: Path, files: Path, out_dir: Path, store: Path | None, census_dir: Path | None
) -> list[TableSummary]:
    snaps = _snapshot_index(store)
    fetched = {sha: at for sha, (_, at, _) in snaps.items()}
    results: list[tuple[ParseResult, type]] = []

    feeders = ParseResult("iesco_feeder")
    slots = ParseResult("iesco_schedule_slot")
    for c in IESCO_CIRCLES:
        f, s = iesco_xlsx.parse_iesco_xlsx(files / f"iesco-{c}-sep26.xlsx", c)
        feeders.extend(f)
        slots.extend(s)
    results += [(feeders, iesco_xlsx.IescoFeeder), (slots, iesco_xlsx.IescoSlot)]

    press = ParseResult("iesco_press_release_window")
    pdfs = {sha256_of(p): p for p in sorted(sources_dir.glob("iesco-press-release-eng-*.pdf"))}
    for sha, (path, _, source) in snaps.items():
        if source == "iesco_press_release":
            pdfs.setdefault(sha, path)
    for path in pdfs.values():
        press.extend(iesco_press.parse_press_release(path))
    results.append((press, iesco_press.PressReleaseWindow))

    results.append(
        (kelectric.parse_feeder_list(files / "kelectric-feeder-list.pdf"),
         kelectric.KeFeederListRow)
    )  # fmt: skip
    sched, cycles = kelectric.parse_schedule(files / "kelectric-load-shed-schedule.pdf")
    results += [(sched, kelectric.KeScheduleRow), (cycles, kelectric.KeCycle)]

    summaries = []
    if census_dir is not None:
        for table, rows in census.restore(census_dir, out_dir).items():
            summaries.append(TableSummary(table, rows, 0))
    for t in (33, 34) if census_dir is None else ():
        res = ParseResult(pbs_urban.TABLES[t][0])
        for prov in ("islamabad", "punjab_districts"):
            res.extend(pbs_urban.parse_urban(sources_dir / f"table_{t}_{prov}.xlsx"))
        res.extend(pbs_urban.parse_urban(sources_dir / f"table_{t}_sindh_districts.pdf"))
        results.append((res, pbs_urban.MODELS[t]))
    for t in (31, 32) if census_dir is None else ():
        res = ParseResult(pbs_rural.TABLES[t][0])
        for prov in ("islamabad", "punjab_districts"):
            res.extend(pbs_rural.parse_rural(sources_dir / f"table_{t}_{prov}.pdf"))
        results.append((res, pbs_rural.MODELS[t]))

    for res, model in results:
        write_result(_stamp(res, fetched), model, out_dir)
        summaries.append(TableSummary(res.table, len(res.rows), len(res.quarantine)))
    return summaries
