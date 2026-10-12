#!/usr/bin/env bash
# Open (or comment on) one issue per failing workflow, and close it when the workflow recovers,
# so a failed daily run is visible without watching Actions. Needs GH_TOKEN with issues: write.
# Usage: failure-issue.sh fail|ok "<workflow name>"
set -euo pipefail
mode=$1
workflow=$2
label=pipeline-failure
title="${workflow} workflow is failing"
run_url="${GITHUB_SERVER_URL}/${GITHUB_REPOSITORY}/actions/runs/${GITHUB_RUN_ID}"

gh label create "$label" --color B60205 \
  --description "Daily snapshot or publish run failed" >/dev/null 2>&1 || true

# Open issues for this workflow, read from the REST list: `gh issue list` goes through an index
# that lags just after an issue is created, which produced duplicates in testing.
open_issues() {
  gh api "repos/${GITHUB_REPOSITORY}/issues?labels=${label}&state=open&per_page=100" \
    --jq ".[] | select(.title == \"${title}\") | .number"
}
mapfile -t open < <(open_issues)

if [ "$mode" = fail ]; then
  if [ "${#open[@]}" -gt 0 ]; then
    gh issue comment "${open[0]}" --body "Failed again: $run_url"
  else
    gh issue create --label "$label" --title "$title" --body "$(cat <<BODY
The **${workflow}** run failed: $run_url

The live site keeps its last good version until a run succeeds. Usual causes:
- a publisher released a new schedule file: its SHA-256 has no \`effective_from\` row in
  \`dbt/seeds/source_documents.csv\`, so the build stops for review (by design);
- a source site was down or changed its page layout (snapshot);
- a GitHub or network hiccup: re-run the workflow.

This issue closes itself when the workflow next succeeds.
BODY
)"
  fi
else
  for n in "${open[@]}"; do
    gh issue close "$n" --comment "Recovered: $run_url"
  done
fi
