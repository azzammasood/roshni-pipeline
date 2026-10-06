# Roshni Pipeline

*روشنی (roshni): light.* A data pipeline showing **where and when Pakistan's load-shedding is scheduled**, and **whether it falls unequally**.

> Not affiliated with IESCO, K-Electric, PBS or any government body. All outage data here is **published schedule data**, not measured outages.

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
Fetch (polite, snapshot on change) → parse (typed rows plus quarantine, Great Expectations) → DuckDB + dbt (tests on models) → entity resolution (human-reviewed seeds) → live / fairness marts → static JSON export.

### Snapshots
`roshni snapshot` discovers source files from the publishers' listing pages, fetches them politely (robots.txt, ≤1 req/s, conditional requests) and stores each distinct version on the orphan branch `data-snapshots`, with a `raw_snapshots.csv` log of every check.

### Scheduler roles
- **GitHub Actions is the production scheduler**: daily snapshot and refresh on the free tier.
- **Airflow (local Docker) is the orchestration showcase**: DAGs only call the same `roshni` CLI tasks, with no business logic in DAGs.

### Reference architecture vs deployment
The public deployment runs on a **free static host** fed by free-tier GitHub Actions, using the same dbt models. An AWS + Terraform setup is the **reference deployment**, not the live one. The dbt models stay portable so they also run on Databricks.

## Development
```bash
uv sync
uv run pytest
uv run roshni --help
```
The hand-downloaded `data-sources/` folder is git-ignored. Tests that need it are marked `needs_data_sources` and skip when it is absent.

## License
MIT. See [LICENSE](LICENSE).
