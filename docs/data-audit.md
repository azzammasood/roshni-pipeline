# Data audit

Facts established before the build (audit, 2026-10-05/06). **These numbers are regression oracles.** If a number changes because a source was republished, surface it; never silently update a test.

PDF text figures come from poppler `pdftotext -layout`, which is canonical and runs in the project Docker image.

## 0. `data-sources/` inventory (2026-10-06)

Hand-downloaded, git-ignored, never committed. Regenerate with `uv run python scripts/inventory.py`. All 21 expected files are present. One extra file (the ResearchGate forecast paper, excluded per the brief) is ignored and not read.

| File | Bytes | SHA-256 |
|---|---:|---|
| `iesco-islamabad-sep26.xlsx` | 30,943 | `f03361962a600fe2b50ecb774d423b6e9135e550044a2cc2f68efe73bc36a13b` |
| `iesco-rawalpindi-sep26.xlsx` | 34,887 | `1f053d92b28f68e08e952eb068811d4af07b3d1cf9ee3d5613f1c9f9ae2af9c5` |
| `iesco-attock-sep26.xlsx` | 23,608 | `06abfb8bd325e6f4a826bb92ce24989d44363a93b2962662c5e2223488c553a4` |
| `iesco-jhelum-sep26.xlsx` | 18,211 | `0e4619a73324c7b545b6d3a38d1bf641249c121a9ba1a6b6b53938bd3f9887bb` |
| `iesco-chakwal-sep26.xlsx` | 19,129 | `bdec3947102255082fd363d3914274d6407b6c2ade240d2993f4205df792b321` |
| `iesco-ajk-sep26.xlsx` | 20,633 | `82bb6206dc3d4c57faa43da9efc28849e1cb59615029e5f1591858258fd54cbe` |
| `iesco-press-release-eng-oct3.pdf` | 109,091 | `43804588ac80149f1d23b14ecaf23c92633c25c7c70c0398bfd51a55df559165` |
| `iesco-press-release-eng-oct5.pdf` | 106,829 | `56dec39295b94803983aa53f4ef6ac0f7a5b703397d3c955708c8c5b4ed4bc63` |
| `iesco-press-release-urdu-oct5.pdf` | 428,911 | `d6372c0cff5a0b84de6acb3642a6b1d7642a14abe47370805208606ad467bc0a` |
| `kelectric-feeder-list.pdf` | 382,786 | `a23cf501a14dbb2df618994d340aa4988bb797c5754517095cd234a35fe6e3b2` |
| `kelectric-load-shed-schedule.pdf` | 153,736 | `0dc6ea8cbbe9fb7e213d3d26bc262d80700644191943e97409294925b4068248` |
| `table_33_punjab_districts.xlsx` | 1,012,615 | `98d6244c28625dfe5a67d4d9666c5e1b6506e61017a3855d5f2bc2078397340d` |
| `table_33_islamabad.xlsx` | 27,418 | `d1e87b65b08e8193d712794075260b64755be9cce22224f8dc2d2274cfd2f5bc` |
| `table_33_sindh_districts.pdf` | 959,837 | `c8f2ee3e872644aa67a10b0ec86a2a642477dd1dfaddcc436c7f2828dbedc471` |
| `table_34_punjab_districts.xlsx` | 490,502 | `93f3aa6122549d61203fc167d0e65ed93093288927d73930eeb9981e17d74c75` |
| `table_34_islamabad.xlsx` | 18,733 | `f205c282c37bb981a976113f07f89dd02ba8ec63023b5731649efff7c9c18bca` |
| `table_34_sindh_districts.pdf` | 1,068,574 | `eb5c82f84f3f28c2cdd7641c9ad91dcbe9a88d0b3eff829b23947cf132298595` |
| `table_31_punjab_districts.pdf` | 13,395,346 | `601b3120b756291993a10a0e23ae9f35baf77806b38c18072218d6a0fc50c7c4` |
| `table_31_islamabad.pdf` | 262,666 | `cc5380eed832fe3d6ddca9d6705654b9a173325fa32baaf92c96948d329c2e5e` |
| `table_32_punjab_districts.pdf` | 7,126,739 | `b0a6ce9412ab34ea12694996b400b37411940346f3bd63ced7e6a3ab1cf10bcf` |
| `table_32_islamabad.pdf` | 234,120 | `265774635dd8d2946580059eb71aa1d3ac9997494ca6c2de771c27b0aef7d57d` |

