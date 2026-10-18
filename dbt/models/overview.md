{% docs __overview__ %}
# Roshni warehouse

Pakistan's published load-shedding **schedules** (IESCO, K-Electric), IESCO's planned-shutdown
press releases, NEPRA's reported load-shedding hours, the PBS Census 2023 and news headlines,
modelled for the site at [azzammasood.github.io/roshni-site](https://azzammasood.github.io/roshni-site/).

**Schedules are not measurements.** Every table here describes what was published or reported,
never what actually happened on a feeder.

## Layers
- **Sources (`parsed`)**: Parquet written by the Python parsers. Every row keeps `source_file`,
  `source_sha256` and `fetched_at`. Rows a parser could not read are quarantined with a reason
  and never reach these tables.
- **Staging (`stg_*`, views)**: types, names and keys only.
- **Intermediate (`int_*`)**: joins that need care, such as K-Electric's feeder list to its
  schedule.
- **Marts (`dim_*`, `fct_*`, `mart_*`, `rpt_*`, tables)**: what the export and the site read.
  `quarantine_*` tables keep rows that fail a join, with a reason.

## Things worth knowing
- `fct_planned_shutdown` is **incremental**. Press releases never change once published, so a
  persistent warehouse only loads new release files (DuckDB `delete+insert`, Databricks `merge`).
- The same models build on **DuckDB** (daily, in CI) and **Databricks** (smoke run). SQL stays
  portable.
- K-Electric shares are **among listed feeders only**, and the fairness statistics are
  descriptive. Sample sizes are always shown.

Open the lineage graph with the button at the bottom right.

Code: [github.com/azzammasood/roshni-pipeline](https://github.com/azzammasood/roshni-pipeline)
{% enddocs %}
