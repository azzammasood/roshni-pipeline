"""Build the static export (data/export/v1/*.json) from the warehouse and validate it."""

import json
import re
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import jsonschema

from roshni.export import models as m
from roshni.paths import REPO_ROOT

SCHEMA_DIR = REPO_ROOT / "schemas" / "v1"
KARACHI = (
    "KARACHI CENTRAL DISTRICT", "KARACHI EAST DISTRICT", "KARACHI SOUTH DISTRICT",
    "KARACHI WEST DISTRICT", "KEAMARI DISTRICT", "KORANGI DISTRICT", "MALIR DISTRICT",
)  # fmt: skip
IESCO_DISTRICTS = (
    "ISLAMABAD DISTRICT", "RAWALPINDI DISTRICT", "ATTOCK DISTRICT", "JHELUM DISTRICT",
    "CHAKWAL DISTRICT",
)  # fmt: skip


def utc_session(con: duckdb.DuckDBPyConnection) -> None:
    """DuckDB returns timestamptz in the session time zone (the machine's by default); the export
    stores UTC, so pin the session or `*_utc` fields come out as local offsets."""
    con.execute("set TimeZone = 'UTC'")


def _rows(con, sql: str, **params) -> list[dict]:
    cur = con.execute(sql, params or None)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r, strict=True)) for r in cur.fetchall()]


def write_schemas(out: Path = SCHEMA_DIR) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, model in m.DOCUMENTS.items():
        schema = model.model_json_schema()
        schema["$id"] = f"https://github.com/azzammasood/roshni-pipeline/schemas/v1/{name}.json"
        schema["title"] = f"roshni/{name}/v1"
        p = out / f"{name}.schema.json"
        text = json.dumps(schema, indent=2, sort_keys=True) + "\n"
        p.write_text(text, encoding="utf-8", newline="\n")
        paths.append(p)
    return paths


# Review-seed note prefixes (CLAUDE.md): rules, LLM and Claude stamp their notes; anything else
# with a decision is the owner's.
_NOTE = re.compile(
    r"^(?:(?P<rules>auto-review)|(?P<llm>llm-review)|(?P<claude>claude-review))"
    r"(?: (?P<date>\d{4}-\d{2}-\d{2}))?[^:]*:\s*(?P<reason>.*)$",
    re.S,
)


def match_review(method: str | None, note: str | None, status: str) -> m.MatchReview | None:
    """Who accepted a match and why, from the seed note; None for automatic exact matches."""
    if method is None or (status == "auto_exact" and not note):
        return None
    note = (note or "").strip()
    if found := _NOTE.match(note):
        by = next(k for k in ("rules", "llm", "claude") if found.group(k))
        return m.MatchReview(method=method, reviewed_by=by, reviewed_on=found.group("date"),
                             reason=found.group("reason").strip() or None)  # fmt: skip
    return m.MatchReview(method=method, reviewed_by="owner", reviewed_on=None, reason=note or None)


def _feeders(con) -> list[m.Feeder]:
    loc = defaultdict(list)
    for r in _rows(con, "select feeder_id, area_id, area_name, match_status, match_confidence, "
                        "method, match_note from feeder_locality_match "
                        "order by feeder_id, area_name"):  # fmt: skip
        review = match_review(r.pop("method"), r.pop("match_note"), r["match_status"])
        loc[r.pop("feeder_id")].append(m.LocalityMatch(**r, review=review))
    out = []
    for r in _rows(con, "select * from dim_feeder order by feeder_id"):
        out.append(m.Feeder(
            feeder_id=r["feeder_id"], source=r["source"], name=r["feeder_name"],
            feeder_code=r["feeder_code"], circle=r["circle"], grid=r["grid_name"], ibc=r["ibc"],
            category=r["category"], atc_loss_pct=r["atc_loss_pct"],
            in_feeder_list=r["in_feeder_list"], has_schedule=r["has_schedule"],
            schedule_match_method=r["schedule_match_method"],
            schedule_match_confidence=r["schedule_match_confidence"],
            localities=loc.get(r["feeder_id"], []),
        ))  # fmt: skip
    return out


