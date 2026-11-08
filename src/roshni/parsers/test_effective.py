import csv
from datetime import date
from pathlib import Path

import pytest

from roshni.parsers import effective
from roshni.parsers.effective import fill_seed, karachi_date, stated_date

HEADER = "source,item_key,label,url,fetched_at,http_status,etag,last_modified,sha256,bytes,path,changed,note\n"
SEED = "source,source_file,source_sha256,effective_from,effective_basis,published_label\n"


def test_stated_date_reads_k_electric_wording() -> None:
    text = "or low loss respectively. The schedule below is applicable from 23rd October, 2026."
    assert stated_date(text) == date(2026, 10, 23)
    assert stated_date("applicable from 5 August 2026") == date(2026, 8, 5)
    assert stated_date("no date here") is None
    assert stated_date("applicable from 31st February, 2026") is None


def test_karachi_date_from_last_modified() -> None:
    # 22:00 UTC is already the next day in Karachi (UTC+5).
    assert karachi_date("Thu, 22 Oct 2026 22:00:00 GMT", "") == date(2026, 10, 23)
    assert karachi_date("", "2026-10-23T05:05:25Z") == date(2026, 10, 23)


def _store(tmp: Path, rows: list[str]) -> Path:
    (tmp / "raw_snapshots.csv").write_text(HEADER + "".join(rows), encoding="utf-8")
    return tmp


def test_fill_seed_adds_new_versions_once_and_keeps_existing_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        effective,
        "pdf_text",
        lambda *_: "The schedule below is applicable from 23rd October, 2026.",
    )
    store = _store(tmp_path, [
        "kelectric_schedule,schedule,,https://ke.com.pk/x/LSM-Oct-2028.pdf,2026-10-23T05:05:25Z,200,,"
        '"Thu, 22 Oct 2026 13:34:52 GMT",bbb,1,files/k.pdf,true,\n',
        "kelectric_schedule,schedule,,https://ke.com.pk/x/LSM-Oct-2028.pdf,2026-10-24T05:05:25Z,304,,"
        '"Thu, 22 Oct 2026 13:34:52 GMT",bbb,1,files/k.pdf,false,not modified\n',
        "iesco_schedule_xlsx,islamabad,Nov-2026,https://iesco.com.pk/a.xlsx,2026-11-02T05:00:00Z,200,,"
        '"Sun, 01 Nov 2026 10:00:00 GMT",ccc,1,files/i.xlsx,true,\n',
        "iesco_schedule_xlsx,islamabad,Sep-2026,https://iesco.com.pk/o.xlsx,2026-10-06T05:00:00Z,200,,"
        '"Wed, 14 Jan 2026 10:00:00 GMT",aaa,1,files/o.xlsx,true,\n',
        "iesco_maintenance_xlsx,islamabad,,https://iesco.com.pk/m.xlsx,2026-11-02T05:00:00Z,200,,,ddd,1,files/m.xlsx,true,\n",
    ])  # fmt: skip
    seed = tmp_path / "source_documents.csv"
    seed.write_text(
        SEED + "iesco_schedule_xlsx,iesco-islamabad-sep26.xlsx,aaa,2026-01-14,by hand,Sep-2026\n"
    )

    added = fill_seed(store, seed)
    assert [(r["source_sha256"], r["effective_from"]) for r in added] == [
        ("bbb", "2026-10-23"),
        ("ccc", "2026-11-01"),
    ]
    rows = list(csv.DictReader(seed.open(encoding="utf-8")))
    assert rows[0]["effective_basis"] == "by hand"  # never changed
    assert rows[1]["source_file"] == "kelectric-load-shed-schedule.pdf"
    assert rows[1]["effective_basis"].startswith("automatic: the PDF says")
    assert rows[1]["published_label"] == "LSM-Oct-2028"
    assert rows[2]["source_file"] == "iesco-islamabad-sep26.xlsx"
    assert rows[2]["effective_basis"] == "automatic: HTTP Last-Modified (file states no date)"
    assert fill_seed(store, seed) == []  # idempotent


def test_schedule_without_a_stated_date_falls_back_to_last_modified(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(effective, "pdf_text", lambda *_: "Load-shed Schedule for KE territory")
    store = _store(tmp_path, [
        "kelectric_schedule,schedule,,https://ke.com.pk/x/s.pdf,2026-12-01T05:00:00Z,200,,"
        '"Mon, 30 Nov 2026 20:00:00 GMT",eee,1,files/s.pdf,true,\n',
    ])  # fmt: skip
    seed = tmp_path / "source_documents.csv"
    seed.write_text(SEED)
    (row,) = fill_seed(store, seed)
    assert row["effective_from"] == "2026-12-01"
    assert row["effective_basis"] == "automatic: HTTP Last-Modified (file states no date)"
