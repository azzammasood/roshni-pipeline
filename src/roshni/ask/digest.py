"""Today's digest ("What changed today", written with the prepared answers in publish): a few
counts for today, computed by SQL on the warehouse, and one or two sentences about them written
by the main model with placeholders only, checked by the same `check_prose` as Ask Roshni (no
numbers of its own, no causes, schedules never called outages). A template is used when no
model passes. One model call a day (~1.5K tokens).
"""

import re
from datetime import date, datetime, timedelta

import duckdb

from roshni.ask import engine
from roshni.llm.chain import ChainConfig, complete

QUESTION = "What does Roshni's published data say for today?"

# Owner, 2026-11-27: the digest says "scheduled". Every count is a scheduled or announced
# window, so wording that sounds like an event that happened or was measured is rejected.
DIGEST_RULES = """
Digest rules, also mandatory:
6. Call every window and shutdown "scheduled" (for example "scheduled maintenance windows",
   "scheduled shutdowns"); the word "scheduled" must appear.
7. Never say reported, recorded, occurred, happened, took place, affected or affecting: these are
   plans published in advance, not events."""
NOT_SCHEDULED = re.compile(
    r"\b(report(ed|s)?|record(ed|s)?|occur(red|s)?|happen(ed|s)?|took place|affect(ed|s|ing)?)\b",
    re.I,
)


def check_digest(text: str, facts: dict[str, str]) -> list[str]:
    problems = engine.check_prose(text, facts, QUESTION)
    if not re.search(r"\bscheduled\b", text, re.I):
        problems.append('say "scheduled"')
    if m := NOT_SCHEDULED.search(text):
        problems.append(f'"{m.group(0)}" describes an event; these are scheduled windows')
    return problems


TEMPLATE = (
    "Today IESCO has {maint_today} scheduled maintenance windows on {maint_feeders} feeders, "
    "{maint_week} scheduled in the next seven days, and {shutdowns_today} scheduled shutdowns "
    "announced in press releases. "
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
                {"role": "system", "content": engine.NARRATOR + DIGEST_RULES},
                {
                    "role": "user",
                    "content": f"Question: {QUESTION}\nColumns: {list(f)}\n"
                    f"Facts (id = value; write the id, never the value):\n{listing}",
                },
            ],
            cfg,
            lambda t: check_digest(t, f),
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
