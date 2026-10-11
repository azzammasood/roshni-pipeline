import json
from datetime import UTC, datetime
from pathlib import Path

import jsonschema
import pytest

from roshni.export import models as m
from roshni.export.build import SCHEMA_DIR, write_schemas


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
           "daily": [0] * 22 + [25, 60], "scenario_levels": None}  # fmt: skip


def test_valid_document_passes() -> None:
    jsonschema.validate(envelope([PROFILE]), schema("dark_profiles"))


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.pop("label"),
        lambda d: d.update(extra="not allowed"),
        lambda d: d["data"][0].update(source="lesco"),
        lambda d: d["data"][0].pop("effective_from"),
    ],
)
def test_invalid_documents_rejected(mutate) -> None:
    doc = envelope([dict(PROFILE)])
    mutate(doc)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(doc, schema("dark_profiles"))