Baselines confirmed: `iesco-islamabad-sep26.xlsx` = 30,943 bytes; `kelectric-feeder-list.pdf` = 382,786 bytes.
The two big PBS PDFs (`table_31_punjab_districts.pdf`, 789 pages; `table_32_punjab_districts.pdf`, 488 pages) never go into git. CI uses trimmed extracts in `tests/fixtures/`.

## 1. IESCO load-shedding XLSX
- Row counts: islamabad 272, rawalpindi 352, attock 164, jhelum 90, chakwal 102, ajk 125 = **1,105 rows** (1,103 unique circle+code pairs; 980 rows excluding AJK).
- Layout: row 1 title, row 2 header (serial, grid, feeder, code, then columns for 2, 4, 6, 8, 10, 12 hour interruption levels), data from row 3. Cells look like `00--01, 12--13` (24-hour clock, start--end; `23--24` ends at midnight). At level N a feeder has exactly N one-hour slots.
- The title says the schedule is applied according to generation shortfall or frequency issues, so it is a **playbook**. Every feeder gets identical hours at each level, the files never say which level applies, and there is no category column. Feeders rotate in cohorts (12 distinct patterns at 2 h, 2 at 12 h). Use: **scenario view** ("if level N is active, who is dark now"). Never use it for inequity analysis.
- Codes lose leading zeros (4 to 6 digits). Normalise to 6-digit zero-padded text. Example: `89201` → `089201`, feeder "BHARAKHAU 1", grid "UNIVERSTY" (typo), Islamabad. Names have typos; **the code is the join key**.
- Known bad data (flag, do not fix): 3 feeders coded `NOT ALLOTED`; code 59704 twice in Chakwal (one is a FESCO feeder); one code appears in two circles; Kohala has 11 slots in its 10-hour column.
- To check: the share of feeders off per hour at the 10-hour level is uneven (about 25% to 50%), unlike the other levels. Report whether this is design or a data error.
- Change detection by `Last-Modified` + SHA-256. The Islamabad file was Last-Modified **14 Jan 2026** despite a "Sep-2026" page label. Files may be overwritten in place, so snapshot every change.

## 2. IESCO press releases
- English PDFs have selectable text. The Urdu text layer is scrambled, so Urdu is ignored.
- Grammar: a time range ("from 08:00 AM to 02:00 PM") applies to the feeder names that follow it, until the next time range. A circle label ("Islamabad Circle:") persists until the next circle label. The time range may come before or after the circle label. One release can span several days ("On Sunday, October 04, 2026, ..."). "GSO Circle" is not one of the six XLSX circles: keep it as its own value.
- **Release No. 02, Oct 3: 29 feeder-windows.** Islamabad Circle 08:00–14:00 ×8 (Islamabad Club-1, Islamabad Club-2, Mehfooz Shaheed / Shahzad Town, Filtration Plant, Pindorian, Scheme-2, Orchard Scheme, CDA Pump); Islamabad Circle 07:00–14:00 ×1 (Sudhran); GSO Circle 06:00–09:00 ×20.
- **Release No. 02, Oct 4: 45 feeder-windows.** Same 8 Islamabad feeders 08:00–14:00; Islamabad Circle 07:00–14:00 ×13 (Chatta Bakhtawar, Tramari, CM Pak Zong, Kurri, Rehara, Park Enclave-1, Kund Rajgan, Scheme-1, King Hammad, PHA-1, Isolation Hospital, IT Park, ISI); Attock Circle 07:00–14:00 ×4 (Lala Zar, POF, Munirabad, Karnel Sher Khan); GSO Circle 06:00–09:00 ×20.
- **Release No. 03, Oct 5: 15 feeder-windows.** Rawalpindi City Circle 07:00–14:00 ×2 (Qadeer Road, KRL); Rawalpindi City Circle 08:00–12:00 ×5 (Millatabad, Dhoke Chaudhrian, Peshawar Road, Askari-XI, Coblane); Islamabad Circle 08:00–12:00 ×8 (same 8 as Oct 3).
- Matching to XLSX feeders (Oct 5 names): 8 confident, 3 plausible (Dhoke Chaudhrian, Coblane, Peshawar Road), 4 none (Qadeer Road, KRL, Filtration Plant, CDA Pump). **Alias table with human review is mandatory.**

