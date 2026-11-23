# 4. Great Expectations on parsed Parquet, dbt tests on models, no duplication

- Status: accepted
- Date: 2026-10-06

## Context

Bad data can enter at two points: when a parser turns a PDF or workbook into rows, and when dbt
joins those rows into marts. Checks at both points are useful, but the same rule written twice
drifts, and a reviewer cannot tell which copy is authoritative.

## Options considered

1. **dbt tests only.** One tool, but parser output would only be checked after it is loaded, and
   a broken parse would surface as a confusing model failure.
2. **Great Expectations everywhere, including on the warehouse.** One tool, but it duplicates
   what dbt's schema tests already do well next to the SQL.
3. **Soda Core** on the parsed layer, as the fallback named in Phase 0.
4. **Great Expectations on the parsed Parquet layer, dbt tests on models, and each rule in one
   place.**

## Decision

I chose option 4, with Great Expectations 1.x over Soda (it installed cleanly on Python 3.12, is
maintained and validates Parquet through pandas). The split:

- **Great Expectations** (`roshni validate`): single-table checks on `data/parsed/*.parquet`, such
  as value ranges, accepted values and not-null on parsed columns. Suites are code in
  `src/roshni/quality/suites.py` with an ephemeral context.
- **dbt tests**: keys, relationships and cross-table rules on staging views and marts.
- **pytest golden tests**: exact row counts and known values from audited files.

Parsers never drop a row silently: rows they cannot read go to a quarantine Parquet file with a
reason, and known anomalies are kept and flagged in a `flags` column.

## Consequences

- When a check fails, its location tells me the layer: a GE failure is a parser or source
  problem, a dbt failure is a modelling or join problem.
- Two tools to learn and keep current instead of one.
- The ranges must stay in step across layers by hand. On 2026-11-08 the K-Electric bounds were
  widened to physical limits in both places (GE `total_minutes` 0–1440, dbt
  `stg_kelectric_schedule.total_minutes` 1–1440), because a schedule with other daily totals had
  been quarantined and would have emptied Karachi without an error.

## Evidence

- Suites: [`src/roshni/quality/suites.py`](../../src/roshni/quality/suites.py),
  [`src/roshni/quality/test_suites.py`](../../src/roshni/quality/test_suites.py).
- dbt tests: the `_*.yml` files in [`dbt/models/`](../../dbt/models/).
- Golden tests: [`tests/test_golden.py`](../../tests/test_golden.py).
- Phase 2 gate: 20 golden tests and 10 GE suites pass; latest gate 2026-11-08: GE validate passes,
  dbt PASS=172 ([PR #32](https://github.com/azzammasood/roshni-pipeline/pull/32)).
- DECISIONS.md entries 2026-10-06 (Phase 0, Phase 2), 2026-11-08 (Resilience).
