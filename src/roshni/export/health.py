"""Pipeline health (export 1.9.0): what the daily pipeline did, for the site's health page.

Three histories, none of which needs a store of its own:
- publish runs (start, duration, outcome) from the GitHub Actions API, which keeps them;
- daily fetch activity from the snapshot log (raw_snapshots.csv), which records every fetch;
- warehouse table sizes per publish, carried forward from the live health.json and appended to.
Plus this run's dbt results and the parsed tables' quarantine counts, and (1.10.0) parser
healing: this run's check (data/heal/status.json), the learned aliases (config) and the committed
chaos-eval record (evals/parser_healing.json); (1.11.0) the Ask Roshni eval record
(evals/ask_roshni.json), both with one history point per weekly run.

Every input is optional: a local run without the store, the API or the live site still writes a
valid document, with those histories empty.
"""

import csv
import json
import os
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import duckdb
import httpx
import yaml

from roshni.export import models as m
from roshni.paths import CONFIG_DIR, DATA_DIR, REPO_ROOT

HEAL_STATUS = DATA_DIR / "heal" / "status.json"
ALIASES = CONFIG_DIR / "parser_aliases.yml"
HEAL_EVAL = REPO_ROOT / "evals" / "parser_healing.json"
ASK_EVAL = REPO_ROOT / "evals" / "ask_roshni.json"

FRESHNESS_TARGET_HOURS = 36  # the watchdog's threshold (watchdog.yml)
KARACHI = timedelta(hours=5)
SIZE_HISTORY = 365  # publish dates kept in the sizes history
RUN_HISTORY = 100  # GitHub's page size: the newest publish runs
# Warehouse tables whose size is tracked: label -> SQL.
SIZE_QUERIES = {
    "feeders": "select count(*) from dim_feeder",
    "schedule_windows": "select count(*) from fct_schedule_window",
    "planned_shutdowns": "select count(*) from fct_planned_shutdown",
    "maintenance_windows": "select count(*) from fct_maintenance_window",
}
# Fetch notes that are not failures: unchanged files and links the audit records as broken.
QUIET_NOTES = ("same content", "not modified", "known broken")


def karachi_day(iso_utc: str) -> date:
    return (datetime.fromisoformat(iso_utc.replace("Z", "+00:00")) + KARACHI).date()


def fetch_days(store: Path | None) -> list[m.FetchDay]:
    """Per Karachi day: fetches made, new or changed files stored, and failed fetches."""
    log = store / "raw_snapshots.csv" if store else None
    if log is None or not log.exists():
        return []
    days: dict[date, list[int]] = defaultdict(lambda: [0, 0, 0])
    with log.open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            d = days[karachi_day(r["fetched_at"])]
            d[0] += 1
            d[1] += r["changed"] == "true"
            status = r["http_status"]
            failed = not status or not (status.startswith("2") or status == "304")
            d[2] += failed and not r["note"].startswith(QUIET_NOTES)
    return [
        m.FetchDay(date=k, fetches=v[0], new_files=v[1], errors=v[2])
        for k, v in sorted(days.items())
    ]


def publish_runs(repo: str | None, token: str | None = None) -> list[m.PublishRun]:
    """Completed publish runs, oldest first, from the GitHub Actions API ([] if unavailable)."""
    if not repo:
        return []
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "roshni-pipeline"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    url = f"https://api.github.com/repos/{repo}/actions/workflows/publish.yml/runs"
    try:
        resp = httpx.get(url, params={"per_page": RUN_HISTORY}, headers=headers, timeout=30)
        resp.raise_for_status()
    except httpx.HTTPError:
        return []
    runs = []
    for r in resp.json().get("workflow_runs", []):
        if r.get("status") != "completed":
            continue  # the run writing this document is still in progress
        start = datetime.fromisoformat(r["run_started_at"].replace("Z", "+00:00"))
        end = datetime.fromisoformat(r["updated_at"].replace("Z", "+00:00"))
        runs.append(
            m.PublishRun(
                started_at=start,
                duration_seconds=max(0, int((end - start).total_seconds())),
                conclusion=r.get("conclusion") or "unknown",
                trigger=r.get("event") or "",
                url=r.get("html_url") or "",
            )
        )
    return sorted(runs, key=lambda x: x.started_at)


