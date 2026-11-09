#!/usr/bin/env bash
# Freshness watchdog: read the live site's meta.json and keep one "site-stale" issue in step with
# it. Stale (last_updated older than MAX_AGE_HOURS, or meta.json unreadable): open the issue, or
# comment on it once a day, @-mentioning NOTIFY so GitHub sends a notification. Fresh: close it.
# Needs GH_TOKEN with issues: write. DRY_RUN=1 prints the issue commands instead of running them.
# Usage: stale-site.sh
set -euo pipefail
url=${META_URL:-https://azzammasood.github.io/roshni-site/data/v1/meta.json}
max_h=${MAX_AGE_HOURS:-36}
notify=${NOTIFY:-azzammasood}
label=site-stale
title="Live site is out of date"
repo_url="${GITHUB_SERVER_URL:-https://github.com}/${GITHUB_REPOSITORY}"
run_url="${repo_url}/actions/runs/${GITHUB_RUN_ID:-local}"

act() {
  if [ -n "${DRY_RUN:-}" ]; then
    printf 'DRY_RUN:'
    printf ' %q' "$@"
    echo
  else
    "$@"
  fi
}

now=$(date -u +%s)
problem=""
# The query string skips the Pages CDN cache (max-age 600) so a just-published build counts.
if meta=$(curl -fsS --retry 3 --retry-delay 20 --max-time 30 "${url}?watchdog=${now}"); then
  last=$(jq -r '.last_updated // empty' <<<"$meta" 2>/dev/null || true)
  if [ -z "$last" ] || ! ts=$(date -u -d "$last" +%s 2>/dev/null); then
    problem="meta.json has no readable \`last_updated\` (got \`${last:-nothing}\`)."
  elif [ $((now - ts)) -gt $((max_h * 3600)) ]; then
    problem="Last updated ${last}, $(((now - ts) / 3600)) hours ago (limit ${max_h} h)."
  fi
else
  problem="Could not read ${url} (after 3 retries)."
fi
echo "checked ${url}: ${problem:-fresh, last updated ${last}}"

act gh label create "$label" --color D93F0B \
  --description "The live site has not updated for too long" >/dev/null 2>&1 || true

# REST list, not `gh issue list` (its index lags just after creation; see failure-issue.sh).
mapfile -t open < <(
  gh api "repos/${GITHUB_REPOSITORY}/issues?labels=${label}&state=open&per_page=100" \
    --jq ".[] | select(.title == \"${title}\") | \"\(.number) \(.updated_at)\""
)

if [ -n "$problem" ]; then
  if [ "${#open[@]}" -eq 0 ]; then
    act gh issue create --label "$label" --title "$title" --body "$(cat <<BODY
@${notify} the live site has not updated for more than ${max_h} hours.

${problem}

Where to look:
- open [pipeline-failure issues](${repo_url}/issues?q=is%3Aissue+is%3Aopen+label%3Apipeline-failure);
- recent [publish](${repo_url}/actions/workflows/publish.yml) and [snapshot](${repo_url}/actions/workflows/snapshot.yml) runs;
- whether the workflows are still enabled ([Actions](${repo_url}/actions)).

Checked by the watchdog: ${run_url}. It comments here (with a mention) at most once a day while the
site stays stale, and closes this issue when it is fresh again.
BODY
)"
  else
    read -r number updated <<<"${open[0]}"
    if [ $((now - $(date -u -d "$updated" +%s))) -gt $((24 * 3600)) ]; then
      act gh issue comment "$number" --body "@${notify} still out of date. ${problem} ${run_url}"
    else
      echo "issue #${number} already updated in the last 24 h"
    fi
  fi
else
  for entry in "${open[@]}"; do
    act gh issue close "${entry%% *}" --comment "Fresh again: last updated ${last}. ${run_url}"
  done
fi
