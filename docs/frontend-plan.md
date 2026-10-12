# Frontend plan (v1)

Static Next.js site in `web/`, built from `data/export/v1` (schemas in `schemas/v1/`), deployed to
GitHub Pages by Actions. English first, Urdu-ready (RTL-safe). No map. Decisions: DECISIONS.md
2026-10-11. One phase per session, each ends at a gate with evidence.

## Non-negotiables carried into the UI
- Every time-based view says **"Scheduled"**, never "outage" or "power cut happened". The export
  `label` is shown on every data page; `last_updated` and source `effective_from` are shown in the footer
  and on each feeder.
- Display Asia/Karachi (UTC+5, fixed offset, no DST); data stays UTC. "Now" = browser clock converted
  to UTC+5, never the browser's own zone.
- IESCO = **scenario playbook**: the site never claims which level is active. The user picks a level
  ("If level 8 is in force, this feeder is scheduled dark 01:00–02:00 …"). No IESCO ranking or inequity view.
- K-Electric equity: descriptive only, **n on every statistic**, "among listed feeders only", no causal
  words, no p-values. The weekly narrative is shown as published, with its fact table.
- Approximate matches show their confidence (`match_confidence`, `schedule_match_confidence`);
  unmatched / out-of-scope press-release rows are shown as printed, never guessed.
- No consumer reference numbers, no CCMS links, no gas proxy, no district income claims.

## Stack
- Next.js (App Router, `output: "export"`, `basePath: /roshni-pipeline`, `trailingSlash`), React,
  TypeScript, Tailwind (logical utilities only: `ms-/me-/ps-/pe-/start-/end-`), next-intl with
  locale-prefixed routes (`/en/…`, later `/ur/…`), `dir` set per locale.
- Types generated from `schemas/v1/*.schema.json` (`json-schema-to-typescript`) into
  `web/src/types/v1.ts`; a check fails if they drift from the schemas.
- Charts: small hand-written SVG components (24-hour bars, ranked bars). No chart library.
- Tests: Vitest for `lib/` (dark-now, time zone, formatting); a build smoke test in CI.
- Data: `web/scripts/sync-data.mjs` copies `../data/export/v1` → `web/public/data/v1` (git-ignored)
  and validates each envelope's `schema_id`/`schema_version`. CI builds from trimmed fixtures in
  `web/fixtures/v1/` (public names only, a few rows each).

## Pages
| Route | Content |
|---|---|
| `/` | "Scheduled dark now": search feeders (name, code, grid, IBC, locality); K-Electric list for the current Karachi time; IESCO needs a chosen level. Planned shutdowns active now. |
| `/feeder/[slug]` | 24-hour profile (K-E daily; IESCO one row per level), localities with confidence, related planned shutdowns, source + effective date. ~1,725 static pages. |
| `/shutdowns` | Press-release planned shutdowns: upcoming and recent, by circle, match state shown. |
| `/karachi-equity` | IBC table (n), sub-division table with census indicators, correlations (rho, n), anomaly rules, weekly narrative + fact table, scope note. |
| `/about` | Method, sources (`meta.sources`), attribution, disclaimer, glossary (feeder, IBC, level, scheduled vs measured). |

## Phases
- **F0 scaffold** (done 2026-10-11): `web/` app, i18n skeleton, types from schemas, data sync + fixtures,
  layout with label/footer, placeholder routes, lint/typecheck/test/build in CI. Gate: `npm run build`
  produces `web/out` with all routes; CI green.
- **F1 data fidelity + dark-now lib** (done 2026-10-11): additive export v1.1.0 adds exact
  K-Electric windows (`daily_windows`; IESCO slots are whole hours, so hourly is exact), because hourly minute counts cannot answer
  "is 22:40 dark?" when hour 22 has 25 scheduled minutes. Port Phase 5 window semantics ([start, end),
  midnight wrap, not before `effective_from`) to TS with tests mirroring the Python ones.
  Gate: TS results equal `roshni dark-now --json` for a set of times.
- **F2 pages** (done 2026-10-12): home, feeder, shutdowns, about. Gate: screenshots desktop + mobile, a11y check, sizes.
  A11y check: build, copy `web/node_modules/axe-core/axe.min.js` into `web/out/` (never committed), serve `out/`, run `axe.run()` on each page in light and dark.
- **F3 equity page** (done 2026-10-12). Gate: every number on the page traced to `equity.json` (`npm run check:equity`, in CI).
- **F4 deploy** (done 2026-10-12, live at https://azzammasood.github.io/roshni-site/): `publish.yml` after each snapshot run → public repo `roshni-site` (Pages). Owner decisions below were made: separate public site repo; census option (a).
- **F5 Urdu** (done 2026-10-12): translations, RTL, checks; owner approved, `/ur/` published.

## Owner decisions needed before F4
1. **Repo visibility / plan** for GitHub Pages (public repo or paid plan). Not changed by Claude.
2. **Census data in CI.** Census PDFs are hand-downloaded (`data-sources/`, never committed), so a
   GitHub-hosted job cannot rebuild `areas.json` or the census half of `equity.json`. Options:
   (a) commit the small census-derived parsed tables (aggregate public statistics, trimmed to the
   used columns) so CI can build everything; (b) CI rebuilds only schedule documents and reuses the
   last owner-built `areas.json`/`equity.json` from a `data-export` branch; (c) owner publishes the
   whole export from their machine. Recommendation: (a), since census 2023 is static and the tables
   are public aggregates, but it is a "commit third-party data" call that needs approval.
