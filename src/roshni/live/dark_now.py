"""'Dark now': which feeders are scheduled to be without power at a given instant.

Everything here is SCHEDULE data (published schedules, scenario playbooks and planned-shutdown
announcements), never measured outages. Times: input in Asia/Karachi (UTC+5, no DST) or any
aware datetime; recurring windows are local minutes of day; planned shutdowns are stored in UTC.
"""

from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta, timezone

import duckdb

PKT = timezone(timedelta(hours=5), "Asia/Karachi")
LABEL = "Scheduled (published schedule data), not a measured outage"
IESCO_LEVELS = (2, 4, 6, 8, 10, 12)


def to_pkt(at: datetime) -> datetime:
    """Naive datetimes are taken as Asia/Karachi; aware ones are converted."""
    return at.replace(tzinfo=PKT) if at.tzinfo is None else at.astimezone(PKT)


def minute_of_day(at: datetime) -> int:
    local = to_pkt(at)
    return local.hour * 60 + local.minute


def window_active(start_min: int, end_min: int, minute: int) -> bool:
    """Is `minute` (0..1439) inside [start, end)? A window with end <= start wraps midnight.

    End is exclusive, so a 22:35~02:05 window is dark at 22:35 and 02:04, not at 02:05;
    an IESCO 23--24 slot (end 1440) is dark from 23:00 to 23:59.
    """
    if end_min > start_min:
        return start_min <= minute < end_min
    return minute >= start_min or minute < end_min


def _fmt(minutes: int) -> str:
    return f"{minutes // 60 % 24:02d}:{minutes % 60:02d}" if minutes < 1440 else "24:00"


@dataclass
class DarkRow:
    feeder_id: str | None
    feeder_name: str
    source: str  # iesco | kelectric
    kind: str  # daily_cycle | scenario_level_N | planned_shutdown
    area: str | None  # K-Electric IBC or IESCO circle (as printed for unmatched shutdowns)
    window_local: str  # "22:35-02:05" (Asia/Karachi)
    effective_from: date | None
    last_updated: datetime | None  # when the underlying source was fetched (UTC)
    label: str = LABEL


@dataclass
class DarkNow:
    at_local: datetime
    iesco_level: int | None
    rows: list[DarkRow]
    notes: list[str]

    def counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for r in self.rows:
            out[r.kind] = out.get(r.kind, 0) + 1
        return out

    def to_dict(self) -> dict:
        return {
            "at_local": self.at_local.isoformat(),
            "iesco_level": self.iesco_level,
            "label": LABEL,
            "counts": self.counts(),
            "notes": self.notes,
            "rows": [asdict(r) for r in self.rows],
        }


def dark_now(
    con: duckdb.DuckDBPyConnection, at: datetime, iesco_level: int | None = None
) -> DarkNow:
    """Feeders scheduled dark at `at`, from the warehouse tables built by dbt."""
    if iesco_level is not None and iesco_level not in IESCO_LEVELS:
        raise ValueError(f"IESCO level must be one of {IESCO_LEVELS}")
    local = to_pkt(at)
    minute, today = minute_of_day(local), local.date()
    notes: list[str] = []
    built = con.sql("select max(built_at) from mart_build_info").fetchone()[0]

    windows = con.sql(
        """
        select w.feeder_id, f.feeder_name, w.source, w.schedule_kind, w.scenario_level_hours,
               coalesce(f.ibc, f.circle, 'grid ' || f.grid_name) as area,
               w.start_minute_local, w.end_minute_local,
               w.effective_from, f.fetched_at
        from fct_schedule_window as w
        join dim_feeder as f on f.feeder_id = w.feeder_id
        where w.schedule_kind = 'daily_cycle'
           or (w.schedule_kind = 'scenario_level' and w.scenario_level_hours = $level)
        """,
        params={"level": iesco_level if iesco_level is not None else -1},
    ).fetchall()
    rows: list[DarkRow] = []
    not_yet: set[str] = set()
    for fid, name, src, kind, level, area, s, e, eff, fetched in windows:
        if eff is not None and eff > today:
            not_yet.add(f"{src} effective from {eff}")
            continue
        if window_active(s, e, minute):
            rows.append(
                DarkRow(
                    feeder_id=fid,
                    feeder_name=name,
                    source=src,
                    kind="daily_cycle" if kind == "daily_cycle" else f"scenario_level_{level}",
                    area=area,
                    window_local=f"{_fmt(s)}-{_fmt(e)}",
                    effective_from=eff,
                    last_updated=fetched or built,
                )
            )
    notes += sorted(f"not applicable at this date: {n}" for n in not_yet)
    if iesco_level is None:
        notes.append(
            "IESCO scenario not shown: its files never say which interruption level is active; "
            "pass a level (2-12) to see 'if level N is active'"
        )

    at_utc = local.astimezone(UTC)
    unmatched = 0
    for fid, name, circle, s_loc, e_loc, d, fetched, state in con.sql(
        """
        select p.feeder_id, coalesce(f.feeder_name, p.feeder_name_as_printed), p.circle_as_printed,
               p.start_local, p.end_local, p.outage_date, p.fetched_at,
               p.feeder_match_state
        from fct_planned_shutdown_feeder as p
        left join dim_feeder as f on f.feeder_id = p.feeder_id
        where p.start_utc <= $at and $at < p.end_utc
        order by 3, 2
        """,
        params={"at": at_utc},
    ).fetchall():
        rows.append(
            DarkRow(
                feeder_id=fid,
                feeder_name=name,
                source="iesco",
                kind="planned_shutdown",
                area=circle,
                window_local=f"{s_loc}-{e_loc}",
                effective_from=d,
                last_updated=fetched or built,
            )
        )
        unmatched += state != "matched"
    if unmatched:
        notes.append(
            f"{unmatched} planned shutdown(s) name a feeder not matched to the feeder list"
        )
    rows.sort(key=lambda r: (r.kind, r.source, r.area or "", r.feeder_name))
    return DarkNow(local, iesco_level, rows, notes)