def previous_sizes(url: str | None) -> list[m.SizePoint]:
    """The sizes history from the live health.json ([] when there is none yet)."""
    if not url:
        return []
    try:
        resp = httpx.get(url, timeout=30, headers={"User-Agent": "roshni-pipeline"})
        resp.raise_for_status()
        return [m.SizePoint(**p) for p in resp.json()["data"]["sizes"]]
    except (httpx.HTTPError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return []


def dbt_results(path: Path) -> m.DbtResults:
    counts = {"pass": 0, "success": 0, "warn": 0, "error": 0, "fail": 0, "skipped": 0}
    if path.exists():
        for r in json.loads(path.read_text(encoding="utf-8")).get("results", []):
            counts[r.get("status", "")] = counts.get(r.get("status", ""), 0) + 1
    return m.DbtResults(
        passed=counts["pass"] + counts["success"],
        warned=counts["warn"],
        failed=counts["error"] + counts["fail"],
        skipped=counts["skipped"],
    )


def parsed_quality(parsed: Path) -> list[m.TableQuality]:
    """Rows kept and rows quarantined per parsed table, with the most common reasons."""
    out = []
    con = duckdb.connect()
    try:
        for p in sorted(parsed.glob("*.parquet")):
            kept = con.execute("select count(*) from read_parquet(?)", [str(p)]).fetchone()[0]
            q = parsed / "quarantine" / p.name
            reasons = (
                con.execute(
                    "select split_part(reason, ':', 1) as r, count(*) as n "
                    "from read_parquet(?) group by 1 order by 2 desc, 1",
                    [str(q)],
                ).fetchall()
                if q.exists()
                else []
            )
            out.append(
                m.TableQuality(
                    table=p.stem,
                    rows=kept,
                    quarantined=sum(n for _, n in reasons),
                    top_reasons=[m.QuarantineReason(reason=r, rows=n) for r, n in reasons[:3]],
                )
            )
    finally:
        con.close()
    return out


def healing(
    status: Path = HEAL_STATUS, aliases: Path = ALIASES, evals: Path = HEAL_EVAL
) -> m.Healing:
    """Parser healing; each part is None or empty when its file is missing."""
    check = (
        m.HealCheck(**json.loads(status.read_text(encoding="utf-8"))) if status.exists() else None
    )
    learned = []
    if aliases.exists():
        for parser, entries in (yaml.safe_load(aliases.read_text(encoding="utf-8")) or {}).items():
            learned += [
                m.LearnedAlias(parser=parser, header=e["header"], field=e["field"],
                               added=e.get("added"), by=e.get("by", ""))
                for e in entries or []
            ]  # fmt: skip
    ev = m.HealEval(**json.loads(evals.read_text(encoding="utf-8"))) if evals.exists() else None
    return m.Healing(last_check=check, aliases=learned, eval=ev)


def ask_eval(path: Path = ASK_EVAL) -> m.AskEval | None:
    """The committed Ask Roshni eval record, or None before its first recorded run."""
    if not path.exists():
        return None
    from roshni import evalrecord
    from roshni.ask.evaluate import load_items

    data = json.loads(path.read_text(encoding="utf-8"))
    run_on = date.fromisoformat(data["run_on"])
    models = sorted({p["model"] for p in data["history"] if p["date"] == data["run_on"]})
    rolling = []
    for mo in models:
        r = evalrecord.rolling(data, mo, run_on)
        if r:
            items = data.get("items_last", {}).get(mo, {})
            rolling.append(r | {"by_question": evalrecord.by_question(items)})
    return m.AskEval(
        run_on=data["run_on"],
        models=data["models"],
        history=data["history"],
        items_total=len(load_items()),
        rolling=rolling,
    )


def build_health(
    con: duckdb.DuckDBPyConnection,
    parsed: Path,
    run_results: Path,
    store: Path | None = None,
    repo: str | None = None,
    previous_url: str | None = None,
    now: datetime | None = None,
) -> m.Health:
    today = ((now or datetime.now(UTC)) + KARACHI).date()
    rows = {k: con.sql(q).fetchone()[0] for k, q in SIZE_QUERIES.items()}
    sizes = [p for p in previous_sizes(previous_url) if p.date != today]
    sizes = [*sizes, m.SizePoint(date=today, rows=rows)][-SIZE_HISTORY:]
    return m.Health(
        freshness_target_hours=FRESHNESS_TARGET_HOURS,
        dbt=dbt_results(run_results),
        parsed=parsed_quality(parsed),
        sizes=sizes,
        publish_runs=publish_runs(
            repo, os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        ),
        fetch_days=fetch_days(store),
        healing=healing(),
        ask_eval=ask_eval(),
    )
