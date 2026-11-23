# 3. Raw snapshots in a private git repository, not object storage

- Status: accepted
- Date: 2026-10-06 (snapshot branch), 2026-10-18 (moved to a private repository)

## Context

Every source (IESCO workbooks and press releases, K-Electric PDFs, NEPRA reports, news feeds) can
change or disappear without notice. The pipeline must keep every version it has seen, record each
daily check, and be able to rebuild from what it stored. The source files are third-party
documents: I may read and parse them, but republishing whole copies is a different matter. The
pipeline repository was going to become public as a portfolio piece.

## Options considered

1. **Object storage (S3, GCS, R2).** The usual choice at scale, but it needs a cloud account,
   credentials in CI and a bill, and its history is not reviewable the way a commit log is.
2. **An orphan branch `data-snapshots` in the pipeline repository.** Free and versioned, but it
   would publish every third-party file once the repository went public.
3. **The same branch in a separate private repository, `azzammasood/roshni-snapshots`.** Free,
   versioned, and private.

## Decision

I started with option 2 on 2026-10-06 and moved to option 3 on 2026-10-18, before the pipeline
repository went public. The store holds `raw_snapshots.csv` (one row per check: URL, HTTP status,
ETag, Last-Modified, SHA-256, size, path, changed flag) and
`files/<source>/<item_key>/<UTC stamp>_<sha12><ext>`. A file is added only when its content
changes; the log is committed on every run. The workflows clone the store over SSH through the
composite action `.github/actions/snapshot-store` with the secret `SNAPSHOTS_DEPLOY_KEY`.

Third-party documents never go in the public repository. CI uses small trimmed or synthetic
fixtures in `tests/fixtures/`, the census enters CI only as trimmed Parquet tables in `census/`,
and a pre-commit hook blocks anything under `data-sources/`. News feeds are stored trimmed to
headline, link and time; article text is never stored.

## Consequences

- No cloud account or bill. Git gives history, diffs of the log, and a full copy on every clone.
- Git is a poor store for large binaries: the repository grows with every changed file and has no
  lifecycle rules. At this size (a few sources, files added only when they change) that is acceptable; at scale I would
  move the files to object storage and keep the CSV log.
- One more secret to manage, and writes are serialised: `snapshot.yml` and `news.yml` share one
  concurrency group so they never push at once.
- Moving the branch meant a full-history copy and a secrets scan of the public repository before
  it went public; main's history never contained a PDF or XLSX.

## Evidence

- Store code: [`src/roshni/fetch/store.py`](../../src/roshni/fetch/store.py),
  [`src/roshni/fetch/snapshot.py`](../../src/roshni/fetch/snapshot.py); action
  [`.github/actions/snapshot-store/action.yml`](../../.github/actions/snapshot-store/action.yml).
- First runs: run 1 new=73; run 2 unchanged=8 known=65 (Phase 1).
- Move to the private repository: [PR #17](https://github.com/azzammasood/roshni-pipeline/pull/17).
- Rehearsal with `data-sources/` hidden: parse from the store plus `census/` reproduced the normal
  parse table for table (DECISIONS.md 2026-10-12, F4).
- DECISIONS.md entries 2026-10-06 (Phase 0, Phase 1), 2026-10-14 (N2, N3), 2026-10-18 (Portfolio
  round).