## 3. K-Electric
- **Feeder list PDF:** 22 pages; columns S.No., Feeder Name, IBC, ATC(OI) %, Final Category. **623 rows**: Medium 133, High 163, Very High 327. 2 rows have no ATC (Kaghzi Bazaar, New Sabzi Mandi).
- **Schedule PDF:** 12 pages; columns Feeder, Grid, four cycles `HHMM~HHMM` (a cycle can wrap midnight, e.g. `2235~0205`). **618 rows**. Every feeder has 4 cycles totalling exactly **6 h (125 feeders) or 12 h (493 feeders)**.
- **Join** list to schedule on a normalised name (uppercase, strip non-alphanumerics): 616 match, plus 1 after fixing a truncated name (`NAVY HOUSING SCHEME (Ex. PAKISTAN NAVY HOUSING SCHEM`) = **617 joined**. 6 listed feeders have no schedule row (Andaleeb CHS, Behavioral Sciences, CBR Income Tax Building, Miskeenabad, Muhammad Farooq +, PNSC S/S). `ARMY HOUSE` (grid DEFENCE) is in the schedule but not the list.
- **Category vs hours:** Medium = 6 h (125 of the 127 Medium feeders that have a schedule row); High and Very High = 12 h (all 490). Exceptions: `ABDUL GHANI +` and `KHYABAN-E-HAFIZ` (Medium, 12 h). High and Very High have identical hours.
- Category is not a pure function of loss %: Medium goes up to 42.5% and High starts at 26.9%. In that band there are 112 Medium and 89 High feeders. This is an observation, not a finding of unfairness.
- **Per-IBC oracles** (listed feeders, share at 12 h): Orangi - I 41, 97.6%; Korangi 39, 61.5%; Clifton 11, 100%; F.B. Area 4, 0%. 30 IBC areas, 53 grids. Keep **both** taxonomies (IBC from the list, grid from the schedule) in `dim_feeder`.
- `IBC - Uthal` = the same 9 feeders as grid `HUB CHOWKI` (Balochistan, Hub/Uthal). Sindh tables do not cover it, so census coverage is "out of scope". Do not force a join.
- `pdftotext -layout` sometimes glues two rows onto one line (e.g. `...2205IQBAL CENTER ELENDER RD ...`). Parse robustly and validate that each feeder sums to 6 or 12 h.
- **No denominator:** only load-shed feeders are listed. Shares are among listed feeders and must be labelled so. The schedule is tentative (K-Electric disclaimer). The files are dated 5 Aug 2026 and may predate the 11 Sept directive: store `effective_from` and flag newer files.

