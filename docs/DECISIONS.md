# Decisions

Newest first. Format: date — decision — why.

## 2026-10-10 (Phase 3b)
- **Databricks smoke run passed** on a Databricks Free Edition workspace (serverless SQL warehouse, catalog `workspace`): `scripts/databricks_load.py` uploaded the 10 parsed tables to `workspace.roshni_raw` via a Unity Catalog volume (row counts identical to local), and `roshni build --target databricks` gave **PASS=78**, same as DuckDB. **No dialect fixes were needed.**
- An older Databricks workspace on the owner's account had exhausted its budget and lost serverless eligibility; a separate Free Edition workspace was used. Free Edition is non-commercial with no SLA: Databricks stays a portability check, not a dependency.
- `dbt-databricks` lives in the optional `databricks` dependency group; run with `uv run --group databricks ...`. Credentials only via `DATABRICKS_HOST`, `DATABRICKS_HTTP_PATH`, `DATABRICKS_TOKEN` env vars; nothing in the repo.

## 2026-10-09 (Phase 3)
- **dbt-duckdb 1.11 / dbt-core 1.12**, project in `dbt/`, profile in `dbt/profiles.yml` (paths from env, set by `roshni build`). Sources point at `data/parsed/*.parquet` via `external_location`, so model SQL never references files (portable to Databricks, where sources are uploaded tables).
- **Portable SQL only:** `||`, `like`, window functions, `cast(... as string|integer|double)`; no DuckDB-only functions in models.
- **Layers:** staging views → `int_ke_feeder_join` → tables `dim_feeder`, `fct_schedule_window`, `fct_planned_shutdown`, `dim_area_indicators`, `mart_ke_feeder_hours`, plus `quarantine_feeder`, `quarantine_schedule_window`, `quarantine_area`.
- **IESCO quarantine rules:** non-numeric code; a `(FESCO)` feeder that reuses an IESCO code; any other duplicate circle + code (both rows). Slots of a feeder-level whose count ≠ N are quarantined (Kohala L10).
- **K-Electric truncated-name rule:** a schedule name ≥ 20 chars that is a unique prefix of a unique unmatched listed name → `truncated_name`, confidence 0.95 (only the NAVY feeder). All other K-Electric joins are exact (1.0).
- **`effective_from` from seed `source_documents.csv` keyed by SHA-256.** A new file version has no seed row → `fct_schedule_window.effective_from` not_null test fails → owner reviews before it flows. IESCO: HTTP Last-Modified 2026-01-14 (file states no date); K-Electric schedule: 2026-08-05.
- **Recurring vs dated:** recurring schedules in `fct_schedule_window` (local minutes of day; K-E wraps flagged); dated press-release windows in `fct_planned_shutdown` (UTC + printed local time). Press-release feeder matching is Phase 4.
- **Census:** urban 33↔34 and rural 31↔32 joined on (province,) hierarchical key; housing joined only where the key is unique; shares computed only for positive denominators; gas excluded.
- **CI runs `dbt parse`** (no data there); `tests/test_warehouse.py` builds into a temp DuckDB locally.

## 2026-10-09 (Phase 2 review)
- **Rural localities: keep the 3 mauzas printed without a hadbast number** (2,581 localities in the five IESCO districts, 2,360 with ≥20 housing units; audit said 2,578 / 2,357). Owner approved.
- **Rural `-` cells stay 0** (census convention), not missing. Indicator minimums are therefore 0 and 27 localities fall under 70 % electricity (audit: 24 with `-` as missing). Owner approved.

