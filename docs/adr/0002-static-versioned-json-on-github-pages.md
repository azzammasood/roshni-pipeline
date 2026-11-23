# 2. Static, versioned JSON on GitHub Pages instead of an API

- Status: accepted
- Date: 2026-10-11 (export), 2026-10-12 (hosting)

## Context

The data changes at most once a day, when the publish job runs. Readers ask "which feeders are
scheduled dark now?", which depends on the reader's clock, not on new data. The project has no
budget for a server and should keep working if nobody touches it for weeks.

## Options considered

1. **An API (for example FastAPI on a small VM or serverless functions) over the warehouse.**
   Flexible queries, but it needs hosting, uptime, secrets and patching, and every page view
   becomes a request.
2. **A static site that reads static JSON, with "dark now" computed in the browser.** Free
   hosting, no runtime to keep alive, and the whole site can be rebuilt from one export.

## Decision

I chose option 2. `roshni export` writes `data/export/v1/*.json`. Each file is an envelope with
`schema_id`, `schema_version`, `generated_at`, `last_updated`, the label "schedules, not
measurements" and `data`. JSON Schemas in `schemas/v1/` are generated from the pydantic export
models, and every export is validated before it counts. Additive changes bump the minor version
(1.0.0 to 1.8.0 so far); a breaking change would go to a `v2` folder. Dark profiles carry exact
K-Electric windows and IESCO hourly vectors, so the browser computes "dark now" itself.

The Next.js site is a static export. The publish job pushes it, with the JSON, to a separate
public repository, `azzammasood/roshni-site`, served by GitHub Pages and never edited by hand.

## Consequences

- No server, no uptime to watch, no cost; Pages serves the JSON gzipped.
- The dark-now logic exists twice, in Python (`roshni.live.dark_now`) and TypeScript
  (`web/src/lib/darkNow.ts`). An oracle test keeps them equal, and every change has to be made in
  both.
- Data is only as fresh as the last publish. A failed publish leaves the last good site in place
  (see [ADR 7](0007-publish-after-failed-snapshot-and-watchdog.md)).
- Large documents cost page weight. The full maintenance document reached 19,337 rows and 9.4 MB,
  so the browser now loads a slim `maintenance_upcoming` (14,994 rows, 5.6 MB, export 1.8.0).
- Ad-hoc queries are not possible; anything the site shows has to be in the export.

## Evidence

- Export models and build: [`src/roshni/export/models.py`](../../src/roshni/export/models.py),
  [`src/roshni/export/build.py`](../../src/roshni/export/build.py); schemas in
  [`schemas/v1/`](../../schemas/v1/).
- Tests: [`src/roshni/export/test_export.py`](../../src/roshni/export/test_export.py)
  (`test_committed_schemas_match_models`, `test_v1_0_document_still_valid`,
  `test_invalid_documents_rejected`); `npm run check:types` fails on drift between schemas and the
  generated TypeScript types.
- Oracle: [`scripts/dark_now_oracle.py`](../../scripts/dark_now_oracle.py), 144/144 cases at F1
  and 514/514 after maintenance windows were added
  ([PR #21](https://github.com/azzammasood/roshni-pipeline/pull/21)).
- First deploy 2026-10-12: 8,675 files pushed; live at https://azzammasood.github.io/roshni-site/.
- DECISIONS.md entries 2026-10-11 (Phase 7, F1), 2026-10-12 (F4), 2026-11-08 (Resilience).
