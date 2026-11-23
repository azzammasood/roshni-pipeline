# 7. Publish runs after a failed snapshot, and a watchdog checks the live site

- Status: accepted
- Date: 2026-11-08

## Context

`publish.yml` runs after each `snapshot.yml` run. At first it ran only after a successful one,
so a fetch error in any single source skipped the publish and froze the whole site, even though
every other source was fine. Separately, the only alert was a failure issue per workflow. During
the 17-day outage (see [ADR 6](0006-automate-review-gates.md)) that issue existed but nobody
noticed that the live site had stopped moving. Two more risks were silent by nature: GitHub
disables scheduled workflows in a public repository after 60 days without repository activity,
and a disabled schedule produces no failure at all.

## Options considered

1. **Publish only after a fully successful snapshot.** Simple, but one broken source stops
   everything.
2. **Publish unless the snapshot was cancelled.** The store keeps every last good file, so a
   failed fetch only means that source is a day older.
3. **For staleness: rely on failure issues**, or add a step to an existing workflow, or run a
   **separate watchdog** that checks the live site itself.
4. **For the 60-day rule: empty commits to main**, or re-enable the workflows through the API
   (the "API mode" of the widely used keepalive-workflow action).

## Decision

I chose options 2, the separate watchdog and API re-enabling.

- `publish.yml` runs unless the snapshot was cancelled (`conclusion != 'cancelled'`). The
  snapshot's failure issue still reports the fetch error.
- `watchdog.yml`, job `freshness`, every 3 h: reads the live `data/v1/meta.json` (a query string
  skips the 10-minute Pages cache). If `last_updated` is more than 36 h old, or the file cannot be
  read after 3 retries, it opens one "Live site is out of date" issue (label `site-stale`) that
  @-mentions the owner, comments at most once a day while stale, and closes the issue when fresh.
  It is its own workflow so a failing news fetch cannot hide it.
- `watchdog.yml`, job `keep-enabled`, Mondays: calls the enable endpoint for the snapshot, news,
  publish and watchdog workflows with the job's own token.

## Consequences

- One broken source no longer blocks the others; the site can show a mix of fresh and day-old
  sources, each with its own fetch date.
- The watchdog checks the outcome readers see rather than any one job, so it also catches causes
  I have not thought of, including a disabled schedule, within 36 h.
- No empty commits to main.
- Whether re-enabling resets GitHub's 60-day timer cannot be proven short of waiting 60 days; the
  freshness check is the backstop.
- The watchdog job stays green when it opens an issue; the issue, not a red run, is the signal.

## Evidence

- Workflows: [`.github/workflows/publish.yml`](../../.github/workflows/publish.yml),
  [`.github/workflows/watchdog.yml`](../../.github/workflows/watchdog.yml); script
  [`.github/scripts/stale-site.sh`](../../.github/scripts/stale-site.sh).
- [PR #32](https://github.com/azzammasood/roshni-pipeline/pull/32) (publish after a failed
  snapshot; pytest 257 passed, dbt PASS=172) and
  [PR #33](https://github.com/azzammasood/roshni-pipeline/pull/33) (watchdog).
- DECISIONS.md entries 2026-10-12 (Follow-ups after F5: failure issues), 2026-11-08 (Resilience,
  Watchdog).
