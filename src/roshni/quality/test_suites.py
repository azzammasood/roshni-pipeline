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
    r = validate_table("kelectric_schedule", schedule_df([360, 1500]))  # more than a day
    assert not r.success
    assert r.failed == ["expect_column_values_to_be_between(total_minutes)"]


def test_suite_accepts_other_daily_totals() -> None:
    # K-Electric may change its hours: a 7 h feeder is valid data (flagged by the parser).
    assert validate_table("kelectric_schedule", schedule_df([360, 420])).success
