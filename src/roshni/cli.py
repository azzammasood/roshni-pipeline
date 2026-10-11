"""Command-line entry point. Orchestrators (GitHub Actions, Airflow) call these commands."""

from pathlib import Path

import typer

from roshni import __version__

app = typer.Typer(no_args_is_help=True, add_completion=False)


def _version(value: bool) -> None:
    if value:
        typer.echo(f"roshni {__version__}")
        raise typer.Exit


@app.callback()
def main(
    version: bool = typer.Option(
        False, "--version", callback=_version, is_eager=True, help="Show version."
    ),
) -> None:
    """Roshni Pipeline CLI."""


@app.command()
def info() -> None:
    """Print package version and repo paths."""
    from roshni.paths import DATA_DIR, DATA_SOURCES_DIR, REPO_ROOT

    typer.echo(f"roshni {__version__}")
    typer.echo(f"repo root:    {REPO_ROOT}")
    typer.echo(f"data:         {DATA_DIR}")
    typer.echo(f"data-sources: {DATA_SOURCES_DIR} (present: {DATA_SOURCES_DIR.is_dir()})")


@app.command()
def snapshot(
    store: Path = typer.Option(
        None,
        help="Snapshot store root (default: data/snapshots). CI uses a data-snapshots checkout.",
    ),
    only: list[str] = typer.Option(None, help="Limit to these source ids (repeatable)."),
) -> None:
    """Discover and fetch source files; store changed ones and log every check."""
    import os

    from roshni.fetch.http import PoliteClient
    from roshni.fetch.snapshot import run_snapshot
    from roshni.fetch.store import SnapshotStore
    from roshni.paths import DATA_DIR
    from roshni.sources.registry import load_registry

    reg = load_registry()
    st = SnapshotStore(store or DATA_DIR / "snapshots")
    with PoliteClient(reg.user_agent, reg.min_request_interval_seconds, reg.timeout_seconds) as c:
        report = run_snapshot(c, st, reg, set(only) if only else None)

    lines = [
        f"- `{i.source}/{i.item_key}`: **{i.outcome}** {i.detail}".rstrip()
        for i in report.items
        if i.outcome != "known"
    ]
    lines += [f"- ERROR {e}" for e in report.errors]
    lines += [f"- WARNING {w}" for w in report.warnings]
    lines.append(f"\n**{report.summary_line()}**")
    text = "\n".join(lines)
    typer.echo(text)
    if summary := os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(summary).open("a", encoding="utf-8") as f:
            f.write("## Snapshot\n" + text + "\n")
    if not report.ok:
        raise typer.Exit(1)


@app.command()
def parse(
    sources: Path = typer.Option(None, help="Folder of source files (default: data-sources/)."),
    out: Path = typer.Option(None, help="Output folder (default: data/parsed)."),
    snapshots: Path = typer.Option(
        None, help="Optional snapshot store (data-snapshots checkout) for extra press releases."
    ),
) -> None:
    """Parse every source into typed Parquet tables plus quarantine files."""
    from roshni.parsers.run import run_all
    from roshni.paths import DATA_DIR, DATA_SOURCES_DIR

    out = out or DATA_DIR / "parsed"
    for s in run_all(sources or DATA_SOURCES_DIR, out, snapshots):
        typer.echo(f"{s.table:30} rows={s.rows:6} quarantined={s.quarantined}")
    typer.echo(f"written to {out}")


@app.command()
def validate(
    parsed: Path = typer.Option(None, help="Parsed Parquet folder (default: data/parsed)."),
) -> None:
    """Run the Great Expectations suites on the parsed Parquet layer."""
    from roshni.paths import DATA_DIR
    from roshni.quality.suites import validate_dir

    results = validate_dir(parsed or DATA_DIR / "parsed")
    for r in results:
        status = "PASS" if r.success else "FAIL"
        typer.echo(f"{status} {r.table:30} expectations={r.evaluated} {' '.join(r.failed)}")
    if not results or not all(r.success for r in results):
        raise typer.Exit(1)


@app.command()
def build(
    parsed: Path = typer.Option(None, help="Parsed Parquet folder (default: data/parsed)."),
    db: Path = typer.Option(None, help="DuckDB file (default: data/roshni.duckdb)."),
    command: str = typer.Option("build", help="dbt command: build, run, test, parse, seed."),
    select: str = typer.Option(None, help="dbt --select expression."),
    target: str = typer.Option("dev", help="dbt target: dev (DuckDB) or databricks."),
) -> None:
    """Build the warehouse with dbt (seeds, models, tests) on DuckDB or Databricks."""
    import os

    from dbt.cli.main import dbtRunner

    from roshni.paths import DATA_DIR, REPO_ROOT

    project = REPO_ROOT / "dbt"
    os.environ["ROSHNI_PARSED_DIR"] = (parsed or DATA_DIR / "parsed").resolve().as_posix()
    db_path = (db or DATA_DIR / "roshni.duckdb").resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    os.environ["ROSHNI_DUCKDB_PATH"] = db_path.as_posix()
    args = [command, "--project-dir", str(project), "--profiles-dir", str(project)]
    args += ["--target", target]
    if select:
        args += ["--select", select]
    result = dbtRunner().invoke(args)
    if not result.success:
        raise typer.Exit(1)


