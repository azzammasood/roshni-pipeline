# 5. Entity resolution: written rules first, then an LLM that may only choose listed candidates

- Status: accepted
- Date: 2026-10-10 (review loop), 2026-10-13 (rules and LLM)

## Context

IESCO press releases name feeders in free text ("Dk Chaudharian", "Askari Heights (IV)"), while
the schedule workbooks list them by code and official name ("DHOKE CHODRIAN"). New names arrive
every day. A wrong match puts a shutdown on the wrong feeder, which is worse than no match. There
is no human reviewer on call: the owner delegated review, and the pipeline has to run unattended.

## Options considered

1. **Fuzzy score with a threshold.** Fast, but scores cannot tell "Club-1" from "Club-2" or
   "JALALA" from "JALALIA".
2. **Human review of every suggestion.** Accurate, but it stops the pipeline whenever nobody is
   available.
3. **An LLM matching names freely.** Handles spelling well, but it can invent a feeder and its
   decisions cannot be tested.
4. **A layered resolver:** exact unique matches auto-accept; written, tested rules decide what
   they can; an LLM decides the rest but only among candidates already listed; anything still
   unclear stays pending.

## Decision

I chose option 4.

- **Candidates:** RapidFuzz `ratio` ≥ 70 with numbers kept for press-release names; top 3, with
  the score stored as confidence (score / 100) and shown on the site.
- **Rules** (`src/roshni/resolve/autoreview.py`): reject when the subject already has an exact or
  accepted match, when numbers differ, or when names differ only in single letters; accept when the
  bracketed part names the feeder, or when every word has the same consonant skeleton and the same
  ending vowels and no other candidate qualifies. Normalisation treats roman numerals as digits,
  splits "G8" into "G-8", drops leading zeros and expands "Dk" to "Dhoke".
- **LLM** (`src/roshni/resolve/llmreview.py`): the OpenRouter chain used for narration, under the
  same $0.01 cap, at most 40 names a run. The reply must be JSON that validates completely: known
  subject, offered candidate, one decision per name. Otherwise it is ignored. The prompt says "when
  unsure, reject".
- **Decisions are stored once** in `dbt/seeds/review_*.csv` with a note (`auto-review: …`,
  `llm-review <date> <model>: …`, `claude-review …`), committed back to main by the publish job.
  An owner or Claude decision is never overwritten.

## Consequences

- Most names are decided by code I can read and test; the LLM handles only the remainder and
  cannot add a feeder that was not offered.
- The rules are conservative, so some true matches stay pending or rejected.
- A bot commit to main on days when seeds change, so local seed edits need a pull first.
- Every rule change has to pass the backtest below, which slows rule changes on purpose.

## Evidence

- Backtest: [`test_backtest_agrees_with_every_reviewed_decision`](../../src/roshni/resolve/test_autoreview.py)
  clears every past reviewed row and re-decides it. The rules decide 222 of 335 reviewed rows and
  agree with all of them except two where the earlier review was wrong (Scheme-II, Iqbal Road-II);
  correcting those moved 10 windows from unmatched to matched (1,058 to 1,068).
- LLM guardrail tests: [`src/roshni/resolve/test_llmreview.py`](../../src/roshni/resolve/test_llmreview.py)
  (`test_invented_candidate_rejects_the_whole_reply`, `test_partial_answer_leaves_the_rest_pending`).
- The site shows the method, confidence, reviewer and reason for each match (export 1.2.0
  `match_review`).
- DECISIONS.md entries 2026-10-10 (Phase 4, Phase 4 review), 2026-10-13 (Automatic review, LLM
  review).