## 2026-10-06 (Phase 2)
- **PDF text only from poppler.** Git for Windows ships xpdf `pdftotext` 4.00, whose layout differs; `parsers/pdftext.py` rejects non-poppler binaries and falls back to `docker run roshni:dev pdftotext`. Text is cached by SHA-256 in `data/cache/pdftext/`.
- **Outputs:** `data/parsed/<table>.parquet` + `data/parsed/quarantine/<table>.parquet` (source_file, source_sha256, location, raw, reason). Tables: iesco_feeder, iesco_schedule_slot, iesco_press_release_window, kelectric_feeder_list, kelectric_schedule, kelectric_schedule_cycle, pbs_urban_population, pbs_urban_housing, pbs_rural_population, pbs_rural_housing.
- **Known anomalies are flagged in a `flags` column, not quarantined** (quarantine = could not parse). Phase 3 decides which flags exclude rows from marts.
- **IESCO XLSX** stored long: one row per feeder, one row per feeder × level × one-hour slot.
- **Press releases:** a new date resets circle and time (no carry-over across days). Non-feeder phrases are quarantined; short `NNkV` asset names kept with `transmission_asset`. Times stored as local HH:MM and UTC.
- **K-Electric truncated NAVY name is not fixed in the parser**; the join fix belongs in entity resolution / dbt with a recorded rule.
- **PBS hierarchical keys** (`area_key`) built from document order; tables join on the key. `-` → 0; `#######` → null + `overflow_cells`.
- **Sindh urban PDFs: never guess wrapped rows**; reliable at district and sub-division level only.
- **`fetched_at` is null for hand-downloaded files** unless the same SHA-256 exists in the snapshot log.
- **Great Expectations 1.x chosen over Soda** (installs cleanly on 3.12, maintained, pandas validation of Parquet). Suites are code (`quality/suites.py`), ephemeral context, single-table checks only; golden counts live in pytest, cross-table rules in dbt.
- **Unit tests use synthetic layout text** (monkeypatched `pdf_text`) and generated XLSX; no third-party documents are committed.

## 2026-10-06 (Phase 1)
- **Snapshot store = orphan branch `data-snapshots`**: `raw_snapshots.csv` (one row per check: source, item_key, label, url, fetched_at, http_status, etag, last_modified, sha256, bytes, path, changed, note) plus `files/<source>/<item_key>/<UTC stamp>_<sha12><ext>`. CSV, so DuckDB reads it directly in Phase 3. Locally the default store is `data/snapshots/`.
- **Change detection:** conditional GET (`If-None-Match` / `If-Modified-Since` from the last good record) → 304 = unchanged; on 200 the SHA-256 decides. A new URL for the same item (e.g. a K-Electric republish) is noted in `note`.
- **Press releases fetched once per URL** (immutable notices; the listing has ~65 and grows daily). XLSX files and K-Electric PDFs are re-checked daily because they can be overwritten in place.
- **K-Electric schedule discovered by file name** (all links read "Download"); exactly one match required, otherwise the run fails loudly. `Non-Payers-List.pdf` on the same page is **excluded** (not a confirmed source).
- **Fetcher policy in code:** hard denylist (`lesco.gov.pk`, `pitc.com.pk` incl. CCMS), robots.txt checked per host, ≤1 request/s globally, 5xx retried twice with backoff.
- **Every run commits the log** (unchanged checks included) so the branch records each daily check; files are only added when content changes.
- **HTML parsing with BeautifulSoup**; tests use small synthetic pages, not copies of third-party pages.

## 2026-10-06 (Phase 0)
- **Remote over SSH alias `github-azzammasood`** (`git@github-azzammasood:azzammasood/roshni-pipeline.git`, key `id_ed25519`). The gh CLI is logged into azzamverse and is never used against this repo. The remote existed and was empty, so the first push was a plain push with no force.
- **Repo identity per repo only:** `user.name azzammasood`, `user.email ahmaduzzammasood@gmail.com`. The global config is untouched.
- **Repo visibility: private.** If it ever goes public, add a scheduled-workflow keepalive (GitHub disables crons after about 60 days of inactivity).
- **Owner shell: PowerShell.** All scripts stay cross-platform (Python + pathlib). `.gitattributes` forces LF.
- **Python 3.12** via uv-managed interpreter (`.python-version`); `requires-python >=3.12,<3.13`.
- **Tests live next to code** (`src/roshni/**/test_*.py`); cross-cutting tests and fixtures in `tests/`. Marker `needs_data_sources` is auto-skipped by the root `conftest.py` when `data-sources/` is absent (CI).
- **Pre-commit** runs ruff via `uv run` (one ruff version, pinned by `uv.lock`) and includes a hook that fails if anything under `data-sources/` is staged.
- **Canonical PDF text = poppler `pdftotext -layout` inside the Docker image** (python:3.12-slim + poppler-utils; poppler **25.03.0** at first build). If a Debian base update changes the poppler version and golden counts drift, pin the base image digest. The local Git-for-Windows `pdftotext` is for convenience only.
- **The brief `roshni-claude-code-prompt.md` is git-ignored** (it names personal accounts); its durable content lives in `CLAUDE.md`, this file and `docs/data-audit.md`.
- **License: MIT** (brief default).
- **Data quality split:** Great Expectations on the parsed Parquet layer; dbt tests on models; no duplicated checks. Soda Core is the fallback (decide in Phase 2).
- **Deps added per phase**, not up front: Phase 0 only has typer and pydantic.
