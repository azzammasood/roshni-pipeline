"""Today's digest ("What changed today", written with the prepared answers in publish): a few
counts for today, computed by SQL on the warehouse, and one or two sentences about them written
by the main model with placeholders only, checked by the same `check_prose` as Ask Roshni (no
numbers of its own, no causes, schedules never called outages). A template is used when no
model passes. One model call a day (~1.5K tokens).
"""

from datetime import date, datetime, timedelta

import duckdb

from roshni.ask import engine
from roshni.llm.chain import ChainConfig, complete

QUESTION = "What does Roshni's published data say for today?"

TEMPLATE = (
    "Today IESCO lists {maint_today} announced maintenance windows on {maint_feeders} feeders, "
    "{maint_week} in the next seven days, and {shutdowns_today} press-release shutdowns. "
    "K-Electric's schedule in use took effect on {ke_effective}. "
    "{news_day} new headlines were seen in the last day."
)


def facts(con: duckdb.DuckDBPyConnection, today: date, now: datetime) -> dict[str, str]:
    """Counts for `today` (Pakistan date); `now` is UTC, for the news window."""
    week_end = today + timedelta(days=6)
    q = lambda sql, *p: con.execute(sql, list(p)).fetchone()  # noqa: E731
    mt, mf = q(
        "select count(*), count(distinct feeder_code) from fct_maintenance_window "
        "where outage_date = ? and not coalesce(repeats_circle_window, false)",
        today,
    )
    (mw,) = q(
        "select count(*) from fct_maintenance_window where outage_date between ? and ? "
        "and not coalesce(repeats_circle_window, false)",
        today,
        week_end,
    )
    (st,) = q("select count(*) from fct_planned_shutdown where outage_date = ?", today)
    (ke,) = q("select max(effective_from) from mart_ke_schedule_history")
    (nd,) = q(
        "select count(*) from mart_news_headline where first_seen_at >= ?",
        now - timedelta(hours=24),
    )
    raw = {
        "maint_today": mt,
        "maint_feeders": mf,
        "maint_week": mw,
        "shutdowns_today": st,
        "ke_effective": ke,
        "news_day": nd,
    }
    return {k: ("none" if v is None else engine.fmt(v)) for k, v in raw.items()}


def build(con, cfg: ChainConfig | None, today: date, now: datetime, log=print) -> dict:
    f = facts(con, today, now)
    text, model, tokens = None, "", 0
    if cfg is not None:
        listing = "\n".join(f"{k} = {v}" for k, v in f.items())
        comp = complete(
            [
                {"role": "system", "content": engine.NARRATOR},
                {
                    "role": "user",
                    "content": f"Question: {QUESTION}\nColumns: {list(f)}\n"
                    f"Facts (id = value; write the id, never the value):\n{listing}",
                },
            ],
            cfg,
            lambda t: engine.check_prose(t, f, QUESTION),
        )
        tokens = sum(a.tokens_in + a.tokens_out for a in comp.attempts)
        if comp.text is not None:
            text, model = " ".join(engine.render(comp.text, f).split()), comp.accepted.label
    log(f"  digest: {'narrated by ' + model if text else 'template'} ({tokens} tokens)")
    return {
        "date": str(today),
        "facts": f,
        "text": text or engine.render(TEMPLATE, f),
        "narrated_by": model,
        "tokens": tokens,
    }
