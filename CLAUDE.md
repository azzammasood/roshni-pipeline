# Roshni Pipeline — working notes for Claude

Data pipeline: Pakistan load-shedding **schedules** (IESCO, K-Electric) + PBS Census 2023 → DuckDB/dbt → "dark now" view, K-Electric fairness analysis, AI narration, static JSON export, and a static Next.js site in `web/` (plan: `docs/frontend-plan.md`). No logo.

Long facts: `docs/data-audit.md` (oracles, file inventory). Decisions: `docs/DECISIONS.md`. Keep both current.

## Hard rules
- **Never touch CCMS** (`ccms.pitc.com.pk`) or any consumer reference number: not in code, tests or docs.
- **Never fetch `lesco.gov.pk` or `pitc.com.pk`** (robots disallow). Check `robots.txt` for every host.
- Polite client: UA `roshni-pipeline/0.1 (+https://github.com/azzammasood/roshni-pipeline)`, ≤1 req/s, daily (news feeds every 3 h, `news.yml`, owner 2026-10-14), `If-Modified-Since`/`ETag`.
- **Schedules are not measurements.** Never call a scheduled outage an actual outage.
- Fairness stats are descriptive: no causal language, always show n. K-Electric shares are **among listed feeders only**.
- Never invent data. Unparseable rows → quarantine with a reason. Known anomalies are flagged, never silently fixed.
- Display Asia/Karachi (UTC+5, no DST); store UTC.
- Approximate matches always carry a stored, displayed confidence. Exact matches auto-accept; press-release suggestions are also decided automatically by the written, tested rules in `src/roshni/resolve/autoreview.py` (owner, 2026-10-13; note `auto-review: …`), and what the rules leave pending by the OpenRouter chain in `resolve/llmreview.py` (choose among listed candidates only; note `llm-review <date> <model>: …`; the publish job commits these decisions). Anything else is delegated to Claude (rules in DECISIONS.md 2026-10-10, reason `claude-review …` in each seed row's note). A rule change must keep `test_backtest_agrees_with_every_reviewed_decision` green.
- IESCO XLSX = scenario playbook, never inequity analysis. IESCO feeder **code** (6-digit zero-padded) is the join key.
- No gas-connection wealth proxy; no district-level income claims.
- Do not label any feeder or file as "the author's own".
- Only the sources in `docs/data-audit.md` are allowed. Adding a source (including boundaries) needs owner approval.
- Section-7 numbers are regression tests: if one changes, surface it; don't edit the test.

## Repo and git safety
- Remote: `git@github-azzammasood:azzammasood/roshni-pipeline.git`. `gh` is allowed (owner, 2026-10-12) **only after `gh api user --jq .login` prints `azzammasood`**; the keyring also holds another account, so check before every session's first use and stop if it differs. Never force-push without asking.
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
uv run roshni snapshot [--store DIR] [--only SOURCE]   # polite fetch; default store data/snapshots; --only takes patterns (news_*)
uv run roshni parse [--snapshots data/snapshots-branch] [--census-from census]  # -> data/parsed/*.parquet + quarantine/
uv run roshni census-freeze                             # parsed census -> census/ (committed; after census-parser changes only)
uv run roshni validate                                   # Great Expectations on data/parsed
uv run roshni build [--command build|parse|test] [--select X]  # dbt -> data/roshni.duckdb
uv run roshni resolve                                           # candidates -> dbt/seeds/review_*.csv (keeps decisions)
uv run roshni dark-now [--at "2026-10-10 23:30"] [--level 12] [--json]   # scheduled-dark feeders
uv run roshni report [--engine auto|openrouter|template]   # weekly equity report -> data/reports
uv run roshni export [--write-schemas]                     # static JSON -> data/export/v1, validated
docker compose -f airflow/docker-compose.yml up --build    # Airflow showcase on :8080 (manual DAG)
uv run --group databricks python scripts/databricks_load.py     # upload parsed tables (env creds)
uv run --group databricks roshni build --target databricks      # same models on Databricks
docker compose build ; docker compose run --rm app <cmd>   # canonical pdftotext
# web/ (Node 24, npm), run inside web/:
npm ci ; npm run sync-data        # copy data/export/v1 -> public/data/v1 (or sync-data:fixtures)
npm run gen:types                 # after any schemas/v1 change (check:types in CI)
npm run lint ; npm run typecheck ; npm test ; npm run build   # static site -> web/out
npm run check:equity [-- --locale ur]  # after build: every equity-page number traces to equity.json
npm run check:i18n ; npm run i18n:review   # translation checks; regenerate docs/urdu-review.md
uv run python scripts/dark_now_oracle.py   # then npm test: TS dark-now == Python (full export)
```

## Layout
```
src/roshni/{sources,fetch,parsers,resolve,live,fairness,narrate,export}/
src/roshni/cli.py      typer CLI; orchestrators only call these commands
src/roshni/paths.py    REPO_ROOT, DATA_DIR, DATA_SOURCES_DIR (env ROSHNI_ROOT)
src/roshni/fetch/      http.py (PoliteClient), discover.py, store.py, snapshot.py
src/roshni/parsers/    pdftext.py (poppler only), one module per source, run.py
src/roshni/quality/    suites.py (GE suites per parsed table)
src/roshni/export/     models.py (pydantic, source of schemas/v1), build.py; airflow/ = showcase DAG
roshni-snapshots       private repo, branch data-snapshots: raw_snapshots.csv + files/ (written
                       only by snapshot.yml/news.yml via .github/actions/snapshot-store; secret
                       SNAPSHOTS_DEPLOY_KEY). Third-party documents never go in this public repo.
config/                sources.yml, policy.yml
dbt/                   staging views, int_ke_feeder_join, marts + quarantine_* tables, seeds/source_documents.csv
tests/                 cross-cutting tests, fixtures/
scripts/  docs/  .github/workflows/
web/                   Next.js static site: src/app/[lang], src/i18n, src/lib, src/types/v1 (generated), fixtures/v1
census/                committed trimmed census tables + manifest (used by publish.yml)
data/                  generated, git-ignored
data-sources/          hand-downloaded, git-ignored, not managed by code
```

## Conventions
- Python 3.12, uv, ruff (line 100), pytest. pathlib only; no hardcoded separators.
- Tests next to code (`test_*.py`); mark full-file tests `@pytest.mark.needs_data_sources`.
- Parsers return pydantic models → Parquet + quarantine file. Every source-derived table keeps `source_file`, `source_sha256`, `fetched_at`.
- PDF text: `pdftotext -layout` (poppler in Docker) is canonical. Local Git-for-Windows pdftotext is xpdf: never use it.
- Data quality: Great Expectations on parsed Parquet; dbt tests on models; don't duplicate.
- dbt SQL stays portable (must also run on Databricks): avoid DuckDB-only syntax.
- Every schedule row carries `effective_from`; every live output carries source, effective date, `last_updated`.
- Narration: the LLM writes prose only; numbers are injected from queries and validated.
- Schedulers: GitHub Actions = production (`news.yml` every 3 h, news feeds only, trimmed; `snapshot.yml` daily, then `publish.yml`: parse → validate → build → resolve → build → report (Haiku 5.5 on prepaid credits, ≤$0.01/run; free models after credits run out) → export → site → public repo `azzammasood/roshni-site`, never edited by hand; failures open a `pipeline-failure` issue); Airflow = local showcase calling the CLI.
- The daily resolve (`roshni resolve --llm` in publish) decides press-release names by rules, then by LLM; the publish job commits `dbt/seeds/review_*.csv` back to main (bot commits: pull before editing seeds locally). Names stay `pending_review` only when no key/credits/valid reply; an owner or Claude decision always wins and is never overwritten.

## Working agreement
- Work phase by phase; stop at each gate with evidence (test output, row counts).
- Owner is on a limited plan: don't dump whole PDFs or tables; use head/counts; one phase per session.

## Phase status
- Phase 0 (repo, tooling, CI, docs): done 2026-10-06 (CI green, Docker image builds).
- Phase 1 (snapshot job): done 2026-10-06 (run 1: new=73; run 2: unchanged=8 known=65). Snapshots on branch `data-snapshots` (moved to the private repo `roshni-snapshots` 2026-10-18).
- Phase 2 (parsers): done 2026-10-09; 20 golden tests, 10 GE suites pass; audit mismatches explained and approved (data-audit.md §8).
- Phase 3 (warehouse): built 2026-10-09; dbt build PASS=78; warehouse golden tests pass.
- Phase 3b (Databricks smoke run): done 2026-10-10; PASS=78 on Databricks Free Edition, no dialect fixes.
- Phase 4 (entity resolution): done 2026-10-10; dbt PASS=108; review delegated to Claude (rules in DECISIONS.md, notes per row); boundary report in docs/boundary-research.md (no map in v1).
- Phase 5 (live layer): done 2026-10-10; dark-now function + CLI, mart_feeder_dark_hours; dbt PASS=116; midnight-wrap tests pass.
- Phase 6 (analytics + narration): done 2026-10-11; dbt PASS=129; LLM report (gemini-2.5-flash via fallback, $0.0075) validated and traced to queries.
- Phase 7 (export + orchestration): done 2026-10-11; export validates against schemas/v1; Airflow DAG ran all 6 tasks successfully.
- Frontend F0 (scaffold): done 2026-10-11; full build 1,731 static pages, fixture build in CI. F1 (export 1.1.0 exact K-E windows, TS dark-now): done 2026-10-11, oracle 144/144 cases.
- Frontend F2 (pages: home, feeder, shutdowns, about): done 2026-10-12; axe 0 violations light/dark at 375 px.
- Frontend F3 (Karachi equity page): done 2026-10-12; `npm run check:equity` traces all 499 numbers to equity.json (in CI).
- Frontend F4 (daily publish): done 2026-10-12; first publish run green (dbt PASS=129, equity check, 8,675 files), live at https://azzammasood.github.io/roshni-site/.
- Frontend F5 (Urdu, RTL): done 2026-10-12; axe 0 on all Urdu pages; owner approved the translation, /ur/ published.
- Redesign "Grid Gazette" (2026-10-13/14): owner chose direction D; pinned-feeder lead, power-line day strips, tower skyline, theme toggle, opening animation; axe 0 at 375 px light/dark en/ur; equity trace passes.
- National context N1–N4 (2026-10-13/14, owner-approved sources): NEPRA reported load-shedding hours (130 company-years, FY2012-13…FY2024-25), news headlines (14 trimmed feeds, every 3 h), NEPRA order on K-Electric (620 feeders); export 1.3.0; dbt PASS=148.
- Month by month (2026-10-14): IESCO planned shutdowns per month and K-Electric's schedule per month from every stored schedule version; export 1.5.0. Fonts self-hosted (OFL); Urdu review of 131 strings done by Claude (owner-delegated).
- Owner visual review (2026-10-14, PR #13): motion layer (`motion.css`), theme/tab view transitions, intro loader, month names ("Sep 2026"), "How it's built" architecture tab, UX pass; axe 0 at 375 px light/dark en/ur, equity trace passes. Merged and deployed 2026-10-14.
- Portfolio round (2026-10-18): The maker tab and footer credit, freshness badge, dbt docs + lineage at <site>/dbt-docs/, incremental fct_planned_shutdown, README with screenshots and How this scales, docs/case-study.md; snapshots moved to private repo roshni-snapshots before the repo went public.
- Maintenance + zero flag (2026-10-18, owner): new source IESCO monthly maintenance schedules (8 workbooks, 18,737 windows; export 1.6.0 maintenance + notices); reported-0 cells hatched with plan badges. Facebook notices (hand-recorded seed) removed 2026-10-19: no manual inputs, export 1.7.0.
- Dark-now maintenance (2026-10-19): IESCO announced maintenance windows in both dark-now engines (kind `maintenance`, GSO repeats once) + home group/stat en/ur; oracle 514/514; axe 0 at 375 px. PR #21.
- Nil + nav (2026-10-19, owner): reported 0 shown as "nil reported" off the colour scale; pinned home "On this page" bar; maker card trimmed to name, quote, links; axe 0 at 375 px.
- My feeder tab (2026-10-20, owner): search + pin on /my-feeder/, one-feeder analysis; IESCO without a level leads with announced maintenance; news strip freshness line.
- Backend complete. Frontend kickoff (2026-10-11): Next.js static export, English first with Urdu-ready i18n/RTL, no map in v1; hosted from the public repo roshni-site (2026-10-12).
