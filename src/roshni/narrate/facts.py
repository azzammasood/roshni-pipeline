"""Facts: every number a report may state, each traced to the SQL query that produced it."""

from dataclasses import dataclass

import duckdb


@dataclass(frozen=True)
class Fact:
    id: str
    label: str  # plain-English meaning
    value: object  # number or text
    unit: str  # count, %, n, rho, date, text
    query_id: str

    def rendered(self) -> str:
        v = self.value
        if isinstance(v, float):
            return f"{v:.3f}".rstrip("0").rstrip(".") if self.unit == "rho" else f"{v:g}"
        return str(v)


# Named queries. Each returns exactly one row; its columns become facts named <prefix>_<column>.
QUERIES: dict[str, str] = {
    "coverage": """
        select count(*) as listed_feeders,
               sum(case when has_schedule then 1 else 0 end) as scheduled_feeders,
               count(distinct ibc) as ibcs
        from dim_feeder where source = 'kelectric' and in_feeder_list""",
    "hours_split": """
        select sum(case when scheduled_hours_per_day = 12 then 1 else 0 end) as feeders_12h,
               sum(case when scheduled_hours_per_day = 6 then 1 else 0 end) as feeders_6h,
               round(100.0 * sum(case when scheduled_hours_per_day = 12 then 1 else 0 end)
                     / count(*), 1) as share_12h_pct
        from mart_ke_feeder_hours""",
    "effective": """
        select cast(min(effective_from) as varchar) as schedule_effective_from
        from fct_schedule_window where source = 'kelectric'""",
    "ibc_highest": """
        select ibc as name, share_12h_pct, scheduled_feeders as n
        from mart_ke_ibc_equity where scheduled_feeders >= 10
        order by share_12h_pct desc, scheduled_feeders desc, ibc limit 1""",
    "ibc_lowest": """
        select ibc as name, share_12h_pct, scheduled_feeders as n
        from mart_ke_ibc_equity where scheduled_feeders >= 10
        order by share_12h_pct asc, scheduled_feeders desc, ibc limit 1""",
    "ibc_all_12h": """
        select count(*) as ibcs from mart_ke_ibc_equity
        where scheduled_feeders > 0 and share_12h_pct = 100""",
    "medium_12h": """
        select feeders from rpt_ke_anomalies where rule = 'medium_category_at_12h'""",
    "overlap": """
        select max(case when rule = 'medium_in_overlap_band' then feeders end) as medium,
               max(case when rule = 'high_in_overlap_band' then feeders end) as high
        from rpt_ke_anomalies""",
    "rho_loss_hours": """
        select spearman_rho as rho, n from rpt_spearman
        where unit = 'feeder' and x_name = 'atc_loss_pct'""",
    "rho_literacy": """
        select spearman_rho as rho, n from rpt_spearman
        where unit = 'subdivision' and x_name = 'literacy_pct'""",
    "rho_degree": """
        select spearman_rho as rho, n from rpt_spearman
        where unit = 'subdivision' and x_name = 'degree_share_pct'""",
    "crosswalk": """
        select count(*) as accepted_ibcs, count(distinct subdivision_area_id) as subdivisions
        from ke_ibc_subdivision where crosswalk_status = 'accepted'""",
}
# Every fact id -> (plain-English meaning shown to the writer, unit kind used by validation).
# Unit kinds: count, %, n (sample size), rho, date, text.
SL = "scheduled listed feeders"
MEANINGS: dict[str, tuple[str, str]] = {
    "coverage_listed_feeders": ("number of feeders K-Electric lists as under load shed", "count"),
    "coverage_scheduled_feeders": ("number of those listed feeders that have a schedule row",
                                   "count"),
    "coverage_ibcs": ("number of K-Electric IBC areas the listed feeders belong to", "count"),
    "hours_split_feeders_12h": (f"number of {SL} scheduled 12 hours a day", "count"),
    "hours_split_feeders_6h": (f"number of {SL} scheduled 6 hours a day", "count"),
    "hours_split_share_12h_pct": (f"percentage of {SL} that are scheduled 12 hours a day", "%"),
    "effective_schedule_effective_from": ("date from which the K-Electric schedule applies",
                                          "date"),
    "ibc_highest_name": ("IBC area (at least 10 scheduled feeders) with the highest percentage of "
                         "its scheduled listed feeders at 12 hours", "text"),
    "ibc_highest_share_12h_pct": (f"percentage of that IBC area's {SL} at 12 hours", "%"),
    "ibc_highest_n": (f"number of {SL} in that IBC area (its n)", "n"),
    "ibc_lowest_name": ("IBC area (at least 10 scheduled feeders) with the lowest percentage of "
                        "its scheduled listed feeders at 12 hours", "text"),
    "ibc_lowest_share_12h_pct": (f"percentage of that IBC area's {SL} at 12 hours", "%"),
    "ibc_lowest_n": (f"number of {SL} in that IBC area (its n)", "n"),
    "ibc_all_12h": ("number of IBC areas where every scheduled listed feeder is at 12 hours",
                    "count"),
    "medium_12h": ("number of Medium loss-category feeders scheduled 12 hours a day (Medium is "
                   "otherwise 6 hours)", "count"),
    "overlap_medium": ("number of scheduled Medium-category feeders whose published loss lies in "
                       "the loss range where the Medium and High categories overlap", "count"),
    "overlap_high": ("number of scheduled High-category feeders whose published loss lies in the "
                     "loss range where the Medium and High categories overlap", "count"),
    "rho_loss_hours_rho": ("Spearman rank correlation across listed feeders between published "
                           "AT&C loss percentage and scheduled hours per day", "rho"),
    "rho_loss_hours_n": ("number of feeders in that correlation (its n)", "n"),
    "rho_literacy_rho": ("Spearman rank correlation across census sub-divisions between the "
                         "percentage of listed feeders at 12 hours and the literacy rate", "rho"),
    "rho_literacy_n": ("number of census sub-divisions in that correlation (its n)", "n"),
    "rho_degree_rho": ("Spearman rank correlation across census sub-divisions between the "
                       "percentage of listed feeders at 12 hours and the share of people with a "
                       "degree", "rho"),
    "rho_degree_n": ("number of census sub-divisions in that correlation (its n)", "n"),
    "crosswalk_accepted_ibcs": ("number of IBC areas matched by name to a census sub-division",
                                "count"),
    "crosswalk_subdivisions": ("number of census sub-divisions those IBC areas map to", "count"),
}  # fmt: skip


def collect(con: duckdb.DuckDBPyConnection) -> list[Fact]:
    facts: list[Fact] = []
    for qid, sql in QUERIES.items():
        cur = con.execute(sql)
        cols = [d[0] for d in cur.description]
        row = cur.fetchone()
        if row is None:
            continue
        for col, val in zip(cols, row, strict=True):
            if val is None:
                continue
            if isinstance(val, int | float) and not isinstance(val, bool):
                val = int(val) if float(val).is_integer() and col != "rho" else val
            fid = qid if col in ("feeders", "ibcs") and len(cols) == 1 else f"{qid}_{col}"
            if fid not in MEANINGS:
                raise KeyError(f"fact {fid!r} has no meaning in MEANINGS")
            meaning, unit = MEANINGS[fid]
            facts.append(Fact(fid, meaning, val, unit, qid))
    return facts
