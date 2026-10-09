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
) -> None:
    """Build the DuckDB warehouse with dbt (seeds, models, tests)."""
    import os

    from dbt.cli.main import dbtRunner

    from roshni.paths import DATA_DIR, REPO_ROOT

    project = REPO_ROOT / "dbt"
    os.environ["ROSHNI_PARSED_DIR"] = (parsed or DATA_DIR / "parsed").resolve().as_posix()
    db_path = (db or DATA_DIR / "roshni.duckdb").resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    os.environ["ROSHNI_DUCKDB_PATH"] = db_path.as_posix()
    args = [command, "--project-dir", str(project), "--profiles-dir", str(project)]
    if select:
        args += ["--select", select]
    result = dbtRunner().invoke(args)
    if not result.success:
        raise typer.Exit(1)
