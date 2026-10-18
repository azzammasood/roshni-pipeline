# Case study: Roshni

*Building an honest data product from scattered public documents.* Ahmad Uzzam Masood, 2026.

## The problem

Load shedding is part of daily life in Pakistan. The information people need exists, but it is fragmented:

- **IESCO** (Islamabad and Rawalpindi) publishes one spreadsheet per circle with **six alternative schedules**, one for each interruption level from 2 to 12 hours a day, and never says which level is in force. It also announces maintenance shutdowns in English PDF press releases.
- **K-Electric** (Karachi) publishes a feeder list and a schedule as PDFs, and a newer schedule replaces the old one without notice.
- **NEPRA**, the regulator, publishes yearly performance reports with the load-shedding hours each company *reported*, and says itself that some companies under-report.
- **PBS Census 2023** tables describe the areas those feeders serve.

Nothing joined these sources, nothing kept their history, and nothing said clearly what was a plan, what was a report and what was a measurement.

## Constraints I set

1. **Never invent data.** Unreadable rows are quarantined with a reason, and known anomalies are flagged, never fixed silently.
2. **Schedules are not measurements.** Every page and export says so.
3. **Be a polite client.** Check robots.txt for every host, make at most one request a second, use conditional requests, and run daily. Two government hosts were excluded because their robots.txt disallows crawling, and a social-media page was rejected for the same reason.
4. **Provenance on every row:** `source_file`, `source_sha256` and `fetched_at`.
5. **Free to run.** The language-model step is capped at $0.01 per run, and everything else uses free tiers.

## Design

A batch pipeline with one CLI (`roshni`). Every step is a command, so GitHub Actions (production) and Airflow (a local showcase) orchestrate the same code without holding any business logic.

`snapshot → parse → validate → dbt build → resolve → report → export → static site`

- **Snapshots** are append-only and content-addressed by SHA-256, with a CSV log of every check, in a private repository (they are third-party documents).
- **Parsers** return pydantic models written to Parquet, with a quarantine file next to each table. PDF text comes from one pinned poppler `pdftotext -layout` in Docker, so extraction is identical on every machine; a different build (the xpdf one bundled with Git for Windows) is never used.
- **dbt** builds staging views, intermediate joins and marts on DuckDB daily. The same project ran unchanged on Databricks. Planned shutdowns load incrementally, since press releases never change once published.
- **Export**: versioned JSON validated against JSON Schemas generated from the pydantic models. TypeScript types for the site are generated from the same schemas, and CI fails when they drift.
- **Site**: a static Next.js export in English and Urdu (right to left, Nastaliq). The "who is scheduled dark now" logic runs in the browser and is checked case by case against the Python implementation.

## The hard parts

**What does IESCO's spreadsheet actually say?** It is a playbook, not a timetable: six possible schedules and no statement of which applies. Treating it as "the schedule" would invent load shedding. The site makes the reader choose a level and labels every result "if level N is in force". It also never ranks areas by IESCO hours, because the playbook says nothing about fairness.

**Reported versus planned.** NEPRA's FY 2024-25 report prints **0** hours for IESCO and GEPCO ("reported negligible load shedding"), while IESCO's own schedule plans 2 to 12 hours a day. Roshni shows both side by side, with NEPRA's caveat, and neither replaces the other.

**Matching names across sources.** Press releases print feeder names freehand. Exact matches auto-accept; written, tested rules decide most of the rest; a language model may choose **only among listed candidates**, and its pick is stored with a reason. A backtest replays every past decision so a rule change cannot silently change history.

**Numbers you can trust on a web page.** The Karachi equity page has about 650 numbers. A CI check parses the built HTML and traces every number and date back to `equity.json`, in both languages. The language model writes prose only; numbers are injected and validated.

**Accessibility and Urdu.** Every chart has a table view, and axe runs at 375 px in light and dark themes in both languages. Urdu strings are reviewed against the English, and the build fails on a missing key or stray English words.

## Results

- Runs every morning without intervention; a failure opens an issue and the site keeps its last good version.
- 1,719 feeders with a published schedule, 2,675 planned-shutdown windows, and 130 company-years of NEPRA figures across 13 fiscal years.
- 225 Python tests, 117 dbt tests and 184 web tests; Great Expectations suites on all 15 parsed tables.
- About 3,500 static pages in two languages, published to GitHub Pages, with dbt docs and the lineage graph alongside.

## What I would do next

- **Measured data**, if a source ever allows it: a crowd-reported outage feed would need moderation and a backend, and would be labelled as reports, not measurements.
- **More companies' schedules.** The warehouse and the site already handle any company; each new source needs a parser and owner approval.
- **Scale-out**, as described in the README's "How this scales": Iceberg on object storage, streaming ingestion, and data contracts at the bronze boundary.

Code: [github.com/azzammasood/roshni-pipeline](https://github.com/azzammasood/roshni-pipeline) · Site: [azzammasood.github.io/roshni-site](https://azzammasood.github.io/roshni-site/)
