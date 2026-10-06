from pathlib import Path

import pytest

from roshni.paths import DATA_SOURCES_DIR
from roshni.sources.inventory import EXPECTED_FILES, inventory, sha256_of


def test_sha256_of(tmp_path: Path) -> None:
    p = tmp_path / "x.txt"
    p.write_bytes(b"abc")
    assert sha256_of(p) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_inventory_reports_missing(tmp_path: Path) -> None:
    (tmp_path / EXPECTED_FILES[0]).write_bytes(b"abc")
    (tmp_path / "unrelated.png").write_bytes(b"ignored")
    entries, missing = inventory(tmp_path)
    assert [e.name for e in entries] == [EXPECTED_FILES[0]]
    assert entries[0].bytes == 3
    assert len(missing) == len(EXPECTED_FILES) - 1


@pytest.mark.needs_data_sources
def test_all_expected_files_present() -> None:
    _, missing = inventory(DATA_SOURCES_DIR)
    assert missing == []
