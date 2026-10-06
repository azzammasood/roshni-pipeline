"""Great Expectations suites for each parsed Parquet table.

Scope: single-table validity (types, domains, ranges, formats, uniqueness of natural keys).
Cross-table rules and golden counts live in dbt tests and pytest respectively, never duplicated.
Suites are defined in code and run with an ephemeral GX context.
"""

import copy
from dataclasses import dataclass
from pathlib import Path

import great_expectations as gx
import great_expectations.expectations as gxe
import pandas as pd
from great_expectations.data_context.types.base import ProgressBarsConfig

SHA = r"^[0-9a-f]{64}$"
PROVENANCE = [
    gxe.ExpectColumnValuesToNotBeNull(column="source_file"),
    gxe.ExpectColumnValuesToMatchRegex(column="source_sha256", regex=SHA),
]
URBAN_LEVELS = ["district", "tehsil", "body", "charge", "circle"]
RURAL_LEVELS = ["district", "tehsil", "qh", "pc", "mauza"]


def _pct(col: str) -> gxe.Expectation:
    return gxe.ExpectColumnValuesToBeBetween(column=col, min_value=0, max_value=100)


def _household_size() -> gxe.Expectation:
    # Published values reach ~98 in tiny (likely institutional) units with 1-2 housing units.
    return gxe.ExpectColumnValuesToBeBetween(
        column="avg_household_size", min_value=0, max_value=100
    )


def _nonneg(*cols: str) -> list[gxe.Expectation]:
    return [gxe.ExpectColumnValuesToBeBetween(column=c, min_value=0) for c in cols]


