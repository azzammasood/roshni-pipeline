# 6. Automate the review gates after the site went 17 days stale

- Status: accepted (supersedes the manual gates of 2026-10-09)
- Date: 2026-11-08

## Context

Two gates were built to stop the pipeline for a person:

- **Effective dates.** Every schedule version needs an `effective_from`, taken from the seed
  `source_documents.csv` keyed by SHA-256. A new file had no row, so the dbt test
  `not_null_fct_schedule_window_effective_from` failed and the build stopped for review.
- **Listing rows.** Snapshot discovery mapped each row of IESCO's listing to a configured circle
  and failed on any label it did not know.

From 2026-10-23 publish failed every day: K-Electric published a new schedule with no seed row,
and the not-null test failed on 2,500 rows. From 2026-11-06 the snapshot failed too: IESCO added
a ninth listing row, "PD GSC". The site kept its 2026-10-22 build and read "last updated 17 days
ago". The only signal was the failure issues (#25, #28).

## Options considered

1. **Keep the gates and alert harder.** The gates were correct but depended on someone acting;
   louder alerts do not remove that dependency.
2. **Drop the checks.** The site stays fresh, but undated rows and unknown files flow in unseen.
3. **Decide automatically by a written basis, record each decision, and report it without
   stopping** (owner: "automate both").

## Decision

I chose option 3.

- **Dates:** after parse, `roshni effective-dates` adds a seed row for every stored schedule or
  feeder-list version that has none. The date is the one the file states (K-Electric: "applicable
  from 23rd October, 2026" on the first page), otherwise the HTTP Last-Modified date in
  Asia/Karachi, the same basis as the hand-made rows. Each row says `automatic: …` in
  `effective_basis`, and existing rows are never changed. The not-null test stays and now fails
  only if dating itself fails.
- **Listing rows:** an unknown row is fetched under a key derived from its label ("PD GSC" →
  `pd_gsc`); a configured row that disappears is skipped. Only a page with no XLSX rows at all, a
  changed layout, is still an error.
- **Visibility:** what the pipeline decides on its own goes to `data/notices/*.md` and one open
  "Pipeline notices" issue (label `pipeline-notice`). Failure issues are kept for the unexpected.

## Consequences

- A new schedule reaches the site the next morning without a person.
- A wrong stated date or a misleading Last-Modified header would now flow through. It is visible
  in the notices issue and in `effective_basis`, and a person can correct the seed row afterwards.
- A new listing row is fetched before it is configured; it gets display names only once someone
  adds it to the config (PD GSC was added with en/ur names, and its layout needed parser changes).

## Evidence

- Code: [`src/roshni/parsers/effective.py`](../../src/roshni/parsers/effective.py),
  [`src/roshni/fetch/discover.py`](../../src/roshni/fetch/discover.py),
  [`.github/scripts/notice-issue.sh`](../../.github/scripts/notice-issue.sh).
- Tests: [`src/roshni/parsers/test_effective.py`](../../src/roshni/parsers/test_effective.py),
  [`src/roshni/fetch/test_discover.py`](../../src/roshni/fetch/test_discover.py)
  (`test_iesco_xlsx_new_label_is_fetched_with_a_warning`,
  `test_iesco_xlsx_missing_circle_is_skipped_with_a_warning`,
  `test_iesco_xlsx_page_without_rows_fails`).
- Gate: pytest 256 passed; a local run on the real store gave dbt PASS=172 with the new
  K-Electric version dated 2026-10-23 (625 feeders).
  [PR #30](https://github.com/azzammasood/roshni-pipeline/pull/30).
- DECISIONS.md entries 2026-10-09 (Phase 3), 2026-11-08 (Review gates automated).
