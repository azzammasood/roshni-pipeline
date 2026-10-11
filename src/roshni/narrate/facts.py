"""Facts: every number a report may state, each traced to the SQL query that produced it."""

from dataclasses import dataclass

import duckdb


@dataclass(frozen=True)
class Fact:
    id: str
    label: str
    value: object  # number or text
    unit: str  # "feeders", "%", "hours", "rho", "date", "text", ...
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
UNITS = {
    "listed_feeders": "feeders", "scheduled_feeders": "feeders", "ibcs": "IBC areas",
    "feeders_12h": "feeders", "feeders_6h": "feeders", "share_12h_pct": "%",
    "schedule_effective_from": "date", "name": "text", "n": "feeders", "feeders": "feeders",
    "medium": "feeders", "high": "feeders", "rho": "rho", "accepted_ibcs": "IBC areas",
    "subdivisions": "sub-divisions",
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
                val = int(val) if float(val).is_integer() and UNITS.get(col) != "rho" else val
            fid = qid if col in ("feeders", "ibcs") and len(cols) == 1 else f"{qid}_{col}"
            facts.append(Fact(fid, f"{qid}.{col}", val, UNITS.get(col, ""), qid))
    return facts