SUITES: dict[str, list[gxe.Expectation]] = {
    "iesco_feeder": [
        *PROVENANCE,
        gxe.ExpectColumnValuesToBeInSet(
            column="circle",
            value_set=["islamabad", "rawalpindi", "attock", "jhelum", "chakwal", "ajk"],
        ),
        gxe.ExpectColumnValuesToNotBeNull(column="feeder_name"),
        gxe.ExpectColumnValuesToNotBeNull(column="feeder_code_raw"),
        # Known anomaly: 3 feeders coded "NOT ALLOTED" have no numeric code (flagged, not fixed).
        gxe.ExpectColumnValuesToNotBeNull(column="feeder_code", mostly=0.99),
        gxe.ExpectColumnValuesToMatchRegex(column="feeder_code", regex=r"^\d{6}$"),
        gxe.ExpectCompoundColumnsToBeUnique(column_list=["circle", "sheet_row"]),
    ],
    "iesco_schedule_slot": [
        gxe.ExpectColumnValuesToBeInSet(column="level_hours", value_set=[2, 4, 6, 8, 10, 12]),
        gxe.ExpectColumnValuesToBeBetween(column="slot_start_hour", min_value=0, max_value=23),
        gxe.ExpectColumnValuesToBeBetween(column="slot_end_hour", min_value=1, max_value=24),
        gxe.ExpectCompoundColumnsToBeUnique(
            column_list=["circle", "sheet_row", "level_hours", "slot_start_hour"]
        ),
    ],
    "iesco_press_release_window": [
        *PROVENANCE,
        gxe.ExpectColumnValuesToNotBeNull(column="outage_date"),
        gxe.ExpectColumnValuesToNotBeNull(column="circle"),
        gxe.ExpectColumnValuesToNotBeNull(column="feeder_name"),
        gxe.ExpectColumnValuesToMatchRegex(column="start_local", regex=r"^\d{2}:\d{2}$"),
        gxe.ExpectColumnValuesToMatchRegex(column="end_local", regex=r"^\d{2}:\d{2}$"),
        gxe.ExpectColumnPairValuesAToBeGreaterThanB(column_A="end_utc", column_B="start_utc"),
        gxe.ExpectCompoundColumnsToBeUnique(column_list=["source_sha256", "seq"]),
    ],
    "kelectric_feeder_list": [
        *PROVENANCE,
        gxe.ExpectColumnValuesToBeUnique(column="serial"),
        gxe.ExpectColumnValuesToBeUnique(column="feeder_name_norm"),
        gxe.ExpectColumnValuesToBeInSet(
            column="category", value_set=["Medium", "High", "Very High"]
        ),
        gxe.ExpectColumnValuesToMatchRegex(column="ibc", regex=r"^IBC - "),
        # Known: 2 feeders have no published loss figure.
        gxe.ExpectColumnValuesToNotBeNull(column="atc_loss_pct", mostly=0.99),
        _pct("atc_loss_pct"),
    ],
    "kelectric_schedule": [
        *PROVENANCE,
        gxe.ExpectColumnValuesToBeUnique(column="feeder_name_norm"),
        gxe.ExpectColumnValuesToNotBeNull(column="grid"),
        gxe.ExpectColumnValuesToBeInSet(column="total_minutes", value_set=[360, 720]),
    ],
    "kelectric_schedule_cycle": [
        gxe.ExpectColumnValuesToBeInSet(column="cycle_no", value_set=[1, 2, 3, 4]),
        gxe.ExpectColumnValuesToMatchRegex(column="start_hhmm", regex=r"^\d{4}$"),
        gxe.ExpectColumnValuesToMatchRegex(column="end_hhmm", regex=r"^\d{4}$"),
        gxe.ExpectColumnValuesToBeBetween(column="minutes", min_value=1, max_value=720),
        gxe.ExpectCompoundColumnsToBeUnique(column_list=["feeder_name_norm", "cycle_no"]),
    ],
    "pbs_urban_population": [
        *PROVENANCE,
        gxe.ExpectColumnValuesToBeInSet(column="level", value_set=URBAN_LEVELS),
        gxe.ExpectColumnValuesToNotBeNull(column="area_key"),
        *_nonneg("pop_total", "pop_male", "pop_female"),
        _pct("literacy_pct_total"),
    ],
    "pbs_urban_housing": [
        *PROVENANCE,
        gxe.ExpectColumnValuesToBeInSet(column="level", value_set=URBAN_LEVELS),
        gxe.ExpectColumnValuesToNotBeNull(column="area_key"),
        *_nonneg("housing_units_total", "structure_pacca", "electricity"),
        _household_size(),
    ],
    "pbs_rural_population": [
        *PROVENANCE,
        gxe.ExpectColumnValuesToBeInSet(column="level", value_set=RURAL_LEVELS),
        gxe.ExpectColumnValuesToBeUnique(column="area_key"),
        *_nonneg("pop_total", "pop_male", "pop_female", "area_acres"),
        _pct("literacy_pct_total"),
    ],
    "pbs_rural_housing": [
        *PROVENANCE,
        gxe.ExpectColumnValuesToBeInSet(column="level", value_set=RURAL_LEVELS),
        gxe.ExpectColumnValuesToBeUnique(column="area_key"),
        *_nonneg("housing_units_total", "structure_pacca", "electricity"),
        _household_size(),
    ],
}


@dataclass
class SuiteResult:
    table: str
    success: bool
    evaluated: int
    failed: list[str]


def validate_table(table: str, df: pd.DataFrame, context=None) -> SuiteResult:
    context = context or _context()
    ds = context.data_sources.add_or_update_pandas(name="parsed")
    asset = ds.add_dataframe_asset(name=table)
    batch_def = asset.add_batch_definition_whole_dataframe(f"{table}_all")
    batch = batch_def.get_batch(batch_parameters={"dataframe": df})
    suite = gx.ExpectationSuite(name=table)
    for exp in SUITES[table]:
        suite.add_expectation(copy.deepcopy(exp))
    result = batch.validate(suite)
    failed = [
        f"{r.expectation_config.type}({r.expectation_config.kwargs.get('column', '')})"
        for r in result.results
        if not r.success
    ]
    return SuiteResult(table, result.success, len(result.results), failed)


def _context():
    context = gx.get_context(mode="ephemeral")
    context.variables.progress_bars = ProgressBarsConfig(globally=False)
    return context


def validate_dir(parsed_dir: Path) -> list[SuiteResult]:
    context = _context()
    out = []
    for table in SUITES:
        path = parsed_dir / f"{table}.parquet"
        if path.exists():
            out.append(validate_table(table, pd.read_parquet(path), context))
    return out
