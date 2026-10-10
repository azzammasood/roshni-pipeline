# Reviewing matches (owner)

> 2026-10-10: the owner delegated this review to Claude. All rows already carry a decision and a
> `claude-review` note with the reason. Use this guide only to overturn a decision.

Three files in `dbt/seeds/` hold match candidates. Open them in Excel or any CSV editor.

| File | What is matched |
|---|---|
| `review_feeder_locality.csv` | IESCO feeder → census village/town (same district) |
| `review_press_feeder.csv` | Feeder name printed in a press release → IESCO feeder |
| `review_ibc_subdivision.csv` | K-Electric IBC area → Karachi census sub-division (draft) |

Each row: `subject_name` (what we try to match), `candidate_name`, `score` (0 to 100), `status`.

**What to do:** in the `decision` column write `accepted` or `rejected`. Leave it blank to decide later. Optional `note`.
- Focus on `status = suggested` rows. `auto_exact` rows already count; write `rejected` only if one is wrong.
- Accept at most the right candidate(s); a feeder may genuinely serve several villages.
- For a subject with `no_candidate`, you may add your own row: copy the line, put the correct `candidate_id` and `candidate_name` (from another row or `dim_area`), and write `accepted`.
- `review_ibc_subdivision.csv`: nothing counts until accepted. IBCs and sub-divisions are different kinds of area, so accept only where you are confident they correspond.

Then run:
```
uv run roshni build
uv run roshni resolve   # optional: regenerates candidates, keeps your decisions
```
