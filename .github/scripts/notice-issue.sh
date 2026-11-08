#!/usr/bin/env bash
# Post what the pipeline decided on its own (a new listing row fetched, a new schedule version
# dated automatically) to one open "Pipeline notices" issue, so changes stay visible without
# stopping the run. The run itself still succeeds. Needs GH_TOKEN with issues: write.
# Usage: notice-issue.sh "<workflow name>" <notice file>
set -euo pipefail
workflow=$1
file=$2
[ -s "$file" ] || exit 0
label=pipeline-notice
title="Pipeline notices"
run_url="${GITHUB_SERVER_URL}/${GITHUB_REPOSITORY}/actions/runs/${GITHUB_RUN_ID}"
body="$(printf '**%s** (%s)\n\n%s\n' "$workflow" "$run_url" "$(cat "$file")")"

gh label create "$label" --color 0E8A16 \
  --description "Something the pipeline handled automatically" >/dev/null 2>&1 || true
open=$(gh api "repos/${GITHUB_REPOSITORY}/issues?labels=${label}&state=open&per_page=100" \
  --jq ".[] | select(.title == \"${title}\") | .number" | head -1)
if [ -n "$open" ]; then
  gh issue comment "$open" --body "$body"
else
  gh issue create --label "$label" --title "$title" --body "$(printf '%s\n\n%s\n' \
    "Things the pipeline handled on its own. Nothing here stops the site from updating; close this issue once read." \
    "$body")"
fi
