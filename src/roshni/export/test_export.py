import json
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import jsonschema
import pytest

from roshni.export import models as m
from roshni.export.build import SCHEMA_DIR, _rows, hourly_minutes, utc_session, write_schemas


def test_committed_schemas_match_models(tmp_path: Path) -> None:
    for generated in write_schemas(tmp_path):
        committed = SCHEMA_DIR / generated.name
        assert committed.exists(), f"missing {committed}; run `roshni export --write-schemas`"
        assert json.loads(committed.read_text(encoding="utf-8")) == json.loads(
            generated.read_text(encoding="utf-8")
        ), f"{generated.name} drifted; bump the schema and run `roshni export --write-schemas`"


def schema(name: str) -> dict:
    return json.loads((SCHEMA_DIR / f"{name}.schema.json").read_text(encoding="utf-8"))


def envelope(data) -> dict:
    now = datetime(2026, 10, 11, tzinfo=UTC).isoformat()
    return dict(schema_id="roshni/dark_profiles/v1", schema_version=m.SCHEMA_VERSION,
                generated_at=now, last_updated=now, label=m.LABEL, data=data)  # fmt: skip


PROFILE = {"feeder_id": "ke:A", "source": "kelectric", "effective_from": "2026-08-05",
           "daily": [0] * 22 + [25, 60], "scenario_levels": None,
           "daily_windows": [{"start_min": 1355, "end_min": 1440}]}  # fmt: skip


def test_v1_0_document_still_valid() -> None:
    """1.1.0 is additive: a profile without daily_windows (1.0.0 shape) still validates."""
    old = {k: v for k, v in PROFILE.items() if k != "daily_windows"}
    jsonschema.validate(envelope([old]), schema("dark_profiles"))


def test_hourly_minutes_from_windows() -> None:
    wrap = [m.Window(start_min=22 * 60 + 35, end_min=2 * 60 + 5)]  # 22:35~02:05
    assert hourly_minutes(wrap) == [60, 60, 5] + [0] * 19 + [25, 60]
    assert hourly_minutes([m.Window(start_min=1380, end_min=1440)])[23] == 60


def test_valid_document_passes() -> None:
    jsonschema.validate(envelope([PROFILE]), schema("dark_profiles"))


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.pop("label"),
        lambda d: d.update(extra="not allowed"),
        lambda d: d["data"][0].update(source="lesco"),
        lambda d: d["data"][0].pop("effective_from"),
        lambda d: d["data"][0].update(daily_windows=[{"start_min": 0, "end_min": 0}]),
        lambda d: d["data"][0].update(daily_windows=[{"start_min": 1440, "end_min": 60}]),
    ],
)
def test_invalid_documents_rejected(mutate) -> None:
    doc = envelope([dict(PROFILE)])
    mutate(doc)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(doc, schema("dark_profiles"))


def test_export_session_is_utc_on_any_machine() -> None:
    """Regression: on a machine in Asia/Karachi, *_utc fields were written as +05:00."""
    con = duckdb.connect()
    con.execute("set TimeZone = 'Asia/Karachi'")
    utc_session(con)
    (row,) = _rows(con, "select timestamptz '2026-09-10 05:00:00+05' as start_utc")
    assert row["start_utc"].utcoffset().total_seconds() == 0
    assert row["start_utc"].hour == 0
