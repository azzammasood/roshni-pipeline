# Roshni Pipeline

*روشنی (roshni): light.* A data pipeline showing **where and when Pakistan's load-shedding is scheduled**, and **whether it falls unequally**.

> Not affiliated with IESCO, K-Electric, PBS or any government body. All outage data here is **published schedule data**, not measured outages.

## Live site
**https://azzammasood.github.io/roshni-site/**, rebuilt daily from the latest published schedules.

| Page | English | اردو |
|---|---|---|
| Scheduled now (pick a time and an IESCO level) | [/en/](https://azzammasood.github.io/roshni-site/en/) | [/ur/](https://azzammasood.github.io/roshni-site/ur/) |
| Planned shutdowns (IESCO press releases) | [/en/shutdowns/](https://azzammasood.github.io/roshni-site/en/shutdowns/) | [/ur/shutdowns/](https://azzammasood.github.io/roshni-site/ur/shutdowns/) |
| Karachi: schedule hours by IBC | [/en/karachi-equity/](https://azzammasood.github.io/roshni-site/en/karachi-equity/) | [/ur/karachi-equity/](https://azzammasood.github.io/roshni-site/ur/karachi-equity/) |
| About the data | [/en/about/](https://azzammasood.github.io/roshni-site/en/about/) | [/ur/about/](https://azzammasood.github.io/roshni-site/ur/about/) |

Every feeder also has its own page (24-hour schedule, IESCO levels, matched census localities, planned shutdowns), linked from the tables. The export JSON the site is built from is public too: [`data/v1/`](https://azzammasood.github.io/roshni-site/data/v1/meta.json) (`meta`, `feeders`, `dark_profiles`, `planned_shutdowns`, `areas`, `equity`).

## The question
Public data has no real-time outages. Roshni therefore builds:
1. **"Dark now"**: a clock-driven view computed from published schedules and planned-shutdown notices. It is always labelled as schedule data and carries a last-updated stamp.
2. **Fairness analysis** on **K-Electric (Karachi)**, the only source that publishes unequal hours per feeder. The analysis is exploratory and descriptive, with sample sizes shown.

**IESCO (Islamabad/Rawalpindi)** is the live-operations layer: a scenario playbook by interruption level, plus planned shutdowns from press releases. An AI layer only narrates results already computed in SQL.

## Sources
| Source | Use |
|---|---|
| IESCO load-shedding XLSX (6 circles) | Scenario view ("if level N is active") |
| IESCO press releases (English PDFs) | Planned shutdown windows |
| K-Electric feeder list PDF | Feeder category, loss %, IBC area |
| K-Electric load-shed schedule PDF | Exact daily windows per feeder |
| PBS Census 2023, tables 31–34 | Area indicators (literacy, housing) |

## What is and is not measured
- **Measured:** nothing about actual outages. Census indicators come from PBS.
- **Published:** schedules, which are tentative and may be superseded. Planned-shutdown notices.
- **Geography** is area-level: no source publishes feeder coordinates.
- K-Electric shares are computed **among listed (load-shed) feeders only**, because exempt feeders are not published.

## Architecture
Fetch (polite, snapshot on change) → parse (typed rows plus quarantine, Great Expectations) → DuckDB + dbt (tests on models) → entity resolution (reviewed seeds) → live / fairness marts → static JSON export → static Next.js site (English and Urdu) on GitHub Pages.

### Snapshots
`roshni snapshot` discovers source files from the publishers' listing pages, fetches them politely (robots.txt, ≤1 req/s, conditional requests) and stores each distinct version on the orphan branch `data-snapshots`, with a `raw_snapshots.csv` log of every check.

### Scheduler roles
- **GitHub Actions is the production scheduler**: `snapshot.yml` runs daily (05:30 Pakistan time); when it succeeds, `publish.yml` parses, validates, builds, exports, builds the site and pushes it to the public repo [`azzammasood/roshni-site`](https://github.com/azzammasood/roshni-site), which GitHub Pages serves. This repo stays private. If any step fails, the site keeps its last good version.
- **Airflow (local Docker) is the orchestration showcase**: DAGs only call the same `roshni` CLI tasks, with no business logic in DAGs.

### Reference architecture vs deployment
The public deployment runs on a **free static host** fed by free-tier GitHub Actions, using the same dbt models. An AWS + Terraform setup is the **reference deployment**, not the live one. The dbt models stay portable so they also run on Databricks.

## Static export
`roshni export` writes versioned JSON to `data/export/v1/` (feeders, 24-hour dark profiles, planned shutdowns, census areas, equity figures and the latest report), each with `schema_id`, `schema_version`, `last_updated` and a "schedule, not measurement" label, validated against the JSON Schemas in `schemas/v1/`. A static site can compute "dark now" in the browser from the profiles.

## Website
`web/` is a Next.js static export (TypeScript, Tailwind, no map in v1). "Scheduled now" is computed in the browser from the export and is checked row for row against the Python `dark-now` (`scripts/dark_now_oracle.py`). English and Urdu (right-to-left, Nastaliq); every number on the Karachi page is traced to `equity.json` by a CI check, and translations are checked for completeness. The census tables the daily job needs are committed in trimmed form in `census/` (the census files themselves are hand-downloaded and never committed).

## Orchestration showcase (Airflow)
`docker compose -f airflow/docker-compose.yml up --build`, then trigger `roshni_pipeline` at http://localhost:8080. Every task is one `roshni` CLI command; the DAG is unscheduled because GitHub Actions is the production scheduler.

## Development
```bash
uv sync
uv run pytest
uv run roshni --help
```
The hand-downloaded `data-sources/` folder is git-ignored. Tests that need it are marked `needs_data_sources` and skip when it is absent.

Website (Node 24), inside `web/`:
```bash
npm ci
npm run sync-data     # copy data/export/v1 into the site (or sync-data:fixtures)
npm run build         # static site in web/out
```

## License
MIT. See [LICENSE](LICENSE).
