#!/usr/bin/env bash
# Ask Roshni watchdog: read the Worker's daily usage counts (GET /v1/stats; counts only) and keep
# one "ask-health" issue in step with them. Unhealthy (today, Pakistan date, with at least
# MIN_QUESTIONS questions): more than MAX_FAILED_PCT of plans failed (no model produced a valid
# query, usually every free model busy), or half of the plans took longer than SLOW_S seconds;
# or the Worker did not answer at all. Opens the issue (or comments once a day, @-mentioning
# NOTIFY); closes it when healthy. DRY_RUN=1 prints the issue commands instead.
set -euo pipefail
url=${STATS_URL:-https://roshni-ask.ahmaduzzammasood.workers.dev/v1/stats}
min_q=${MIN_QUESTIONS:-5}
max_failed=${MAX_FAILED_PCT:-20}
slow_s=${SLOW_S:-8}
notify=${NOTIFY:-azzammasood}
label=ask-health
title="Ask Roshni is failing or slow"
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
today=$(date -u -d "@$((now + 5 * 3600))" +%Y-%m-%d)
if stats=$(curl -fsS --retry 3 --retry-delay 20 --max-time 30 -H "Origin: https://azzammasood.github.io" "$url"); then
  problem=$(STATS="$stats" TODAY="$today" MIN_Q="$min_q" MAX_F="$max_failed" SLOW="$slow_s" python3 - <<'PY'
import json, os
s = json.loads(os.environ["STATS"])
day = next((d for d in s["days"] if d["date"] == os.environ["TODAY"]), None)
if not day or day["questions"] < int(os.environ["MIN_Q"]):
    raise SystemExit(0)
plans = day["planned"] + day["refused"] + day["failed"]
failed = 100 * day["failed"] / plans if plans else 0
out = []
if failed > float(os.environ["MAX_F"]):
    out.append(f"{day['failed']} of {plans} plans failed today ({failed:.0f}%).")
hist, buckets = day["plan_latency"], s["buckets_s"]
n, seen = sum(hist), 0
for i, c in enumerate(hist):
    seen += c
    if n and seen >= n / 2:
        if i >= len(buckets) or buckets[i] > float(os.environ["SLOW"]):
            limit = f"over {buckets[-1]}" if i >= len(buckets) else f"up to {buckets[i]}"
            out.append(f"Median planning time today is {limit} s.")
        break
print(" ".join(out))
PY
)
else
  problem="Could not read ${url} (after 3 retries)."
fi
echo "checked ${url} for ${today}: ${problem:-healthy}"

act gh label create "$label" --color D93F0B \
  --description "Ask Roshni's Worker is failing or slow" >/dev/null 2>&1 || true

mapfile -t open < <(
  gh api "repos/${GITHUB_REPOSITORY}/issues?labels=${label}&state=open&per_page=100" \
    --jq ".[] | select(.title == \"${title}\") | \"\(.number) \(.updated_at)\""
)

if [ -n "$problem" ]; then
  if [ "${#open[@]}" -eq 0 ]; then
    act gh issue create --label "$label" --title "$title" --body "$(cat <<BODY
@${notify} Ask Roshni looks unhealthy today (${today}, Pakistan date).

${problem}

Where to look: the [health page](https://azzammasood.github.io/roshni-site/en/health/#ask), Groq's
status and free-plan limits, and recent [worker-deploy](${repo_url}/actions/workflows/worker-deploy.yml) runs.

Checked by the watchdog: ${run_url}. It comments here at most once a day while the problem lasts
and closes this issue when Ask Roshni is healthy again.
BODY
)"
  else
    read -r number updated <<<"${open[0]}"
    if [ $((now - $(date -u -d "$updated" +%s))) -gt $((24 * 3600)) ]; then
      act gh issue comment "$number" --body "@${notify} still unhealthy. ${problem} ${run_url}"
    else
      echo "issue #${number} already updated in the last 24 h"
    fi
  fi
else
  for entry in "${open[@]}"; do
    act gh issue close "${entry%% *}" --comment "Healthy again (${today}). ${run_url}"
  done
fi
