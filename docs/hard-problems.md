# Hard problems

Seven places in Roshni where the obvious approach, or a tool's default, gave wrong answers. Each
section says what goes wrong, what the code does instead, and which test holds it in place. The
numbers come from [DECISIONS.md](DECISIONS.md) and [data-audit.md](data-audit.md).

## 1. Matching press-release feeder names to feeder lists

**Problem.** IESCO press releases name the feeders they will shut down in free text ("F-10 (Kala
Base)", "Scheme-II", "Dk. Jalal"). The feeder lists name them differently, and the lists have
typos of their own. Without a match a planned shutdown cannot be shown on its feeder's page.

**Why the default fails.** A fuzzy score with a threshold accepts names that look alike but are
different feeders. "Sector-C" and "SECTOR D" score high, as do "Scheme-II" and "SCHEME-I", and
"JALALA" and "JALALIA". When I reviewed the suggestions on 2026-10-10, the near misses were nearly
all of this kind. A wrong match is worse than no match: it puts a shutdown on someone else's
feeder.

**Approach.** Matching runs in three layers, and each layer only handles what the one before it
left undecided.
- Exact normalised names are accepted automatically. Fuzzy candidates
  ([`matchers.py`](../src/roshni/resolve/matchers.py#L108)) are only *suggestions*, stored with
  their score, method and rank; the score is the confidence shown on the site.
- Written rules ([`autoreview.py`](../src/roshni/resolve/autoreview.py#L63)) decide what they can
  mechanically. Roman numerals count as digits, and numbers on both sides must agree. Names that
  differ only in single letters are rejected. A bracketed alias is accepted. Words must share the
  same consonant skeleton *and* the same ending vowels, which keeps out extra-syllable cases such
  as SOHAN/SOHANA. Anything else stays pending.
- The names the rules leave go to an LLM ([`llmreview.py`](../src/roshni/resolve/llmreview.py#L71)).
  It may only pick a candidate already listed for that name, or reject them all. The reply is
  parsed as strict JSON. If one item is invalid (an unknown subject, a candidate that was not
  offered, a missing reason), the whole reply is thrown away and the names stay pending.
- Earlier decisions are never overwritten ([`review.py`](../src/roshni/resolve/review.py#L11)).

**Tests.** [`test_backtest_agrees_with_every_reviewed_decision`](../src/roshni/resolve/test_autoreview.py#L63)
clears every hand-reviewed row in the committed seed, re-decides it with the rules, and fails if
the rules disagree with any of them. When it was written, the rules decided 222 of the 335
reviewed rows. They disagreed on two, and on both the rules were right and the review was wrong,
so the review was corrected. A rule change that contradicts a past decision now fails CI. The LLM
guardrails are covered by
[`test_invented_candidate_rejects_the_whole_reply`](../src/roshni/resolve/test_llmreview.py#L56) and
[`test_partial_answer_leaves_the_rest_pending`](../src/roshni/resolve/test_llmreview.py#L73).

## 2. Schedule versions: identity by SHA-256, dates from the document

**Problem.** Utilities overwrite schedule files in place, under the same URL and often the same
name. A schedule also applies from a date, and that date is neither the day I fetched the file nor
the date on the web page. The Islamabad file had a "Sep-2026" label and was Last-Modified 14 Jan
2026.

**Why the default fails.** If the file name is the key, an overwritten file silently replaces
history. If the fetch time is the effective date, a schedule seems to start on the day the job
happened to run. Leaving new versions undated is not safe either. On 2026-10-23 K-Electric
published a new schedule, and with no date for it the build failed every day for 17 days.

**Approach.** Every stored file is identified by its SHA-256. Every schedule row carries
`source_sha256`, and [`fct_schedule_window`](../dbt/models/marts/fct_schedule_window.sql#L66)
gets `effective_from` by joining on it to the `source_documents` seed.
[`roshni effective-dates`](../src/roshni/parsers/effective.py#L117) adds a seed row for each new
version. It uses the date the file states (K-Electric: "applicable from 23rd October, 2026",
[`stated_date`](../src/roshni/parsers/effective.py#L57)), or else the HTTP Last-Modified date in
Asia/Karachi. Each such row says `automatic: …` in `effective_basis`, and rows that already exist
are never changed. A dbt `not_null` test on `effective_from` stays, so a version that cannot be
dated still fails the build.

**Tests.** [`test_effective.py`](../src/roshni/parsers/test_effective.py#L14) covers the stated
date (including an impossible "31st February"), the Karachi date from Last-Modified, and
`fill_seed` adding each new version once while keeping existing rows.
[`test_schedule_not_applied_before_effective_date`](../src/roshni/live/test_dark_now.py#L132)
checks that dark-now does not apply a schedule before its date.

## 3. K-Electric windows that wrap midnight, in two engines

**Problem.** K-Electric cycles are written `HHMM~HHMM`, and a cycle can cross midnight
(`2235~0205`). IESCO writes its last slot as `23--24`.

**Why the default fails.** `start <= t < end` is never true for a window whose end is earlier
than its start, so every overnight cycle disappears. Subtracting end from start gives a negative
duration, and `24:00` is not a valid time of day. The site also computes "dark now" in the
browser, so the same logic exists in Python and in TypeScript, and the two can drift apart.

**Approach.** Times are stored as minutes of the local day. A window with `end <= start` wraps:
[`cycle_minutes`](../src/roshni/parsers/kelectric.py#L67) adds 1,440 to the duration and sets
`wraps_midnight`. [`window_active`](../src/roshni/live/dark_now.py#L30) tests
`t >= start or t < end` for it, with the start included and the end excluded, and IESCO's 24 is
stored as 1,440. The TypeScript [`windowActive`](../web/src/lib/darkNow.ts#L51) is the same three
lines. To keep the engines in step,
[`scripts/dark_now_oracle.py`](../scripts/dark_now_oracle.py#L22) runs the Python engine at fixed
instants: the midnight and end-exclusive edges, the K-Electric effective date, and dates across
the planned-shutdown and maintenance periods. Each instant is run with and without an IESCO level.
The output is written as an oracle file, and
[`darkNow.oracle.test.ts`](../web/src/lib/darkNow.oracle.test.ts#L35) requires the browser
engine to return the same rows.

**Tests.** [`test_window_wrapping_midnight`](../src/roshni/live/test_dark_now.py#L32) and
[`test_cycle_minutes_wraps_midnight`](../src/roshni/parsers/test_kelectric.py#L31) in Python, and
the matching `windowActive` cases in [`darkNow.test.ts`](../web/src/lib/darkNow.test.ts#L10).
The oracle comparison matched 514 of 514 cases on the 2026-11-08 export. It needs a full export,
so it runs locally before a release and is skipped in CI's fixture build.

## 4. IESCO's schedule is a playbook, not a timetable

**Problem.** Each IESCO workbook lists every feeder's off-hours at six interruption levels: 2, 4,
6, 8, 10 and 12 hours a day. The title says the level depends on the generation shortfall, and no
file says which level is in force.

**Why the default fails.** If you load the workbook as a schedule, you have to pick a level, or
worse, add the levels together. Either way the site would claim an outage that no one announced.
Every feeder also gets the same hours at each level, so comparing feeders or areas would find
"inequity" that the design itself rules out.

**Approach.** IESCO rows are stored as `scenario_level` windows, one set per level
([`fct_schedule_window`](../dbt/models/marts/fct_schedule_window.sql#L1)). Dark-now leaves them
out unless a level is chosen, and then shows them as "if level N is active", with a note saying
why ([`dark_now.py`](../src/roshni/live/dark_now.py#L129)). The equity marts are K-Electric only.
On the site, an IESCO feeder with no level chosen leads with its announced maintenance, which is
dated. The feeder **code** is the join key, zero-padded to six digits, because the names have
typos and the codes lose their leading zeros in Excel.

**Tests.** [`test_dark_now_scenario_level_is_opt_in`](../src/roshni/live/test_dark_now.py#L112)
checks that no scenario row appears without a level and that only the listed levels are accepted.
[`test_normalise_code`](../src/roshni/parsers/test_iesco_xlsx.py#L40) covers the codes.

## 5. PDF text: one canonical extractor, cached by content

**Problem.** The K-Electric schedules, the PBS census tables and the NEPRA reports are PDFs, and
the parsers read the column layout from `pdftotext -layout`.

**Why the default fails.** Git for Windows ships a `pdftotext` too, but it is xpdf 4.00, not
poppler, and its layout output differs. Poppler versions can differ from each other as well. A
parser tuned on one extractor's output gives different counts on another's, and nothing errors.
Re-extracting hundreds of pages on every run is also slow, and it pulls in Docker even when
nothing has changed.

**Approach.** [`pdftext.py`](../src/roshni/parsers/pdftext.py#L25) uses a local `pdftotext` only
if its version banner says poppler. Otherwise it runs the project's Docker image (poppler 25.03,
the canonical version), and the daily job forces the image with `ROSHNI_PDFTEXT=docker`. Text is
cached under `data/cache/pdftext/`, keyed by the file's SHA-256 plus the page range
([`pdf_text`](../src/roshni/parsers/pdftext.py#L68)). The same bytes under a new name hit the
cache, and a file republished in place misses it. CI restores the cache, and the Airflow image
can parse with its older poppler because it reads the canonical text from this cache.

**Tests.** [`test_only_poppler_is_used_locally`](../src/roshni/parsers/test_pdftext.py#L29)
(an xpdf banner is refused) and
[`test_cache_is_keyed_by_content`](../src/roshni/parsers/test_pdftext.py#L40) (a rename hits the
cache; a page range or new bytes miss it). Both are new in this change. The golden counts in
[`tests/test_golden.py`](../tests/test_golden.py) pin the parsed output of the canonical text.

## 6. IESCO maintenance workbooks: one source, eight layouts

**Problem.** IESCO publishes one maintenance workbook per circle each month, and the layouts
differ. The header is in row 1 in some files, row 2 under a title in others, and rows 4–5 in
PD GSC. Islamabad has a merged `TIME` header over `From`/`To`, and GSO merges date and time cells
down over several feeders. One cell in the construction sheet lists several dates. Dates appear
as `DD.MM.YYYY` text, `DD-MM-YYYY`, `YYYY-MM-DD` or Excel dates, and times as `09:00`, Excel
times or `0800 Hrs`.

**Why the default fails.** Reading by fixed column positions breaks on the first file with a
title row. openpyxl returns a value only for the top-left cell of a merged range, so the rows
under a merged date would be dropped as having no date. Parsing a date cell as one date loses
windows. Treating `800` as 08:00 is a guess.

**Approach.** [`iesco_maintenance.py`](../src/roshni/parsers/iesco_maintenance.py#L145) searches
rows 1–8 for a header that names the date, the from and to times and a feeder column. It reads
From/To from the row underneath when the header is a lone merged "TIME". Before it reads any
rows, [`_unmerged`](../src/roshni/parsers/iesco_maintenance.py#L179) fills each merged range from
its top-left cell, as Excel shows it.
[`parse_dates`](../src/roshni/parsers/iesco_maintenance.py#L104) turns a multi-date cell into one
window per date, flagged `multi_date_cell`, and refuses cells that mix dates with other text.
[`parse_time`](../src/roshni/parsers/iesco_maintenance.py#L117) accepts HH:MM, H.MM and four-digit
HHMM but not three digits. Anything still unreadable is quarantined with a reason: 185 of the
18,761 rows in the first eight files. GSO repeats 1,174 circle windows; those copies are flagged
`repeats_circle_window` and counted once.

**Tests.** One generated workbook per layout in
[`test_iesco_maintenance.py`](../src/roshni/parsers/test_iesco_maintenance.py): Islamabad
([L55](../src/roshni/parsers/test_iesco_maintenance.py#L55)), merged data cells
([L84](../src/roshni/parsers/test_iesco_maintenance.py#L84), new in this change), titled
Attock/Jhelum ([L104](../src/roshni/parsers/test_iesco_maintenance.py#L104)), multi-date cells
([L122](../src/roshni/parsers/test_iesco_maintenance.py#L122)), PD GSC
([L140](../src/roshni/parsers/test_iesco_maintenance.py#L140)), no header at all
([L169](../src/roshni/parsers/test_iesco_maintenance.py#L169)), plus parametrised date and time
cases ([L187](../src/roshni/parsers/test_iesco_maintenance.py#L187),
[L205](../src/roshni/parsers/test_iesco_maintenance.py#L205)).

## 7. An incremental model that is portable across warehouses

**Problem.** `fct_planned_shutdown` grows with every press release. On a persistent warehouse,
rebuilding it from all the files every day does work that has already been done.

**Why the default fails.** The models must also build on Databricks, but incremental strategies
differ between adapters. Without a `unique_key`, a strategy just appends, so a file seen twice is
loaded twice. dbt-duckdb accepts `merge` only from a minimum DuckDB version, and its default is
`delete+insert`. Hard-coding one strategy therefore ties the model to one warehouse. The usual
watermark, `fetched_at > max(fetched_at)`, misses a file that was fetched late and loads a
refetched file again.

**Approach.** [`fct_planned_shutdown.sql`](../dbt/models/marts/fct_planned_shutdown.sql#L8) uses
`unique_key='shutdown_id'` (the first 12 characters of the file's SHA-256 plus the row's sequence
number). It picks the strategy per adapter, `merge` on Databricks and `delete+insert` on DuckDB,
so one SQL file builds on both. An incremental run selects only rows whose `source_sha256` is not
yet in the table. A release never changes once published, so the file's hash is the right
watermark. A full run and an incremental run both gave 1,930 unique rows. CI and the daily job
build a fresh DuckDB file, so in production the model always runs as a full build; the
incremental path matters on a persistent warehouse such as Databricks.

**Tests.** [`test_second_run_loads_only_new_release_files`](../tests/test_incremental.py#L43),
new in this change, runs dbt on DuckDB against a small generated Parquet file. The first run is a
full build. A second run with nothing new adds no duplicates. On a third run, a row of an
already-loaded file has been edited and a new file has arrived: only the new file's row is added,
and the old rows stay as they were first loaded.