## 4. PBS Census 2023
- **Urban 33 (population) / 34 (housing):** district > tehsil/taluka/sub-division > municipal body > charge > circle. **Join on the hierarchical key, never row order** (only about a third of rows line up). Merges completely: Islamabad 90 rows, Punjab 5,534 rows. Below municipality the units are numbered ("CHARGE NO 03"), so they cannot be name-matched to feeders. Islamabad: **12 charges, 75 circles**. The four Punjab IESCO districts (Attock, Rawalpindi, Jhelum, Chakwal) have **39 urban bodies**.
- **Rural 31 (population, 23 numeric cols) / 32 (housing, 11 numeric cols):** district > tehsil > QH > PC (aggregate) > mauza (named, hadbast number like `0000227` or `00S-226`). Parse lines by peeling numeric tokens from the right; `-` = zero/empty. **2,578 localities** in the five IESCO districts (Attock 435, Chakwal 419, Islamabad 129, Jhelum 525, Rawalpindi 1,070); 31 and 32 join 1:1. **2,357** have 20 or more housing units (6.8 M people). About 10% of names repeat: disambiguate by district.
- Indicator spread (2,357 localities): literacy 17% to 99.9%; electricity access 1% to 100% (24 localities under 70%); pacca housing 2% to 100%; degree share 0.2% to 39.8%.
- **Sindh:** Karachi has **28 named sub-divisions**. Oracles: Orangi pop 596,919, literacy 60.8%; Gulshan-e-Iqbal 973,314, 89.2%; Mauripur 217,930, 52.8%. Counts of 1,000,000 or more print as `#######`, so use only unaffected columns. The 30 K-Electric IBC areas need a manual IBC-to-sub-division crosswalk seed, reviewed by the owner.
- **Committed derived copy (owner decision 2026-10-12):** the census source files stay hand-downloaded and uncommitted, but the *parsed* tables 31-34, trimmed to the columns dbt, the GE suites and provenance use (no gas), are committed in `census/` (`roshni census-freeze`; 2.6 MB, manifest with rows and source SHA-256s) so the daily job can build. Urban 33/34: 10,352 / 10,342 rows; rural 31/32: 33,285 / 33,285.
- Wealth proxies: literacy, degree-and-above share, pacca housing share, household size. **Not** gas connection (many towns have no gas network). Income is published by province only, so make no district-level income claims. AJK has no PBS tables.

## 5. Feeder-to-locality name matching (IESCO excl. AJK, 980 feeders)
110 exact (11%); 199 fuzzy 85+ (20%). By circle (fuzzy 85+): Chakwal 53%, Attock 34%, Jhelum 32%, Rawalpindi 11%, Islamabad 8%. The 150 sector-style feeders (F-11/3, H8 Grid, ...) match almost nothing. Some fuzzy hits are wrong (Mangtal→Mangal, Jhanda→Jhandial), so every non-exact match needs review.

## 6. Live discovery (2026-10-06, Phase 1)
- robots.txt: `iesco.com.pk` empty Disallow; `ke.com.pk` disallows only `/wp-admin/`; `www.dawn.com` disallows print/archive/search/some author pages (`/news/...` allowed).
- IESCO load-shedding page: a table of circle label, date label ("Sep-2026"), link. 6 rows; all files under `.../January2026/`, Last-Modified 14 Jan 2026, no ETag. Fetched bytes = local copies (SHA-256 equal).
- IESCO press-release page, "Power Shutdown" tab (`#power-desktop`): 65 rows from 16 Jul 2026 to 6 Oct 2026, roughly daily, each with "English" and "Urdu" links. Titles vary ("Temporary Power Shutdown Schedule ... Development Projects on 6th October 2026", "Due to System Maintenance, IESCO has Issued a Schedule for Power Shut Down on ..."). A release for 6 Oct exists beyond the local files.
- K-Electric `/load-shed-schedule/`: links `2026/07/Feeders-List.pdf`, `2026/07/Non-Payers-List.pdf` (excluded), `2026/08/LSMnew-PDF-Aug-5th.pdf` (the schedule). Schedule: 153,736 bytes, Last-Modified 5 Aug 2026, ETag present; equal to the local copy, so **not republished** after the 11 Sept directive as of 2026-10-06. The page is slow without compression; with gzip it is ~50 KB.
- Dawn 2029158: "PM Shehbaz orders no more than two hours of loadshedding across country", datePublished 2026-09-11T23:07+05:00. Policy date confirmed.

