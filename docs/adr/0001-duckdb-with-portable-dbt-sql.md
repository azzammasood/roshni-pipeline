# 1. DuckDB locally, with dbt SQL kept portable to Databricks

- Status: accepted
- Date: 2026-10-09 (Databricks check 2026-10-10)

## Context

Roshni joins feeder lists, schedule windows, press releases and census areas. The data fits in
one file, the daily build runs on a free GitHub Actions runner, and the project has no budget for a
warehouse that is always on. I still wanted the models to show that they would run on a real
cloud warehouse if the data or the team grew.

## Options considered

1. **A cloud warehouse (Databricks, BigQuery, Snowflake) as the main target.** Realistic for a
   company, but it needs credentials in CI, costs money on every run, and the free tiers have no
   SLA.
2. **Plain Python (pandas) transforms.** No warehouse at all, but no lineage, no tests per model
   and no SQL a reviewer can read.
3. **dbt on DuckDB, with SQL that must also run on Databricks.** One local file, no server, and
   the same models can be pointed at a cloud warehouse.

## Decision

I chose option 3. dbt-duckdb builds `data/roshni.duckdb` locally and in CI. Sources point at
`data/parsed/*.parquet` through `external_location`, so model SQL never names a file. Models use
only portable SQL (`||`, `like`, window functions, `cast(... as string|integer|double)`); no
DuckDB-only functions. Where a date spine would have needed DuckDB syntax, months are expanded in
Python at export time instead. Spearman's rho is computed in SQL (average ranks, then `corr()`).
`fct_planned_shutdown` is incremental with `delete+insert` on DuckDB and `merge` on Databricks.

## Consequences

- The production build is free and has no external dependency. CI builds a fresh DuckDB file, so
  production runs are full builds; the incremental path only pays off on a persistent warehouse.
- The portability rule costs some convenience: no DuckDB macros, no date spines, some logic moved
  into Python.
- Databricks is a portability check, not a dependency. Free Edition is non-commercial with no
  SLA, and an older workspace on the owner's account had already exhausted its budget.
- `dbt-databricks` lives in an optional dependency group, and credentials come only from
  `DATABRICKS_HOST`, `DATABRICKS_HTTP_PATH` and `DATABRICKS_TOKEN`.

## Evidence

- Smoke run 2026-10-10: the 10 parsed tables uploaded to `workspace.roshni_raw` with identical row
  counts, and `roshni build --target databricks` gave PASS=78, the same as DuckDB, with no
  dialect fixes.
- dbt project and profile: [`dbt/`](../../dbt/), [`dbt/profiles.yml`](../../dbt/profiles.yml);
  upload script [`scripts/databricks_load.py`](../../scripts/databricks_load.py).
- Incremental model: 1,930 unique rows on a full and on an incremental run, dbt PASS=157
  (DECISIONS.md 2026-10-18).
- DECISIONS.md entries 2026-10-09 (Phase 3), 2026-10-10 (Phase 3b), 2026-10-14 (Month by month).
