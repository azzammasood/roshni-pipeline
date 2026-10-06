"""Command-line entry point. Orchestrators (GitHub Actions, Airflow) call these commands."""

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