## 7. Access check
2026-10-06: a GitHub Actions runner got HTTP 200 for the IESCO load-shedding page, the Islamabad XLSX, the K-Electric load-shed page and `Feeders-List.pdf`. Re-check only if fetches fail.

## 8. Parser results vs this audit (Phase 2, 2026-10-06)
Golden tests: `tests/test_golden.py` (need `data-sources/`; skipped in CI). Poppler 25.03.0 (Docker image).

**Matches exactly:** IESCO counts (1,105 / 1,103 / 980), anomalies, cohort patterns (12 at 2 h, 2 at 12 h), `089201`; press releases No. 02 (29 + 45) and No. 03 (15) incl. circles, times, names; K-Electric list (623, 133/163/327, 2 without ATC, 30 IBCs), schedule (618; 125 × 6 h, 493 × 12 h), join (616 exact, the 6 missing + truncated NAVY, ARMY HOUSE), Medium-12 h exceptions, all four per-IBC oracles, Uthal = Hub Chowki (9); PBS urban Islamabad 90 and Punjab 5,534 rows joined completely on the key, 12 charges / 75 circles, 39 IESCO urban bodies; Karachi 28 sub-divisions and the Orangi / Gulshan-e-Iqbal / Mauripur oracles; rural literacy 17–99.9 %, degree share max 39.8 %, 6.8 M people.

**Explained differences:**
- *"One code appears in two circles"* is the `NOT ALLOTED` placeholder (Islamabad and Rawalpindi), not a real code.
- *53 grids*: the schedule has 54; `DEFENCE` holds only `ARMY HOUSE`, which is not in the list → 53 among listed feeders.
- *Medium = 6 h for 125*: 124 on exact names + the truncated NAVY feeder (Medium, 6 h) once resolved.
- *Glued rows* (`...2205IQBAL CENTER`): not produced by poppler 25.03; the parser still splits them if they appear.
- *Rural localities 2,581 vs 2,578* (Chakwal 420 vs 419, Rawalpindi 1,072 vs 1,070): the parser also keeps mauzas printed without a hadbast number (e.g. KALIYAL/KOTLA, LOTERI (REHMAN ABAD)); they look genuine. Hence ≥20 housing units = 2,360 vs 2,357. **Owner approved 2026-10-09: keep them.**
- *Rural `-` cells*: stored as 0 (census convention). The audit treated `-` as missing, which is why its minimums were electricity 1 %, pacca 2 %, degree 0.2 % and "24 localities under 70 % electricity" (27 with `-` = 0; 3 localities print `-` for electricity). **Owner approved 2026-10-09: keep `-` = 0.**
- *IESCO 10-hour level*: the share off per hour is exactly ~25 % or ~50 % in every circle (11 cohort patterns) while every other level is flat (±1 pt). 10 does not divide 24, so a cohort rotation cannot be uniform: **design, not a data error**.

**Additional facts:**
- Press releases come in two formats: development notices ("Temporary Power Shutdown Schedule…") and maintenance notices ("POWER SUSPENSION SCHEDULES FOR …", `On 14th September 2026`, `Circle,`, `from 7 am to 11 am`). All 65 snapshotted releases parse: 1,853 feeder-windows; 166 fragments quarantined (transmission-asset descriptions such as "132KV circuit Breaker … controlling … ckt", and "surrounding areas will remain closed"). Short GSO asset names (e.g. "132kv AWC HMC Taxila") are kept and flagged `transmission_asset`. One release (25 Sep) names the circle after the list ("… feeders and adjoining areas in Islamabad Circle."): flagged `circle_after_list`.
- Circle labels in releases include `Rawalpindi Cantt` and `Rawalpindi City` separately (the XLSX has one Rawalpindi circle), plus `GSO`.
- PBS Sindh PDFs: names wrap and numbers sometimes sit on their own line. Rows are accepted only when name and a full set of numbers share a line; 73 (T33) / 112 (T34) lines quarantined. **Sindh is complete at district (30) and sub-division/taluka (130) level**, which is what the IBC crosswalk uses; below that, charges/circles under a quarantined body name are flagged `parent_body_unresolved` and do not join 33↔34. Table 34 (Sindh PDF) prints household size rounded to integers.
- Household size reaches ~98 in tiny rural/urban units with 1–2 housing units (published values, likely institutional).