@app.command()
def resolve(
    db: Path = typer.Option(None, help="Warehouse DuckDB (default: data/roshni.duckdb)."),
) -> None:
    """Generate match candidates into review seeds (dbt/seeds/review_*.csv), keeping decisions.

    Run after `roshni build`; then fill `decision` (accepted/rejected) and run `roshni build`.
    """
    from collections import Counter

    import duckdb

    from roshni.paths import DATA_DIR, REPO_ROOT
    from roshni.resolve import matchers
    from roshni.resolve.review import merge_write

    con = duckdb.connect(str(db or DATA_DIR / "roshni.duckdb"), read_only=True)
    jobs = {
        "review_feeder_locality.csv": matchers.feeder_locality,
        "review_press_feeder.csv": matchers.press_feeders,
        "review_ibc_subdivision.csv": matchers.ibc_subdivision,
    }
    for name, fn in jobs.items():
        rows = fn(con)
        stats = merge_write(REPO_ROOT / "dbt" / "seeds" / name, rows, matchers.REVIEW_COLUMNS)
        top = Counter(r["status"] for r in rows if r["rank"] in (0, 1))
        typer.echo(f"{name:28} subjects={sum(top.values()):4} {dict(top)} {stats}")
    con.close()


@app.command("dark-now")
def dark_now_cmd(
    at: str = typer.Option(
        None, help="Time, e.g. '2026-10-10 23:30' (Asia/Karachi unless an offset is given)."
    ),
    level: int = typer.Option(None, help="IESCO scenario: show 'if level N is active' (2-12)."),
    limit: int = typer.Option(20, help="Rows to print (0 = all)."),
    as_json: bool = typer.Option(False, "--json", help="Print JSON instead of a table."),
    db: Path = typer.Option(None, help="Warehouse DuckDB (default: data/roshni.duckdb)."),
) -> None:
    """Feeders SCHEDULED to be dark at a time (schedule data, not measured outages)."""
    import json
    from datetime import datetime

    import duckdb

    from roshni.live.dark_now import LABEL, dark_now
    from roshni.paths import DATA_DIR

    when = datetime.fromisoformat(at) if at else datetime.now().astimezone()
    con = duckdb.connect(str(db or DATA_DIR / "roshni.duckdb"), read_only=True)
    try:
        result = dark_now(con, when, level)
    except ValueError as e:
        raise typer.BadParameter(str(e)) from e
    finally:
        con.close()
    if as_json:
        typer.echo(json.dumps(result.to_dict(), default=str, indent=2))
        return
    typer.echo(f"{LABEL}\nAt {result.at_local:%Y-%m-%d %H:%M} Asia/Karachi")
    for kind, n in sorted(result.counts().items()):
        typer.echo(f"  {kind:22} {n:5} feeders")
    for note in result.notes:
        typer.echo(f"  note: {note}")
    shown = result.rows if limit == 0 else result.rows[:limit]
    for r in shown:
        typer.echo(
            f"  {r.kind:20} {r.source:9} {(r.area or '')[:22]:22} {r.feeder_name[:34]:34} "
            f"{r.window_local:11} eff {r.effective_from}"
        )
    if len(shown) < len(result.rows):
        typer.echo(f"  ... {len(result.rows) - len(shown)} more (use --limit 0 or --json)")


@app.command()
def report(
    engine: str = typer.Option(
        "auto", help="auto (LLM if OPENROUTER_API_KEY set), openrouter, template."
    ),
    out: Path = typer.Option(None, help="Output folder (default: data/reports)."),
    db: Path = typer.Option(None, help="Warehouse DuckDB (default: data/roshni.duckdb)."),
) -> None:
    """Write the weekly equity report (Markdown + JSON) with every number traced to a query."""
    import duckdb

    from roshni.narrate.report import build_report, write_report
    from roshni.paths import DATA_DIR

    if engine not in ("auto", "openrouter", "template"):
        raise typer.BadParameter("engine must be auto, openrouter or template")
    con = duckdb.connect(str(db or DATA_DIR / "roshni.duckdb"), read_only=True)
    try:
        rep = build_report(con, engine)
    finally:
        con.close()
    md, js = write_report(rep, out or DATA_DIR / "reports")
    typer.echo(
        f"engine={rep.engine} spent_usd={rep.data['spent_usd']} facts={len(rep.data['facts'])}"
    )
    for line in rep.data["narrator_log"]:
        typer.echo(f"  {line}")
    typer.echo(f"wrote {md}\nwrote {js}")


@app.command()
def export(
    out: Path = typer.Option(None, help="Output folder (default: data/export/v1)."),
    db: Path = typer.Option(None, help="Warehouse DuckDB (default: data/roshni.duckdb)."),
    write_schemas: bool = typer.Option(
        False, "--write-schemas", help="Regenerate schemas/v1/*.schema.json from the models."
    ),
) -> None:
    """Write the static JSON export and validate it against the committed JSON Schemas."""
    import duckdb

    from roshni.export.build import build_export, validate_export
    from roshni.export.build import write_schemas as write_schema_files
    from roshni.paths import DATA_DIR

    if write_schemas:
        for p in write_schema_files():
            typer.echo(f"schema {p}")
    out = out or DATA_DIR / "export" / "v1"
    reports = sorted((DATA_DIR / "reports").glob("equity-*.json"))
    con = duckdb.connect(str(db or DATA_DIR / "roshni.duckdb"), read_only=True)
    try:
        counts = build_export(con, out, reports[-1] if reports else None)
    finally:
        con.close()
    for name, status in validate_export(out).items():
        size = (out / f"{name}.json").stat().st_size
        typer.echo(f"{name:18} records={counts[name]:6} bytes={size:9,} schema={status}")
