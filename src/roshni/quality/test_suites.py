import pandas as pd

from roshni.quality.suites import validate_table

SHA = "a" * 64


def schedule_df(minutes: list[int]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "source_file": "s.pdf",
            "source_sha256": SHA,
            "feeder_name_norm": [f"F{i}" for i in range(len(minutes))],
            "grid": "AIRPORT",
            "total_minutes": minutes,
        }
    )


def test_suite_passes_on_valid_data() -> None:
    r = validate_table("kelectric_schedule", schedule_df([360, 720]))
    assert r.success and r.failed == []


def test_suite_flags_invalid_hours() -> None:
    r = validate_table("kelectric_schedule", schedule_df([360, 420]))
    assert not r.success
    assert r.failed == ["expect_column_values_to_be_in_set(total_minutes)"]
