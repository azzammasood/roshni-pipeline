# Architecture decision records

Short records of the decisions that shape Roshni's design, each with the options I did not take
and what the choice costs. They are distilled from the full, dated log in
[`docs/DECISIONS.md`](../DECISIONS.md), which stays the source for detail and later changes.

Each record has the same sections: Context, Options considered, Decision, Consequences, Evidence.
Numbers in them come from DECISIONS.md or the code.

| # | Decision | Date |
|---|----------|------|
| [0001](0001-duckdb-with-portable-dbt-sql.md) | DuckDB locally, with dbt SQL kept portable to Databricks | 2026-10-09 |
| [0002](0002-static-versioned-json-on-github-pages.md) | Static, versioned JSON on GitHub Pages instead of an API | 2026-10-11 |
| [0003](0003-raw-snapshots-in-a-private-git-repo.md) | Raw snapshots in a private git repository, not object storage | 2026-10-18 |
| [0004](0004-great-expectations-on-parquet-dbt-tests-on-models.md) | Great Expectations on parsed Parquet, dbt tests on models, no duplication | 2026-10-06 |
| [0005](0005-entity-resolution-rules-then-constrained-llm.md) | Entity resolution: written rules first, then an LLM limited to listed candidates | 2026-10-13 |
| [0006](0006-automate-review-gates.md) | Automate the review gates after the site went 17 days stale | 2026-11-08 |
| [0007](0007-publish-after-failed-snapshot-and-watchdog.md) | Publish after a failed snapshot, and a watchdog on the live site | 2026-11-08 |

New records take the next number. A record is not rewritten when a decision changes; a new record
supersedes it and says so in its Status line.