## 9. Entity resolution (Phase 4, 2026-10-10)
Candidates come from `roshni resolve` into `dbt/seeds/review_*.csv`; see `docs/review-guide.md`.

**Feeder → locality** (IESCO excl. AJK, 977 feeders after quarantine; candidates: rural mauzas + urban bodies of the circle's district; `token_set_ratio` ≥ 85, top 3):
| Circle | Feeders | auto_exact | suggested (best ≥ 85) | no candidate |
|---|---:|---:|---:|---:|
| Attock | 164 | 30 | 28 | 106 |
| Chakwal | 101 | 25 | 27 | 49 |
| Islamabad | 271 | 6 | 13 | 252 |
| Jhelum | 90 | 5 | 17 | 68 |
| Rawalpindi | 350 | 15 | 36 | 299 |
Fuzzy ≥ 85 (auto + suggested) = 202, close to the audit's 199; shares by circle 35 / 51 / 7 / 24 / 15 % vs audit 34 / 53 / 8 / 32 / 11 %. Identical normalised names = 86 (81 unique in district → auto_exact) vs the audit's "110 exact"; the audit's normalisation is not recorded, so the difference cannot be attributed. Sector-style Islamabad feeders still match almost nothing, as the audit found.

**Press-release names → IESCO feeders** (626 printed names; GSO's 241 are out of scope, no XLSX list): 126 auto_exact, 168 suggested, 91 no candidate. Release No. 03 against audit 7.2: 7 of the 8 confident names auto-match (Millatabad → MILATABAD 94.7 awaits review), the 3 plausible ones are suggested (Dhoke Chaudhrian → DHOKE CHODRIAN 86.7, Coblane → COBE LINE 75, Peshawar Road → PSR ROAD 76.2), KRL / Filtration Plant / CDA Pump have no candidate, and Qadeer Road gets a wrong suggestion (HAIDER ROAD 81.8) to reject.

**IBC → sub-division draft:** 16 IBCs have a name-similar sub-division (e.g. Orangi - I/II → ORANGI, Layari - I/II → LYARI, Liaqatabad → LIAQUATABAD), 13 have none (Bahadurabad, Bin Qasim, Clifton, Defence, F.B. Area, Gadap, Gulshan, Johar - I/II, KIMZ, Malir, Surjani, Tipu Sultan), Uthal is out of scope. Nothing counts until the owner accepts it.

**Boundaries:** see `docs/boundary-research.md`; none adopted.

**After the delegated review (Claude, 2026-10-10):**
| Task / group | In scope | Matched | Share |
|---|---:|---:|---:|
| Feeder → locality: Attock / Chakwal / Islamabad / Jhelum / Rawalpindi | 164 / 101 / 271 / 90 / 350 | 47 / 44 / 11 / 17 / 28 | 28.7 / 43.6 / 4.1 / 18.9 / 8.0 % |
| Press names → feeder: Attock / Chakwal / Islamabad / Jhelum / Rwp Cantt / Rwp City | 66 / 27 / 91 / 71 / 70 / 60 | 42 / 23 / 60 / 49 / 51 / 40 | 63.6 / 85.2 / 65.9 / 69.0 / 72.9 / 66.7 % |
| IBC → sub-division | 29 | 15 | 51.7 % |
Planned-shutdown windows: 1,006 matched to a feeder, 512 unmatched, 335 out of scope (GSO). Release No. 03: 11 of 15 matched (audit: 8 confident + 3 plausible); Qadeer Road, KRL, Filtration Plant, CDA Pump unmatched (audit: no match).

## 10. National context sources (owner approval 2026-10-13, first snapshot same day)

**NEPRA Performance Evaluation Reports, distribution companies** (`nepra_per_distribution`). Listing page `https://nepra.org.pk/publications/Performance%20Reports.php`; robots.txt `Allow: /`. First snapshot: 14 annual PDFs fetched (1.0–7.9 MB each; FY2024-25 back to the combined DISCOs + K-Electric reports of 2013-14 and earlier). **FY2023-24 (`PER DISCOs 2023-24.pdf`) returns HTTP 404 from NEPRA's own link**: a known gap, not guessed from another URL.
- FY2024-25 (`PER 2024-25 Distribution Companies.pdf`, poppler): section 2.6 "Load Shedding (Hours)", Table 10 "Average Load Shedding (Hours) daily", reported figures per company: PESCO 5.5, IESCO 0, FESCO 0.02, GEPCO 0, LESCO 0.06, MEPCO 1.2, QESCO 10.25, SEPCO 1.4, HESCO 8, K-Electric 5.2. **Anomaly:** Figure 13 next to the table prints LESCO as 0.1 (rounded); the table value is the one used.
- NEPRA's own caveat in the same section: monitoring shows actual load shedding above 8–10 h/day in PESCO, QESCO, SEPCO and HESCO (under-reporting), and those companies plus K-Electric still shed by AT&C loss, contrary to the Performance Standards.
- **Parsed (N2, 2026-10-14):** 7 reports x 50 values = 350 rows, 4 reports quarantined (older layout, no section 3.6 table); 130 company-years (10 companies: PESCO, IESCO, GEPCO, FESCO, LESCO, MEPCO, QESCO, SEPCO, HESCO, K-Electric; FY2012-13 to FY2024-25). Restatements agree within 0.01 h except **K-Electric FY2021-22: 3.4 (FY2021-22, FY2022-23 reports) vs 2.6 (FY2024-25)**, flagged. FY2024-25's own section 3.6 prints LESCO 2024-25 as 0.1 (section 2.6 Table 10: 0.06); the section 3.6 value is used. **GEPCO FY2017-18 = 11** is printed so in four reports (an outlier next to 0.5 the year after); shown as reported. Golden values: `src/roshni/parsers/test_nepra_per.py` (trimmed fixtures in `tests/fixtures/nepra_per/`).

**News feeds** (`news_dawn` `https://www.dawn.com/feeds/home`, `news_brecorder` `https://www.brecorder.com/feeds/latest-news`, `news_tribune` `https://tribune.com.pk/feed/home`, `news_app` `https://www.app.com.pk/feed/`). robots.txt allows each path. First (untrimmed, local-only, since deleted) snapshot 2026-10-13: 431 KB / 265 KB / 421 KB / 19 KB. From 2026-10-14 feeds are stored trimmed (DECISIONS N3): first trimmed snapshot 78–84 bytes each, 0 matching items out of 28 / 30 / 73 / 10. Only headline, outlet, publication date and link are used.

**NEPRA order on K-Electric, 2026-08-31** (`nepra_ke_order`; `M&E/Decisions/2026/08 Aug/LAD-01 ORDER UNDER SECTION 27C OF NEPRA ACT 1997 IN MATER OF K-ELECTRIC 31-08-2026 18150.PDF`, 524,268 bytes, fetched 2026-10-14). Paragraph 18 summary table: Very High Loss 316 feeders / 1,177,900 consumers / 69% AT&C / schedule 10:00; High Loss 171 / 707,365 / 42% / 10:00; Medium Loss 133 / 484,637 / 31% / 6:00; total 620 / 2,369,902. Paragraph 19 bands (feeders): Medium: up to 6:00 42, 6:00–8:00+ 91; High: up to 10:00 31, 10–12 109, 12–14 29, above 14:00 2; Very High: up to 10:00 28, 10–12 109, 12–14 128, 14:00–18:00+ 51. All bands add up to their totals. No data period is stated. The order's prose has OCR-like noise ("averagjgi4 hours"); only the tables are parsed.

## 11. IESCO maintenance schedules (owner approval 2026-10-18, first snapshot same day)

**Source** `iesco_maintenance_xlsx`: listing `https://iesco.com.pk/maintenance-schedule` (robots.txt `User-agent: * / Disallow:` = everything allowed), same table layout as the load-shedding page: one row per circle with a date label and an `.xlsx` link under `storage/maintenance-schedules/<Month><Year>/`. First snapshot 2026-10-18: 8 workbooks labelled "01 To 31 October, 2026": Islamabad 622,267 B, Rawalpindi City 587,972, Rawalpindi Cantt 665,171, Attock 557,398, Jhelum 418,353, Chakwal 392,018, GSO 276,881, Shutdown For Construction Work 30,768. The owner's hand-downloaded `islamabad sep 2026 load management iesco.xlsx` is the *load-shedding* file, byte-identical to `iesco-islamabad-sep26.xlsx` (SHA-256 `f0336196…`), not this source.

**Layout (varies by circle):** header in row 1 (Islamabad, Chakwal, construction) or row 2 under a title row (Attock, Jhelum, Rawalpindi, GSO); columns found by header words. Islamabad has a merged `TIME` header over a `From`/`To` sub-header. Dates are `DD.MM.YYYY` text, `DD-MM-YYYY`, `YYYY-MM-DD` or Excel dates; Excel dates often carry a time (07:00/08:00/11:00/12:00) that differs from the printed From time; flagged `date_cell_time_HHMM`, the From/To columns are used. The construction sheet lists several dates in one cell for the same window; one window per listed date (`multi_date_cell`). GSO uses merged cells (filled from the merge's top-left cell, as Excel shows them). Only the first sheet is read; the `OFF ON` sheets restate the same windows as events.

**Parsed 2026-10-18 (all 8 files):** 18,761 rows, 185 quarantined (construction 36: 31 without feeder, 5 unreadable dates; GSO 121: unreadable dates/times; Jhelum 23 and Chakwal 4: missing end time; Islamabad 1: no date). After keeping one row per window: 18,737 windows, about 92,500 feeder-hours, 16,227 linked to an IESCO feeder by code. Dates run 2026-09-28 (construction) and 2026-10-15 to 2027-03-30, well past the "October" in the label: shown as printed, with the note that files cover the dates they print. Islamabad circle: 3,310 windows, all 09:00–14:00, 16,550 feeder-hours, 430 distinct feeder codes (270 of them in the load-shedding workbook); purposes Annual Maintenance 2,259, Construction/Development Work 599, GSC Construction/Development Work 328, Bus Coupler Maintenance 123, Power T/F Maintenance 1. 25 Islamabad rows print the circle as `ISLAMABAD/PESCO` (`circle_shared`).

**Overlap:** 1,174 windows appear in both the GSO file and a circle's file (same feeder code, date and times). Each file's figures stay as printed; `repeats_circle_window` marks the GSO copy, and totals across rows count each window once.

## 12. IESCO Facebook notices (owner, 2026-10-18): hand-recorded only

`facebook.com/robots.txt`: `User-agent: * / Disallow: /`, and it states that automated collection is prohibited without written permission. So nothing is fetched. Notices are read by a person and recorded in `dbt/seeds/iesco_social_notices.csv` (link, date, kind, circle, areas, window, a summary in our words); `src/roshni/export/test_notices.py` enforces the rules. The seed starts empty.