def hourly_minutes(windows: list[m.Window]) -> list[int]:
    """Dark minutes per local hour covered by [start, end) windows (end <= start wraps)."""
    hours = [0] * 24
    for w in windows:
        end = w.end_min if w.end_min > w.start_min else w.end_min + 1440
        for minute in range(w.start_min, end):
            hours[minute % 1440 // 60] += 1
    return hours


def _dark_profiles(con) -> list[m.DarkProfile]:
    prof: dict[str, dict] = {}
    for r in _rows(con, "select * from mart_feeder_dark_hours order by feeder_id"):
        p = prof.setdefault(
            r["feeder_id"],
            {"feeder_id": r["feeder_id"], "source": r["source"], "eff": r["effective_from"]},
        )
        key = "daily" if r["schedule_kind"] == "daily_cycle" else str(r["scenario_level_hours"])
        p.setdefault(key, [0] * 24)[r["hour_of_day"]] = int(r["dark_minutes"])

    # Hourly minutes cannot say whether 22:40 is dark when hour 22 has 25 minutes, so K-Electric
    # profiles also carry their exact windows. IESCO slots must be whole hours: then the hourly
    # vector is exact and needs no windows (fail loudly if a new file breaks that).
    misaligned = con.sql("""
        select count(*) from fct_schedule_window
        where schedule_kind = 'scenario_level'
          and (start_minute_local % 60 <> 0 or end_minute_local - start_minute_local <> 60)
    """).fetchone()[0]
    if misaligned:
        raise ValueError(f"{misaligned} IESCO scenario windows are not whole local hours")
    windows: dict[str, list[m.Window]] = defaultdict(list)
    for fid, s, e in con.sql("""
        select feeder_id, start_minute_local, end_minute_local from fct_schedule_window
        where schedule_kind = 'daily_cycle' order by feeder_id, start_minute_local
    """).fetchall():
        windows[fid].append(m.Window(start_min=s, end_min=e))

    out = []
    for p in prof.values():
        if p.get("daily") and hourly_minutes(windows[p["feeder_id"]]) != p["daily"]:
            raise ValueError(f"{p['feeder_id']}: daily windows disagree with hourly minutes")
        levels = dict(
            sorted(((k, v) for k, v in p.items() if k.isdigit()), key=lambda kv: int(kv[0]))
        )
        out.append(m.DarkProfile(
            feeder_id=p["feeder_id"], source=p["source"], effective_from=p["eff"],
            daily=p.get("daily"), daily_windows=windows.get(p["feeder_id"]),
            scenario_levels=levels or None,
        ))  # fmt: skip
    return out


def _areas(con) -> list[m.Area]:
    rows = _rows(
        con,
        """
        select area_id, area_name as name, area_type || '_' || area_level as level, province,
               district, pop_total, literacy_pct, degree_share_pct, pacca_share_pct,
               electricity_share_pct, avg_household_size
        from dim_area_indicators
        where area_level = 'district' and (district in $iesco or district in $karachi)
           or (area_level = 'tehsil' and district in $karachi)
           or area_id in (select area_id from feeder_locality_match)
        order by area_id
        """,
        iesco=list(IESCO_DISTRICTS),
        karachi=list(KARACHI),
    )
    return [m.Area(**r) for r in rows]


def _equity(con, report_json: Path | None) -> m.Equity:
    ibc = [m.IbcEquity(**{k: r[k] for k in m.IbcEquity.model_fields})
           for r in _rows(con, "select * from mart_ke_ibc_equity order by ibc")]  # fmt: skip
    subs = [m.SubdivisionEquity(**{k: r[k] for k in m.SubdivisionEquity.model_fields})
            for r in _rows(con, "select * from mart_ke_subdivision_equity order by 2")]  # fmt: skip
    corr = [m.Correlation(**r) for r in _rows(con, "select * from rpt_spearman order by 1, 3")]
    anom = [m.Anomaly(**r) for r in _rows(con, "select * from rpt_ke_anomalies order by rule")]
    report = None
    if report_json and report_json.exists():
        d = json.loads(report_json.read_text(encoding="utf-8"))
        report = m.Report(
            iso_week=d["iso_week"], engine=d["engine"], narrative=d["narrative"],
            facts=[m.ReportFact(**f) for f in d["facts"]],
        )  # fmt: skip
    return m.Equity(
        scope_note="K-Electric shares are among listed feeders only (exempt feeders are not "
        "published); statistics are descriptive and exploratory, not causal.",
        ibc=ibc, subdivisions=subs, correlations=corr, anomalies=anom, report=report,
    )  # fmt: skip


def _meta(con, docs: list[str]) -> m.Meta:
    srcs = _rows(
        con,
        "select source, source_file, effective_from, effective_basis, published_label "
        "from source_documents order by source, source_file",
    )
    return m.Meta(
        timezone_display="Asia/Karachi",
        utc_offset_hours=5,
        documents=docs,
        sources=[m.SourceInfo(**s) for s in srcs],
        attribution=[
            "Load-shedding schedules and press releases: Islamabad Electric Supply Company "
            "(IESCO), iesco.com.pk",
            "Feeder list and load-shed schedule: K-Electric, ke.com.pk",
            "Census 2023 tables: Pakistan Bureau of Statistics",
        ],
        disclaimer="Not affiliated with IESCO, K-Electric or PBS. Schedules are published plans, "
        "not measured outages; IESCO schedules are a scenario playbook by interruption level.",
    )


def build_export(
    con: duckdb.DuckDBPyConnection, out: Path, report_json: Path | None = None
) -> dict[str, int]:
    utc_session(con)
    now = datetime.now(UTC).replace(microsecond=0)
    built = con.sql("select max(built_at) from mart_build_info").fetchone()[0]
    fetched = con.sql("select max(fetched_at) from dim_feeder").fetchone()[0]
    last = max(x for x in (built, fetched) if x is not None).astimezone(UTC)
    docs = {
        "feeders": _feeders(con),
        "dark_profiles": _dark_profiles(con),
        "planned_shutdowns": [
            m.PlannedShutdown(
                **{k: r[k] for k in m.PlannedShutdown.model_fields if k != "match_review"},
                match_review=match_review(r["match_method"], r["match_note"], r["match_status"]),
            )
            for r in _rows(con, "select * from fct_planned_shutdown_feeder order by shutdown_id")
        ],
        "areas": _areas(con),
        "equity": _equity(con, report_json),
    }
    docs = {"meta": _meta(con, ["meta", *docs]), **docs}
    out.mkdir(parents=True, exist_ok=True)
    counts = {}
    for name, data in docs.items():
        env = m.DOCUMENTS[name](
            schema_id=f"roshni/{name}/v1", schema_version=m.SCHEMA_VERSION, generated_at=now,
            last_updated=last, label=m.LABEL, data=data,
        )  # fmt: skip
        (out / f"{name}.json").write_text(env.model_dump_json(), encoding="utf-8")
        counts[name] = len(data) if isinstance(data, list) else 1
    return counts


def validate_export(out: Path, schema_dir: Path = SCHEMA_DIR) -> dict[str, str]:
    """Validate every exported file against its committed JSON Schema. Raises on failure."""
    results = {}
    for name in m.DOCUMENTS:
        schema = json.loads((schema_dir / f"{name}.schema.json").read_text(encoding="utf-8"))
        doc = json.loads((out / f"{name}.json").read_text(encoding="utf-8"))
        jsonschema.validate(doc, schema)
        results[name] = "valid"
    return results
