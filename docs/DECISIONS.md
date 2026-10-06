# Decisions

Newest first. Format: date — decision — why.

## 2026-10-06 (Phase 0)
- **Remote over SSH alias `github-azzammasood`** (`git@github-azzammasood:azzammasood/roshni-pipeline.git`, key `id_ed25519`). The gh CLI is logged into azzamverse and is never used against this repo. The remote existed and was empty, so the first push was a plain push with no force.
- **Repo identity per repo only:** `user.name azzammasood`, `user.email ahmaduzzammasood@gmail.com`. The global config is untouched.
- **Repo visibility: private.** If it ever goes public, add a scheduled-workflow keepalive (GitHub disables crons after about 60 days of inactivity).
- **Owner shell: PowerShell.** All scripts stay cross-platform (Python + pathlib). `.gitattributes` forces LF.
- **Python 3.12** via uv-managed interpreter (`.python-version`); `requires-python >=3.12,<3.13`.
- **Tests live next to code** (`src/roshni/**/test_*.py`); cross-cutting tests and fixtures in `tests/`. Marker `needs_data_sources` is auto-skipped by the root `conftest.py` when `data-sources/` is absent (CI).
- **Pre-commit** runs ruff via `uv run` (one ruff version, pinned by `uv.lock`) and includes a hook that fails if anything under `data-sources/` is staged.
- **Canonical PDF text = poppler `pdftotext -layout` inside the Docker image** (python:3.12-slim + poppler-utils). The local Git-for-Windows `pdftotext` is for convenience only.
- **The brief `roshni-claude-code-prompt.md` is git-ignored** (it names personal accounts); its durable content lives in `CLAUDE.md`, this file and `docs/data-audit.md`.
- **License: MIT** (brief default).
- **Data quality split:** Great Expectations on the parsed Parquet layer; dbt tests on models; no duplicated checks. Soda Core is the fallback (decide in Phase 2).
- **Deps added per phase**, not up front: Phase 0 only has typer and pydantic.
