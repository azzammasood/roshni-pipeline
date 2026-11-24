# Benchmarks: how the warehouse build scales

Measured 2026-11-24 between 08:54 and 09:53 UTC on one laptop with `scripts/benchmark.py`.
Most results are from main before the join fix; the [After the fix](#after-the-fix) section
measures the same builds with the fixed `stg_pbs_urban`.
Every number below was copied from that script's JSON output (or, for the join timing, from the
DuckDB session quoted under [Finding](#finding-one-join-is-quadratic)). Nothing is estimated or
rounded up:
- times are seconds as recorded, to 3 decimals;
- memory is MiB rounded down to one decimal place;
- sizes are bytes as the file system reports them;
- ranges are lowest–highest of the repeats.

## Summary

| Scenario | Input rows | Wall time | Peak memory | DuckDB file | dbt |
|---|---|---|---|---|---|
| Full `roshni build`, today's data (3 runs) | 181,660 | 11.905–12.091 s | 287.3–335.6 MiB | 17,051,648–17,575,936 B | PASS=172 |
| Incremental `fct_planned_shutdown`, one new press release (3) | +198 | 5.864–7.176 s | 176.3–176.8 MiB | 17,838,080 B | PASS=6 |
| Synthetic 10×, full build (3) | 1,813,315 | 65.186–66.998 s | 1,057.7–1,073.5 MiB | 97,005,568–98,054,144 B | PASS=172 |
| Synthetic 100×, full build (1) | 18,129,865 | 1,748.282 s | 3,922.4 MiB | 921,186,304 B | PASS=172 |
| Synthetic 100× without `dim_area_indicators+` (1) | 18,129,865 | 86.801 s | 3,750.0 MiB | 416,296,960 B | PASS=153 |
| **After the join fix:** synthetic 10×, full build (3) | 1,813,315 | 20.041–21.343 s | 965.6–1,035.0 MiB | 96,481,280–97,005,568 B | PASS=172 |
| **After the join fix:** synthetic 100×, full build (1) | 18,129,865 | 138.940 s | 3,961.3 MiB | 998,780,928 B | PASS=172 |

- **Today's data builds in about 12 s, and over half of that is fixed cost.** A full build is
  43 relations, 172 dbt nodes. Process start, dbt import and project parse take 6.865–7.136 s on
  their own; dbt reports 4.605–4.780 s for the SQL and tests.
- **The incremental model works, but at today's size dbt's fixed cost dominates.** After one new
  press release (198 windows), the model itself runs in 0.159–0.166 s and adds exactly those
  rows: 4,212 → 4,410. With nothing new it runs in 0.144–0.148 s. The whole command takes
  5.864–7.176 s either way.
- **One model did not scale, and is now fixed.** Before the fix, `dim_area_indicators` took
  0.942–1.001 s at 1×, 53.422–56.172 s at 10× and 1,710.352 s at 100×: 98 % of the 100× build's
  dbt time. The cause was one join condition (see [Finding](#finding-one-join-is-quadratic)).
  After the fix it takes 39.565 s at 100×, and the whole 100× build takes 138.940 s instead of
  1,748.282 s, with every output value unchanged.
- **Everything else scales well.** Without that model and its downstream (153 nodes), the build
  takes 11.696–12.413 s at 1×, 15.674–16.020 s at 10× and 86.801 s at 100×. Peak memory stays
  under 4 GiB on a 16 GB laptop at 100×.

## Machine

| | |
|---|---|
| CPU | 11th Gen Intel Core i7-1165G7 @ 2.80 GHz, 4 cores, 8 threads |
| RAM | 16,844,595,200 bytes |
| Disk | SSD |
| Power | AC (`Win32_Battery` status 2, charge 100 %, read after the runs) |
| OS | Windows 11 Pro (10.0.26100) |
| Software | Python 3.12.13, DuckDB 1.5.6, dbt-core 1.12.5, dbt threads = 4 (`dbt/profiles.yml`) |
| Code | branch `perf/benchmarks` from main `eaa8c57`; models unchanged |

The CPU was 0.8–59.1 % busy in the second before each build (`cpu_busy_percent_before`; other
programs were open). The highest value, 59.1 %, was just before the 100× full build.

### Discarded first batch

A first batch on 2026-11-23 (17:10–17:57 UTC) ran 2–5× slower, and its repeats varied by up to
2.18× (10× full build: 117.360 s against 256.780 s). For example, the full build took 34.829–58.879 s there, against 11.905–12.091 s here.
During that batch the Windows log shows Modern Standby transitions (Kernel-Power events 506 and
507), and the laptop then slept overnight. The cause of the slowdown was not established, so none
of those numbers are used here.

The script now records each run's UTC start and end, and the longest gap between its 50 ms
memory polls. A gap much longer than 50 ms means the process was paused. Across every run used
here, the longest gap was 0.503 s, in the 29-minute 100× build. The app also held the machine
awake for these runs.

## Method

`uv run --group bench python scripts/benchmark.py` (the `bench` group adds `psutil`). Each
scenario copies its inputs to a fresh temporary folder, builds a fresh DuckDB file there, and
points dbt's `target/` folder there too (`DBT_TARGET_PATH`). Real data, seeds and
`data/roshni.duckdb` are never written.

- **Inputs:** `roshni parse` on snapshot store commit `a945c34` (2026-11-23 12:51 UTC), with
  canonical poppler `pdftotext` from the project Docker image. That gives 181,660 parsed rows in
  16 tables. The largest are `iesco_schedule_slot` (46,411), `iesco_maintenance_window` (38,301),
  and `pbs_rural_population` and `pbs_rural_housing` (33,285 each).
- **Each build** is `roshni build --parsed … --db …` in a child process. It runs 3 times, except
  at 100× (once each).
- **Wall time** is measured around the child process. **dbt time** is `elapsed_time` from dbt's
  `run_results.json`, which leaves out process start and project parse. Per-node times are each
  node's `execution_time`.
- **Peak memory** is the OS-kept peak working set (`peak_wset`) of the largest process in the
  child's tree; a uv venv's `python.exe` is a launcher with the real interpreter as its child. It
  is read every 50 ms, so growth in the last 50 ms before exit could be missed.
- **Rows** are `count(*)` over every table and view after the build. At 100×, views are not
  counted (see [Caveats](#caveats)).
- **dbt's anonymous usage stats are switched off** during the timings, so no network call is
  timed.

| Scenario | What it does |
|---|---|
| overhead | `roshni build --command parse`: process start, dbt import, project parse, no SQL |
| full | full `roshni build` (seeds, models, tests) on the real parsed data |
| incremental | full build without the newest press release (release 21, 198 windows, fetched 2026-11-22). Then that release is added back and `--select fct_planned_shutdown` is run, then the same again with nothing new, then `--select fct_planned_shutdown+` (the model and everything downstream) |
| synthetic N× | full build on the parsed data replicated N times with new keys |
| synthetic N×, excluded | the same with `--exclude dim_area_indicators+`, a new `roshni build` option passed to dbt |

**Synthetic replication.** Copy *k* (k ≥ 1) of every row gets new keys:
- string keys get the suffix `~k`: feeder codes and names, K-Electric normalised names, census
  `area_key` and `name`, news titles and links;
- integer row keys are offset by k × 10,000,000: `sheet_row`, press-release `seq`, K-Electric
  `serial`.

Copy *k* of a feeder therefore joins copy *k* of its schedule. Replicas match none of the review
seeds, which are never changed. The NEPRA tables and the K-Electric schedule-version summary
describe documents, not entities, so they stay at 1×. The 1× set is a byte-for-byte copy of the
real input.

## Results

### Today's data

| Run | Wall s | dbt s | Peak MiB | CPU busy before | DuckDB bytes | dbt result |
|---|---|---|---|---|---|---|
| overhead 1 | 6.955 | – | 148.5 | 2.7 % | – | parse only |
| overhead 2 | 6.865 | – | 148.1 | 2.7 % | – | parse only |
| overhead 3 | 7.136 | – | 148.3 | 4.1 % | – | parse only |
| full 1 | 12.064 | 4.777 | 335.6 | 2.2 % | 17,313,792 | PASS=172 |
| full 2 | 12.091 | 4.780 | 326.8 | 5.5 % | 17,575,936 | PASS=172 |
| full 3 | 11.905 | 4.605 | 287.3 | 2.2 % | 17,051,648 | PASS=172 |

Wall minus dbt time was 7.287–7.311 s for the full builds, about the same as the parse-only runs.

### Incremental rebuild of `fct_planned_shutdown`

`fct_planned_shutdown` went from 4,212 to 4,410 rows in all three repeats. The DuckDB file was
17,838,080 bytes afterwards.

| Step | Wall s (3 runs) | dbt s | Model s | Peak MiB | dbt result |
|---|---|---|---|---|---|
| base full build (without release 21) | 13.065 / 12.710 / 12.472 | 4.954 / 5.006 / 4.828 | – | 319.6 / 295.1 / 292.6 | PASS=172 |
| `--select fct_planned_shutdown`, one new release | 7.176 / 5.864 / 5.949 | 0.412 / 0.412 / 0.426 | 0.166 / 0.159 / 0.159 | 176.3 / 176.8 / 176.5 | PASS=6 |
| same, nothing new | 5.748 / 5.750 / 5.943 | 0.398 / 0.410 / 0.411 | 0.144 / 0.147 / 0.148 | 176.3 / 175.5 / 175.7 | PASS=6 |
| `--select fct_planned_shutdown+` | 6.110 / 6.867 / 6.184 | 0.649 / 0.678 / 0.669 | 0.140 / 0.136 / 0.142 | 176.3 / 176.2 / 175.9 | PASS=15 |

"Model s" is the model's own `execution_time`; the rest of the dbt time is its 5 tests (PASS=15
with `+`: the model, its downstream models and their tests). At today's size the incremental model saves almost nothing, because dbt's
fixed cost is far larger than the SQL. It matters for growth: a new release costs the same however
many releases are already loaded, while a full refresh rescans them all. CI and the daily publish
build a fresh DuckDB file, so they always take the full path.

### Synthetic scale, full build

| Factor | Input rows | Wall s | dbt s | `dim_area_indicators` s | Peak MiB | DuckDB bytes | dbt result |
|---|---|---|---|---|---|---|---|
| 1× | 181,660 | 12.665 / 13.370 / 12.467 | 5.047 / 4.857 / 4.841 | 0.942 / 1.001 / 0.969 | 330.7 / 312.3 / 289.3 | 16,789,504 / 17,051,648 / 17,051,648 | PASS=172 |
| 10× | 1,813,315 | 65.186 / 66.998 / 66.360 | 56.357 / 58.828 / 58.238 | 53.422 / 56.172 / 55.710 | 1,073.5 / 1,062.5 / 1,057.7 | 97,267,712 / 98,054,144 / 97,005,568 | PASS=172 |
| 100× | 18,129,865 | 1,748.282 | 1,733.935 | 1,710.352 | 3,922.4 | 921,186,304 | PASS=172 |

At 100× the next slowest models were `fct_schedule_window` (98.722 s), `fct_maintenance_window`
(72.179 s), `dim_feeder` (63.624 s) and `mart_feeder_dark_hours` (54.288 s). Per-node times add
up to more than the dbt time because 4 threads run in parallel.

### Synthetic scale without `dim_area_indicators+`

`--exclude dim_area_indicators+` leaves out 4 models (`dim_area_indicators`, `dim_area`,
`mart_ke_subdivision_equity`, `rpt_spearman`) and 15 tests, so 153 nodes run.

| Factor | Input rows | Wall s | dbt s | Peak MiB | DuckDB bytes | dbt result |
|---|---|---|---|---|---|---|
| 1× | 181,660 | 11.958 / 12.413 / 11.696 | 4.051 / 4.092 / 4.066 | 258.3 / 278.3 / 265.5 | 9,711,616 (all 3) | PASS=153 |
| 10× | 1,813,315 | 15.703 / 16.020 / 15.674 | 7.450 / 6.955 / 7.247 | 897.8 / 921.1 / 920.5 | 37,761,024 / 37,498,880 / 38,023,168 | PASS=153 |
| 100× | 18,129,865 | 86.801 | 73.188 | 3,750.0 | 416,296,960 | PASS=153 |

At 100× the slowest nodes are tests on the view `int_ke_feeder_join`:
- `unique` on `schedule_name_norm`: 29.042 s;
- `unique` on `list_name_norm`: 27.504 s;
- `not_null` on `schedule_name_norm`: 24.563 s.

Next is the model `fct_schedule_window` (25.790 s). A test on a view re-runs the view's join
each time. Making `int_ke_feeder_join` a table would be the next step if this mattered.

### Finding: one join is quadratic

`dim_area_indicators` reads the view `stg_pbs_urban`. That view joins census tables 33 and 34
with a LEFT JOIN whose ON clause includes `pop.key_rows = 1`, a condition on the left side only.
DuckDB 1.5.6 plans the join as a `BLOCKWISE_NL_JOIN` (nested loop) instead of a hash join. Timed
in a DuckDB session on 2026-11-24 at 09:39 UTC (same machine, same Parquet), counting the join's
rows:

| Urban population rows | With `pop.key_rows = 1` in ON | Without it |
|---|---|---|
| 10,352 (1×) | 0.227 s | 0.015 s |
| 103,520 (10×) | 18.726 s | 0.102 s |

Both versions return the same number of rows here, but dropping the condition is not a correct
fix: it would let a population row with an ambiguous key take a housing row. A fix has to keep
every output value identical. Real census data will not grow 10×: PBS publishes these tables
once per census. So this matters for reuse of the pattern more than for Roshni's daily build.

### After the fix

`stg_pbs_urban` now applies the uniqueness rules before the join:
- housing rows whose key is not unique are filtered out in their own CTE;
- an ambiguous population key becomes a NULL join key (`case when key_rows = 1 then area_key
  end`), which matches nothing, exactly as the old ON condition did.

The join is then a plain equality join, and DuckDB plans it as a `HASH_JOIN`. Same session
method as above: 0.019 s at 1× and 0.097 s at 10× (was 0.227 s and 18.726 s).

**Same outputs.** A full build on today's data was compared with a build of main (`d4cfaab`),
relation by relation, with `EXCEPT ALL` in both directions. 42 of 43 relations are identical.
The 43rd, `mart_build_info`, differs only in `built_at`. Today's data has no ambiguous urban
keys, so `tests/test_pbs_urban_join.py` covers those cases with hand-made rows: an ambiguous
population key, an ambiguous housing key, a missing housing row, and the same key in another
province. The test passes on both the old and the new SQL.

| Factor | Input rows | Wall s | dbt s | `dim_area_indicators` s | Peak MiB | DuckDB bytes | dbt result |
|---|---|---|---|---|---|---|---|
| 1× | 181,660 | 16.588 / 13.293 / 14.153 | 6.212 / 4.875 / 5.036 | 0.343 / 0.293 / 0.316 | 292.0 / 329.4 / 281.5 | 17,051,648 / 17,313,792 / 17,051,648 | PASS=172 |
| 10× | 1,813,315 | 21.343 / 20.041 / 21.256 | 11.907 / 11.443 / 10.956 | 3.478 / 2.831 / 3.164 | 969.9 / 1,035.0 / 965.6 | 97,005,568 / 96,481,280 / 96,743,424 | PASS=172 |
| 100× | 18,129,865 | 138.940 | 123.957 | 39.565 | 3,961.3 | 998,780,928 | PASS=172 |

Run 2026-11-24 09:47–09:53 UTC. The longest poll gap was 0.253 s. At 100× the slowest node is
now `fct_schedule_window` (55.367 s), then `dim_area_indicators` (39.565 s),
`fct_maintenance_window` (38.182 s) and the `unique` test on
`int_ke_feeder_join.schedule_name_norm` (38.039 s). No single model dominates any more.

### Rows per relation

From the last full build at each factor. Views are not counted at 100× (shown as –).

| Relation | Type | 1× (today) | 10× | 100× |
|---|---|---|---|---|
| `dim_area` | table | 43,673 | 436,406 | 4,363,736 |
| `dim_area_indicators` | table | 43,637 | 436,370 | 4,363,700 |
| `dim_feeder` | table | 1,777 | 17,780 | 177,800 |
| `fct_maintenance_window` | table | 20,526 | 205,260 | 2,052,600 |
| `fct_planned_shutdown` | table (incremental) | 4,410 | 44,100 | 441,000 |
| `fct_planned_shutdown_feeder` | table | 4,410 | 44,100 | 441,000 |
| `fct_schedule_window` | table | 48,732 | 487,320 | 4,873,200 |
| `feeder_locality_match` | table | 149 | 149 | 149 |
| `hours_of_day` | seed | 24 | 24 | 24 |
| `int_ke_feeder_join` | view | 572 | 5,710 | – |
| `ke_ibc_subdivision` | table | 16 | 16 | 16 |
| `mart_build_info` | table | 1 | 1 | 1 |
| `mart_feeder_dark_hours` | table | 55,485 | 554,850 | 5,548,500 |
| `mart_ke_feeder_hours` | table | 572 | 5,710 | 57,100 |
| `mart_ke_ibc_equity` | table | 30 | 30 | 30 |
| `mart_ke_schedule_history` | table | 2 | 2 | 2 |
| `mart_ke_subdivision_equity` | table | 13 | 13 | 13 |
| `mart_monthly_iesco_shutdowns` | table | 37 | 37 | 37 |
| `mart_monthly_maintenance` | table | 46 | 46 | 46 |
| `mart_nepra_ke_order` | table | 10 | 10 | 10 |
| `mart_nepra_load_shedding` | table | 130 | 130 | 130 |
| `mart_news_headline` | table | 12 | 12 | 12 |
| `quarantine_area` | table | 0 | 0 | 0 |
| `quarantine_feeder` | table | 4 | 40 | 400 |
| `quarantine_schedule_window` | table | 179 | 1,790 | 17,900 |
| `review_feeder_locality` | seed | 1,163 | 1,163 | 1,163 |
| `review_ibc_subdivision` | seed | 35 | 35 | 35 |
| `review_press_feeder` | seed | 2,485 | 2,485 | 2,485 |
| `rpt_ke_anomalies` | table | 6 | 6 | 6 |
| `rpt_match_rates` | table | 16 | 16 | 16 |
| `rpt_spearman` | table | 6 | 6 | 6 |
| `source_documents` | seed | 9 | 9 | 9 |
| `stg_iesco_feeder` | view | 1,105 | 11,050 | – |
| `stg_iesco_maintenance_window` | view | 38,301 | 383,010 | – |
| `stg_iesco_press_release_window` | view | 4,410 | 44,100 | – |
| `stg_iesco_schedule_slot` | view | 46,411 | 464,110 | – |
| `stg_ke_feeder_list` | view | 623 | 6,230 | – |
| `stg_ke_schedule` | view | 625 | 6,250 | – |
| `stg_ke_schedule_cycle` | view | 2,500 | 25,000 | – |
| `stg_nepra_load_shedding` | view | 350 | 350 | – |
| `stg_news_headline` | view | 56 | 560 | – |
| `stg_pbs_rural` | view | 33,285 | 332,850 | – |
| `stg_pbs_urban` | view | 10,352 | 103,520 | – |

Some marts do not grow with the synthetic data:
- marts that aggregate by month, circle, IBC or NEPRA category, because those dimensions are not
  replicated;
- marts that join to the review seeds (`feeder_locality_match`, `ke_ibc_subdivision`, the K-E
  equity marts), because replicas match no seed row.

So the synthetic data exercises the row-level models, not the matching or the aggregate marts.

## Caveats

- **Replication is not variety.** Copies share every value except their keys. Compression,
  dictionary encoding and join selectivity behave differently on real data with ten times more
  distinct feeders, dates and names. The file sizes at 10× and 100× are likely smaller than real
  data of that size would give.
- **One laptop.** These are single-machine numbers on Windows, with other programs open. A CI
  runner or a server gives different absolute times. The discarded first batch shows how far
  the same laptop can drift. The 100× rows are single runs.
- **Windows memory.** Peak memory is the working set, which counts shared pages. Linux RSS
  would differ.
- **Warehouse only.** Parsing (`roshni parse`), validation, resolve, report, export and the site
  build are not timed.
- **Views are not counted at 100×.** `count(*)` on a view re-runs its query, and on
  `stg_pbs_urban` that is the slow join above.
- **The incremental scenario simulates arrival** by holding back the newest release from a full
  build. It uses the same code path as a run on a persistent warehouse.

## Reproduce

```
uv run roshni parse --snapshots <store> --census-from census
uv run --group bench python scripts/benchmark.py --factors 1,10 --repeat 3
uv run --group bench python scripts/benchmark.py --only synthetic --factors 1,10 --repeat 3 --exclude "dim_area_indicators+"
uv run --group bench python scripts/benchmark.py --only synthetic --factors 100 --exclude "dim_area_indicators+"
uv run --group bench python scripts/benchmark.py --only synthetic --factors 100 --timeout 1800
```

Results go to `data/benchmarks/<timestamp>.json` (git-ignored), or wherever `--out` points.
The JSON files behind this page are `main2.json`, `excl2.json`, `excl100b.json` and
`x100b.json` (before the fix), and `fix-1-10.json` and `fix-100.json` (after it), all from
runs on 2026-11-24.
