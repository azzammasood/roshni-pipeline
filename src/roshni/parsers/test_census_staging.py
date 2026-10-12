import csv
import json
from pathlib import Path

import duckdb
import pytest

from roshni.parsers import census
from roshni.parsers.run import SCHEDULE_FILES, stage_schedule_files


def _write_log(store: Path, rows: list[dict]) -> None:
    cols = ["source", "item_key", "fetched_at", "sha256", "path", "changed"]
    with (store / "raw_snapshots.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)


def _store_with_all_items(store: Path, version: str) -> None:
    rows = []
    for name, (source, item) in SCHEDULE_FILES.items():
        rel = f"files/{source}/{item}/{version}{Path(name).suffix}"
        (store / rel).parent.mkdir(parents=True, exist_ok=True)
        (store / rel).write_text(f"{name} {version}", encoding="utf-8")
        rows.append({"source": source, "item_key": item, "fetched_at": version, "sha256": version,
                     "path": rel, "changed": "true"})  # fmt: skip
    _write_log(store, rows)


def test_missing_schedule_files_come_from_latest_snapshot(tmp_path: Path) -> None:
    store = tmp_path / "store"
    _store_with_all_items(store, "v1")
    old = (store / "raw_snapshots.csv").read_text(encoding="utf-8")
    _store_with_all_items(store, "v2")  # newer version of every item, appended to the log
    newer = (store / "raw_snapshots.csv").read_text(encoding="utf-8").split("\n", 1)[1]
    (store / "raw_snapshots.csv").write_text(old + newer, encoding="utf-8")
    sources = tmp_path / "sources"
    sources.mkdir()
    (sources / "kelectric-feeder-list.pdf").write_text("hand copy", encoding="utf-8")

    staged = stage_schedule_files(sources, store, tmp_path / "staging")

    assert sorted(p.name for p in staged.iterdir()) == sorted(SCHEDULE_FILES)
    assert (staged / "kelectric-feeder-list.pdf").read_text() == "hand copy"  # local file wins
    assert (staged / "iesco-ajk-sep26.xlsx").read_text() == "iesco-ajk-sep26.xlsx v2"  # newest


def test_complete_sources_folder_is_used_directly(tmp_path: Path) -> None:
    for name in SCHEDULE_FILES:
        (tmp_path / name).write_text("x", encoding="utf-8")
    assert stage_schedule_files(tmp_path, None, tmp_path / "staging") == tmp_path


def test_missing_file_without_snapshot_fails_loudly(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="iesco-"):
        stage_schedule_files(tmp_path, None, tmp_path / "staging")


def _fake_parsed(folder: Path) -> None:
    folder.mkdir()
    for table, cols in census.TABLES.items():
        con = duckdb.connect()
        select = ", ".join(f"'{c}-' || i as {c}" for c in cols)
        con.execute(
            f"copy (select {select}, 'yes' as gas, 1 as extra from range(3) t(i)) "
            f"to '{(folder / f'{table}.parquet').as_posix()}' (format parquet)"
        )
        con.close()


def test_freeze_trims_columns_and_restore_checks_rows(tmp_path: Path) -> None:
    _fake_parsed(tmp_path / "parsed")
    counts = census.freeze(tmp_path / "parsed", tmp_path / "census")
    assert counts == dict.fromkeys(census.TABLES, 3)
    frozen = tmp_path / "census" / "pbs_rural_housing.parquet"
    cols = [r[0] for r in duckdb.sql(f"describe select * from '{frozen.as_posix()}'").fetchall()]
    assert cols == census.TABLES["pbs_rural_housing"] and "gas" not in cols

    assert census.restore(tmp_path / "census", tmp_path / "out") == counts
    manifest = tmp_path / "census" / census.MANIFEST
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["pbs_rural_housing"]["rows"] = 99
    manifest.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="manifest says 99"):
        census.restore(tmp_path / "census", tmp_path / "out")


def test_committed_census_matches_its_manifest() -> None:
    """The committed census/ folder is complete and consistent (runs in CI)."""
    manifest = json.loads((census.CENSUS_DIR / census.MANIFEST).read_text(encoding="utf-8"))
    assert set(manifest) == set(census.TABLES)
    for table, meta in manifest.items():
        assert meta["columns"] == census.TABLES[table]
        path = (census.CENSUS_DIR / f"{table}.parquet").as_posix()
        assert duckdb.sql(f"select count(*) from '{path}'").fetchone()[0] == meta["rows"]
