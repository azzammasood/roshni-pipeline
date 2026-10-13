"""Candidate generation from the warehouse (DuckDB) into review seeds.

Statuses: auto_exact (identical normalised name, unique in its group: auto-accepted),
suggested (everything else; needs a decision), no_candidate (nothing above the cutoff),
out_of_scope (no comparable census or feeder data). Press-release suggestions are then decided
by the written rules in autoreview.py where they apply; the rest wait for a delegated review.
"""

import re
from collections import Counter

import duckdb
from rapidfuzz import fuzz

from roshni.resolve.names import Candidate, best_candidates, normalise

CIRCLE_DISTRICT = {
    "islamabad": "ISLAMABAD DISTRICT",
    "rawalpindi": "RAWALPINDI DISTRICT",
    "attock": "ATTOCK DISTRICT",
    "jhelum": "JHELUM DISTRICT",
    "chakwal": "CHAKWAL DISTRICT",
}
# Circle labels printed in press releases -> XLSX circle. GSO has no XLSX workbook.
PRESS_CIRCLE = {
    "Islamabad": "islamabad",
    "Rawalpindi City": "rawalpindi",
    "Rawalpindi Cantt": "rawalpindi",
    "Attock": "attock",
    "Jhelum": "jhelum",
    "Chakwal": "chakwal",
}
KARACHI_DISTRICTS = (
    "KARACHI CENTRAL DISTRICT", "KARACHI EAST DISTRICT", "KARACHI SOUTH DISTRICT",
    "KARACHI WEST DISTRICT", "KEAMARI DISTRICT", "KORANGI DISTRICT", "MALIR DISTRICT",
)  # fmt: skip
REVIEW_COLUMNS = [
    "subject_id", "subject_name", "subject_group", "candidate_id", "candidate_name",
    "rank", "score", "method", "status", "decision", "note",
]  # fmt: skip


def _row(sid: str, name: str, group: str, status: str, note: str = "", **cand) -> dict:
    base = dict(candidate_id="", candidate_name="", rank=0, score=0, method="")
    return dict(base | cand, subject_id=sid, subject_name=name, subject_group=group,
                status=status, note=note)  # fmt: skip


def _cand_rows(
    sid: str,
    name: str,
    group: str,
    cands: list[Candidate],
    pool_counts: Counter,
    keep_numbers: bool = False,
    auto: bool = True,
) -> list[dict]:
    if not cands:
        return [_row(sid, name, group, "no_candidate")]
    n_exact = sum(c.exact for c in cands)
    out = []
    for i, c in enumerate(cands, start=1):
        unique = pool_counts[normalise(c.candidate_name, keep_numbers)] == 1
        status = "auto_exact" if auto and c.exact and unique and n_exact == 1 else "suggested"
        out.append(
            _row(
                sid,
                name,
                group,
                status,
                candidate_id=c.candidate_id,
                candidate_name=c.candidate_name,
                rank=i,
                score=c.score,
                method="exact" if c.exact else "fuzzy",
            )  # fmt: skip
        )
    return out


def feeder_locality(con: duckdb.DuckDBPyConnection, min_score=85.0, limit=3) -> list[dict]:
    """IESCO feeders (not AJK) -> census localities (rural mauzas and urban bodies) by district.

    Scored with token_set_ratio (robust to extra words); "exact" still means identical
    normalised names, with numbers dropped ("BHARAKHAU 1" names the village BHARAKHAU).
    """
    feeders = con.sql(
        "select feeder_id, feeder_name, circle from dim_feeder where source = 'iesco' "
        "order by feeder_id"
    ).fetchall()
    areas = con.sql(
        "select area_id, area_name, district from dim_area_indicators "
        "where (area_type = 'rural' and area_level = 'mauza') "
        "or (area_type = 'urban' and area_level = 'body')"
    ).fetchall()
    rows: list[dict] = []
    for fid, fname, circle in feeders:
        if circle not in CIRCLE_DISTRICT:
            rows.append(_row(fid, fname, circle, "out_of_scope", "no PBS tables for AJK"))
            continue
        pool = {a: n for a, n, d in areas if d == CIRCLE_DISTRICT[circle]}
        counts = Counter(normalise(n) for n in pool.values())
        cands = best_candidates(fname, pool, min_score, limit, scorer=fuzz.token_set_ratio)
        rows += _cand_rows(fid, fname, circle, cands, counts)
    return rows


def press_feeders(con: duckdb.DuckDBPyConnection, min_score=70.0, limit=3) -> list[dict]:
    """Feeder names printed in press releases -> IESCO feeders in the mapped circle.

    Numbers are kept ("Club-1" vs "Club-2"). GSO lists have no XLSX circle: out_of_scope.
    """
    names = con.sql(
        "select circle_as_printed, feeder_name_as_printed, count(*) from fct_planned_shutdown "
        "where flags not like '%transmission_asset%' group by 1, 2 order by 1, 2"
    ).fetchall()
    feeders = con.sql(
        "select feeder_id, feeder_name, circle from dim_feeder where source = 'iesco'"
    ).fetchall()
    rows: list[dict] = []
    for circle_p, name, n in names:
        sid = f"{circle_p}:{name}"  # as printed, so SQL can join back without normalising
        circle = PRESS_CIRCLE.get(circle_p)
        if circle is None:
            note = f"circle {circle_p!r} has no XLSX feeder list ({n} windows)"
            rows.append(_row(sid, name, circle_p, "out_of_scope", note))
            continue
        pool = {f: fn for f, fn, c in feeders if c == circle}
        counts = Counter(normalise(x, keep_numbers=True) for x in pool.values())
        cands = best_candidates(name, pool, min_score, limit, keep_numbers=True)
        rows += _cand_rows(sid, name, circle_p, cands, counts, keep_numbers=True)
    return rows


def ibc_subdivision(con: duckdb.DuckDBPyConnection, min_score=70.0, limit=2) -> list[dict]:
    """DRAFT crosswalk: K-Electric IBC areas -> Karachi census sub-divisions, by name only.

    Never auto-accepted: an IBC is a utility billing area whose extent need not match a
    sub-division. Every row needs an owner decision.
    """
    ibcs = [r[0] for r in con.sql(
        "select distinct ibc from dim_feeder where source = 'kelectric' and ibc is not null"
    ).fetchall()]  # fmt: skip
    in_list = ", ".join(f"'{d}'" for d in KARACHI_DISTRICTS)
    subs = dict(con.sql(
        "select area_id, area_name from dim_area_indicators where province = 'sindh' "
        f"and area_level = 'tehsil' and area_name like '%SUB-DIVISION' and district in ({in_list})"
    ).fetchall())  # fmt: skip
    rows: list[dict] = []
    for ibc in sorted(ibcs):
        core = re.sub(r"^IBC\s*-\s*", "", ibc)
        if core == "Uthal":
            note = "Hub/Uthal, Balochistan: not covered by Sindh tables"
            rows.append(_row(ibc, core, "kelectric_ibc", "out_of_scope", note))
            continue
        cands = best_candidates(core, subs, min_score, limit)
        rows += _cand_rows(ibc, core, "kelectric_ibc", cands, Counter(), auto=False)
    return rows
