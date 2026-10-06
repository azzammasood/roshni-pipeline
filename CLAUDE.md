# Roshni Pipeline — working notes for Claude

Backend data pipeline: Pakistan load-shedding **schedules** (IESCO, K-Electric) + PBS Census 2023 → DuckDB/dbt → "dark now" view, K-Electric fairness analysis, AI narration, static JSON export. **Backend only**: no frontend, no logo.

Long facts: `docs/data-audit.md` (oracles, file inventory). Decisions: `docs/DECISIONS.md`. Keep both current.

## Hard rules
- **Never touch CCMS** (`ccms.pitc.com.pk`) or any consumer reference number: not in code, tests or docs.
- **Never fetch `lesco.gov.pk` or `pitc.com.pk`** (robots disallow). Check `robots.txt` for every host.
- Polite client: UA `roshni-pipeline/0.1 (+https://github.com/azzammasood/roshni-pipeline)`, ≤1 req/s, daily, `If-Modified-Since`/`ETag`.
- **Schedules are not measurements.** Never call a scheduled outage an actual outage.
- Fairness stats are descriptive: no causal language, always show n. K-Electric shares are **among listed feeders only**.
- Never invent data. Unparseable rows → quarantine with a reason. Known anomalies are flagged, never silently fixed.
- Display Asia/Karachi (UTC+5, no DST); store UTC.
- Approximate matches always carry a stored, displayed confidence. Only exact matches auto-accept.
- IESCO XLSX = scenario playbook, never inequity analysis. IESCO feeder **code** (6-digit zero-padded) is the join key.
- No gas-connection wealth proxy; no district-level income claims.
- Do not label any feeder or file as "the author's own".
- Only the sources in `docs/data-audit.md` are allowed. Adding a source (including boundaries) needs owner approval.
- Section-7 numbers are regression tests: if one changes, surface it; don't edit the test.

## Repo and git safety
- Remote: `git@github-azzammasood:azzammasood/roshni-pipeline.git`. **Never use `gh`** (it is logged into the wrong account). Never force-push without asking.
- Commit identity is set per repo (azzammasood). Don't touch the global git config.
- `data-sources/` is git-ignored and guarded by a pre-commit hook. **Never read images/screenshots there**, nor files not in the inventory. Never commit full third-party documents without asking; CI uses trimmed fixtures in `tests/fixtures/`.
- Ask before installing system packages, Docker changes, or anything destructive.
- Small conventional commits (`feat:`, `fix:`, `build:`, `ci:`, `docs:`, `test:`, `chore:`).

## Commands (PowerShell or bash)
```
uv sync                          # install
uv run pytest                    # tests (needs_data_sources skip if folder absent)
uv run ruff check . ; uv run ruff format .
uv run pre-commit run --all-files
uv run roshni --help
uv run python scripts/inventory.py   # data-sources sizes + SHA-256
docker compose build ; docker compose run --rm app <cmd>   # canonical pdftotext
```

## Layout
```
src/roshni/{sources,fetch,parsers,resolve,live,fairness,narrate,export}/
src/roshni/cli.py      typer CLI; orchestrators only call these commands
src/roshni/paths.py    REPO_ROOT, DATA_DIR, DATA_SOURCES_DIR (env ROSHNI_ROOT)
config/                sources.yml, policy.yml
dbt/                   models/staging, models/marts, seeds (Phase 3)
tests/                 cross-cutting tests, fixtures/
scripts/  docs/  .github/workflows/
data/                  generated, git-ignored
data-sources/          hand-downloaded, git-ignored, not managed by code
```

## Conventions
- Python 3.12, uv, ruff (line 100), pytest. pathlib only; no hardcoded separators.
- Tests next to code (`test_*.py`); mark full-file tests `@pytest.mark.needs_data_sources`.
- Parsers return pydantic models → Parquet + quarantine file. Every source-derived table keeps `source_file`, `source_sha256`, `fetched_at`.
- PDF text: `pdftotext -layout` (poppler in Docker) is canonical.
- Data quality: Great Expectations on parsed Parquet; dbt tests on models; don't duplicate.
- dbt SQL stays portable (must also run on Databricks): avoid DuckDB-only syntax.
- Every schedule row carries `effective_from`; every live output carries source, effective date, `last_updated`.
- Narration: the LLM writes prose only; numbers are injected from queries and validated.
- Schedulers: GitHub Actions = production; Airflow = local showcase calling the CLI.

## Working agreement
- Work phase by phase; stop at each gate with evidence (test output, row counts).
- Owner is on a limited plan: don't dump whole PDFs or tables; use head/counts; one phase per session.

## Phase status
- Phase 0 (repo, tooling, CI, docs): done 2026-10-06 (CI green, Docker image builds).
- Next: Phase 1, snapshot job (`config/sources.yml`, polite fetcher, `raw_snapshots`, daily cron, orphan branch `data-snapshots`).
