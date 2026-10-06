# Decisions

Newest first. Format: date — decision — why.

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
