"""Run every parser over data-sources/ (and optionally a snapshot store); write Parquet."""

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from roshni.parsers import iesco_press, iesco_xlsx, kelectric, pbs_rural, pbs_urban
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


def _stamp(res: ParseResult, fetched: dict[str, datetime | None]) -> ParseResult:
    for row in res.rows:
        if getattr(row, "fetched_at", "missing") is None and row.source_sha256 in fetched:
            row.fetched_at = fetched[row.source_sha256]
    return res


def run_all(sources_dir: Path, out_dir: Path, store: Path | None = None) -> list[TableSummary]:
    snaps = _snapshot_index(store)
    fetched = {sha: at for sha, (_, at, _) in snaps.items()}
    results: list[tuple[ParseResult, type]] = []

    feeders = ParseResult("iesco_feeder")
    slots = ParseResult("iesco_schedule_slot")
    for c in IESCO_CIRCLES:
        f, s = iesco_xlsx.parse_iesco_xlsx(sources_dir / f"iesco-{c}-sep26.xlsx", c)
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
        (kelectric.parse_feeder_list(sources_dir / "kelectric-feeder-list.pdf"),
         kelectric.KeFeederListRow)
    )  # fmt: skip
    sched, cycles = kelectric.parse_schedule(sources_dir / "kelectric-load-shed-schedule.pdf")
    results += [(sched, kelectric.KeScheduleRow), (cycles, kelectric.KeCycle)]

    for t in (33, 34):
        res = ParseResult(pbs_urban.TABLES[t][0])
        for prov in ("islamabad", "punjab_districts"):
            res.extend(pbs_urban.parse_urban(sources_dir / f"table_{t}_{prov}.xlsx"))
        res.extend(pbs_urban.parse_urban(sources_dir / f"table_{t}_sindh_districts.pdf"))
        results.append((res, pbs_urban.MODELS[t]))
    for t in (31, 32):
        res = ParseResult(pbs_rural.TABLES[t][0])
        for prov in ("islamabad", "punjab_districts"):
            res.extend(pbs_rural.parse_rural(sources_dir / f"table_{t}_{prov}.pdf"))
        results.append((res, pbs_rural.MODELS[t]))

    summaries = []
    for res, model in results:
        write_result(_stamp(res, fetched), model, out_dir)
        summaries.append(TableSummary(res.table, len(res.rows), len(res.quarantine)))
    return summaries
