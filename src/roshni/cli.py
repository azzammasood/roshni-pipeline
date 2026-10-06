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
