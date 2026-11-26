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
    only: list[str] = typer.Option(
        None, help="Limit to these source ids (repeatable; shell-style patterns such as news_*)."
    ),
) -> None:
    """Discover and fetch source files; store changed ones and log every check."""
    import fnmatch
    import os

    from roshni.fetch.http import PoliteClient
    from roshni.fetch.snapshot import run_snapshot
    from roshni.fetch.store import SnapshotStore
    from roshni.paths import DATA_DIR
    from roshni.sources.registry import load_registry

    reg = load_registry()
    selected = None
    if only:
        selected = {name for pat in only for name in fnmatch.filter(reg.sources, pat)}
        unknown = [pat for pat in only if not fnmatch.filter(reg.sources, pat)]
        if unknown:
            raise typer.BadParameter(f"no source matches {unknown}", param_hint="--only")
    st = SnapshotStore(store or DATA_DIR / "snapshots")
    with PoliteClient(reg.user_agent, reg.min_request_interval_seconds, reg.timeout_seconds) as c:
        report = run_snapshot(c, st, reg, selected)

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
    if report.warnings:
        _notice("snapshot", [f"- {w}" for w in report.warnings])
    if not report.ok:
        raise typer.Exit(1)


def _notice(name: str, lines: list[str]) -> None:
    """Something changed that the pipeline handled on its own: written to data/notices/ for the
    workflow to post as a notice issue (the run still succeeds)."""
    from roshni.paths import DATA_DIR

    folder = DATA_DIR / "notices"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{name}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


@app.command()
def parse(
    sources: Path = typer.Option(None, help="Folder of source files (default: data-sources/)."),
    out: Path = typer.Option(None, help="Output folder (default: data/parsed)."),
    snapshots: Path = typer.Option(
        None,
        help="Optional snapshot store (data-snapshots checkout): extra press releases, and any "
        "schedule file missing from the sources folder.",
    ),
    census_from: Path = typer.Option(
        None, help="Use committed census tables (e.g. census/) instead of parsing census files."
    ),
) -> None:
    """Parse every source into typed Parquet tables plus quarantine files."""
    from roshni.parsers.run import run_all
    from roshni.paths import DATA_DIR, DATA_SOURCES_DIR

    out = out or DATA_DIR / "parsed"
    for s in run_all(sources or DATA_SOURCES_DIR, out, snapshots, census_from):
        typer.echo(f"{s.table:30} rows={s.rows:6} quarantined={s.quarantined}")
    typer.echo(f"written to {out}")


@app.command("effective-dates")
def effective_dates(
    snapshots: Path = typer.Option(..., help="Snapshot store (data-snapshots checkout)."),
    seed: Path = typer.Option(
        None, help="Seed to extend (default: dbt/seeds/source_documents.csv)."
    ),
) -> None:
    """Add effective_from rows for new schedule file versions (automatic; never edits a row)."""
    from roshni.parsers.effective import fill_seed
    from roshni.paths import REPO_ROOT

    added = fill_seed(snapshots, seed or REPO_ROOT / "dbt" / "seeds" / "source_documents.csv")
    lines = [
        f"- `{r['source']}` {r['source_file']} (`{r['source_sha256'][:12]}`): effective from "
        f"**{r['effective_from']}**, {r['effective_basis']}"
        for r in added
    ]
    typer.echo("\n".join(lines) or "no new schedule versions")
    if lines:
        _notice("effective-dates", ["New schedule versions, dated automatically:", *lines])


@app.command("census-freeze")
def census_freeze(
    parsed: Path = typer.Option(None, help="Parsed Parquet folder (default: data/parsed)."),
) -> None:
    """Write the trimmed census tables to census/ (committed; used by the daily job)."""
    from roshni.parsers.census import freeze
    from roshni.paths import DATA_DIR

    for table, rows in freeze(parsed or DATA_DIR / "parsed").items():
        typer.echo(f"{table:30} rows={rows}")


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
    exclude: str = typer.Option(None, help="dbt --exclude expression."),
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
    if exclude:
        args += ["--exclude", exclude]
    result = dbtRunner().invoke(args)
    if not result.success:
        raise typer.Exit(1)


@app.command("dbt-docs")
def dbt_docs(
    out: Path = typer.Option(None, help="Folder for index.html (default: data/dbt-docs)."),
    db: Path = typer.Option(
        None, help="DuckDB file for the catalog (default: data/roshni.duckdb)."
    ),
) -> None:
    """dbt docs (models, columns, tests, lineage graph) as one self-contained index.html.

    Run after `roshni build`: the catalog (column types, row counts) is read from the built
    warehouse. The publish job puts the page at <site>/dbt-docs/.
    """
    import os
    import shutil

    from dbt.cli.main import dbtRunner

    from roshni.paths import DATA_DIR, REPO_ROOT

    project = REPO_ROOT / "dbt"
    os.environ.setdefault("ROSHNI_PARSED_DIR", (DATA_DIR / "parsed").resolve().as_posix())
    os.environ["ROSHNI_DUCKDB_PATH"] = (db or DATA_DIR / "roshni.duckdb").resolve().as_posix()
    args = [
        "docs",
        "generate",
        "--static",
        "--project-dir",
        str(project),
        "--profiles-dir",
        str(project),
    ]
    if not dbtRunner().invoke(args).success:
        raise typer.Exit(1)
    target = out or DATA_DIR / "dbt-docs"
    target.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(project / "target" / "static_index.html", target / "index.html")
    typer.echo(f"dbt docs -> {target / 'index.html'}")


@app.command()
def resolve(
    db: Path = typer.Option(None, help="Warehouse DuckDB (default: data/roshni.duckdb)."),
    llm: bool = typer.Option(
        False, help="Let the OpenRouter chain decide press names the rules leave pending."
    ),
) -> None:
    """Generate match candidates into review seeds (dbt/seeds/review_*.csv), keeping decisions.

    Run after `roshni build`; then fill `decision` (accepted/rejected) and run `roshni build`.
    """
    import os
    from collections import Counter

    import duckdb

    from roshni.paths import DATA_DIR, REPO_ROOT
    from roshni.resolve import matchers
    from roshni.resolve.autoreview import review_press
    from roshni.resolve.llmreview import review_with_llm
    from roshni.resolve.review import merge_write

    con = duckdb.connect(str(db or DATA_DIR / "roshni.duckdb"), read_only=True)
    jobs = {
        "review_feeder_locality.csv": matchers.feeder_locality,
        "review_press_feeder.csv": matchers.press_feeders,
        "review_ibc_subdivision.csv": matchers.ibc_subdivision,
    }
    for name, fn in jobs.items():
        rows = fn(con)
        review = None
        if name == "review_press_feeder.csv":

            def review(rows: list[dict]) -> dict[str, int]:
                counts = review_press(rows)
                if llm:
                    counts |= review_with_llm(rows, os.environ.get("OPENROUTER_API_KEY"))
                return counts

        stats = merge_write(
            REPO_ROOT / "dbt" / "seeds" / name, rows, matchers.REVIEW_COLUMNS, review
        )
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

    from roshni.live.dark_now import LABEL, MAINTENANCE_LABEL, dark_now
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
    if "maintenance" in result.counts():
        typer.echo(f"maintenance rows: {MAINTENANCE_LABEL}")
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
    snapshots: Path = typer.Option(
        None, help="Snapshot store: daily fetch activity for the health document."
    ),
    github_repo: str = typer.Option(
        None, help="owner/name: publish-run history from the GitHub Actions API (GITHUB_TOKEN)."
    ),
    previous_health: str = typer.Option(
        None, help="URL of the live health.json: its table-size history is carried forward."
    ),
) -> None:
    """Write the static JSON export and validate it against the committed JSON Schemas."""
    import duckdb

    from roshni.ask.bundle import build_bundle
    from roshni.export.build import build_export, validate_export
    from roshni.export.build import write_schemas as write_schema_files
    from roshni.export.health import build_health
    from roshni.paths import DATA_DIR, REPO_ROOT

    if write_schemas:
        for p in write_schema_files():
            typer.echo(f"schema {p}")
    out = out or DATA_DIR / "export" / "v1"
    # Latest week; within it prefer the LLM-narrated report over the template one.
    reports = sorted(
        (DATA_DIR / "reports").glob("equity-*-*.json"),
        key=lambda p: (p.stem.rsplit("-", 1)[0], p.stem.endswith("-llm")),
    )
    con = duckdb.connect(str(db or DATA_DIR / "roshni.duckdb"), read_only=True)
    try:
        health = build_health(
            con,
            DATA_DIR / "parsed",
            REPO_ROOT / "dbt" / "target" / "run_results.json",
            store=snapshots,
            repo=github_repo,
            previous_url=previous_health,
        )
        counts = build_export(con, out, reports[-1] if reports else None, health)
    finally:
        con.close()
    for name, status in validate_export(out).items():
        size = (out / f"{name}.json").stat().st_size
        typer.echo(f"{name:18} records={counts[name]:6} bytes={size:9,} schema={status}")
    con = duckdb.connect(str(db or DATA_DIR / "roshni.duckdb"), read_only=True)
    try:
        ctx = build_bundle(con, out / "ask")
    finally:
        con.close()
    size = sum(f.stat().st_size for f in (out / "ask").iterdir())
    typer.echo(f"ask/ (Ask Roshni bundle) tables={len(ctx['tables'])} bytes={size:,}")


@app.command()
def ask(
    question: str = typer.Argument(..., help="A question about schedules, e.g. 'Which IBC areas…'"),
    model: str = typer.Option(None, help="Pin one 'provider/model', e.g. groq/qwen/qwen3.8-27b."),
    as_json: bool = typer.Option(False, "--json", help="Print JSON (answer, SQL, rows, usage)."),
    show_sql: bool = typer.Option(True, help="Print the SQL that produced the answer."),
    db: Path = typer.Option(None, help="Warehouse DuckDB (default: data/roshni.duckdb)."),
) -> None:
    """Ask Roshni in plain language: guarded SQL over the semantic layer, validated answer."""
    import json
    import sys

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # model text may hold any char

    from roshni.ask import engine, sqlguard
    from roshni.llm.chain import ChainConfig

    cfg = ChainConfig.load()
    if model:
        cfg = cfg.pinned(model)
    con = sqlguard.connect(db or engine.default_db())
    try:
        res = engine.ask(question, con, cfg)
    finally:
        con.close()
    if as_json:
        typer.echo(json.dumps(res.to_json(), default=str, indent=2, ensure_ascii=False))
        return
    typer.echo(f"[{res.status}] {res.answer or res.reason}")
    if res.rows:
        widths = [
            min(32, max(len(c), *(len(r[i]) for r in res.rows[:20])))
            for i, c in enumerate(res.columns)
        ]
        cells = zip(res.columns, widths, strict=True)
        typer.echo("  " + "  ".join(c[:w].ljust(w) for c, w in cells))
        for r in res.rows[:20]:
            typer.echo("  " + "  ".join(v[:w].ljust(w) for v, w in zip(r, widths, strict=True)))
        if len(res.rows) > 20:
            typer.echo(f"  ... {len(res.rows) - 20} more rows (use --json)")
    for c in res.caveats:
        typer.echo(f"  note: {c}")
    if show_sql and res.sql:
        typer.echo(f"  sql: {res.sql}")
    used = sorted(
        {a["provider"] + "/" + a["model"] for a in res.attempts if a["outcome"] == "accepted"}
    )
    typer.echo(
        f"  usage: {res.tokens} tokens, {res.latency_s}s, guard={res.guard}, "
        f"models={used}, narrated_by={res.narrated_by}"
    )


@app.command("ask-eval")
def ask_eval(
    model: list[str] = typer.Option(
        None, help="'provider/model' to score (repeatable; default: every model in llm.yml)."
    ),
    only: list[str] = typer.Option(None, help="Golden item ids to run (default: all)."),
    pause: float = typer.Option(8.0, help="Seconds between questions (free-plan token limits)."),
    out: Path = typer.Option(None, help="Output folder (default: data/reports)."),
    db: Path = typer.Option(None, help="Warehouse DuckDB (default: data/roshni.duckdb)."),
    main: bool = typer.Option(False, "--main", help="Score only the chain's first model."),
    record: bool = typer.Option(
        False, "--record", help="Also update evals/ask_roshni.json (shown on /health/)."
    ),
) -> None:
    """Score models on the Ask Roshni golden set: accuracy, refusals, guard, tokens, latency."""
    import sys

    from roshni.ask import engine, evaluate, semantic, sqlguard
    from roshni.llm.chain import ChainConfig
    from roshni.paths import DATA_DIR

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    cfg = ChainConfig.load()
    cfg.max_wait_s = 65  # wait out a per-minute limit instead of failing over during an eval
    items = [i for i in evaluate.load_items() if not only or i["id"] in only]
    layer = semantic.load()
    con = sqlguard.connect(db or engine.default_db())
    scores = []
    try:
        for m in model or (cfg.labels()[:1] if main else cfg.labels()):
            typer.echo(f"== {m}")
            scores.append(evaluate.evaluate(con, cfg, m, items, layer, pause, typer.echo))
    finally:
        con.close()
    md, js = evaluate.write(scores, out or DATA_DIR / "reports")
    typer.echo(md.read_text(encoding="utf-8"))
    typer.echo(f"wrote {md}\nwrote {js}")
    if record:
        rec, lines = evaluate.record(scores)
        typer.echo(f"updated {rec}")
        _eval_notice("ask-eval", lines)


def _eval_notice(name: str, lines: list[str]) -> None:
    """A weekly score below its floor or below the model's last run: a notice issue entry."""
    if lines:
        typer.echo("\n".join(lines))
        _notice(name, [f"Weekly eval regression (`roshni {name} --record`):", *lines])


@app.command()
def heal(
    snapshots: Path = typer.Option(
        Path("data/snapshots"), help="Snapshot store with raw_snapshots.csv (e.g. store)."
    ),
    apply: bool = typer.Option(False, "--apply", help="Write accepted aliases to config."),
    model: str = typer.Option(None, help="Pin one 'provider/model'."),
    all_versions: bool = typer.Option(
        False, "--all", help="Check every stored version (default: the newest per item)."
    ),
) -> None:
    """Detect IESCO maintenance-workbook header drift and heal it with gated, learned aliases."""
    import sys

    from roshni.heal import headers as h
    from roshni.llm.chain import ChainConfig
    from roshni.parsers import iesco_maintenance as im
    from roshni.paths import DATA_DIR

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    workbooks = h.stored_workbooks(snapshots)
    if not workbooks:
        typer.echo(f"no maintenance workbooks in {snapshots}")
        return
    newest = list({w.item: w for w in workbooks}.values())
    targets = workbooks if all_versions else newest
    cfg = ChainConfig.load()
    if model:
        cfg = cfg.pinned(model)
    corpus = h.Corpus(workbooks, im.load_aliases())
    results = [h.heal(t, cfg, corpus) for t in targets]
    typer.echo(f"checked {len(targets)} workbook(s); drifted: "
               f"{sum(r.status != 'healthy' for r in results)}")  # fmt: skip
    lines = h.report(results, typer.echo)
    added = 0
    if apply:
        added = h.save_aliases(results)
        typer.echo(f"aliases added to config/parser_aliases.yml: {added}")
    h.write_status(results, added, DATA_DIR / "heal" / "status.json")
    if lines:
        _notice(
            "parser-healing",
            ["Parser header drift in IESCO maintenance workbooks (`roshni heal`):", *lines],
        )


@app.command("heal-eval")
def heal_eval(
    snapshots: Path = typer.Option(Path("data/snapshots"), help="Snapshot store."),
    model: list[str] = typer.Option(None, help="'provider/model' (repeatable; default: chain)."),
    scenario: list[str] = typer.Option(None, help="renamed | abbreviated | urdu (default: all)."),
    item: list[str] = typer.Option(None, help="Workbook items (default: newest of every item)."),
    out: Path = typer.Option(None, help="Output folder (default: data/reports)."),
    record: bool = typer.Option(
        False, "--record", help="Also update evals/parser_healing.json (shown on /health/)."
    ),
    main: bool = typer.Option(False, "--main", help="Score only the chain's first model."),
) -> None:
    """Chaos eval: rename real workbooks' headers, heal them, count exact recoveries per model."""
    import json
    import sys
    import tempfile
    from datetime import UTC, datetime

    from roshni.heal import headers as h
    from roshni.heal import simulate as sim
    from roshni.llm.chain import ChainConfig
    from roshni.paths import DATA_DIR

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    workbooks = h.stored_workbooks(snapshots)
    newest = [w for w in {w.item: w for w in workbooks}.values() if not item or w.item in item]
    cfg = ChainConfig.load()
    cfg.max_wait_s = 65
    corpus = h.Corpus(workbooks, {})  # no learned aliases: measure the healer alone
    summaries, cases_out = [], {}
    with tempfile.TemporaryDirectory() as tmp:
        for m in model or (cfg.labels()[:1] if main else cfg.labels()):
            typer.echo(f"== {m}")
            cases = []
            for wb in newest:
                for sc in scenario or list(sim.SCENARIOS):
                    c = sim.run_case(wb, sc, cfg.pinned(m), corpus, Path(tmp))
                    cases.append(c)
                    typer.echo(f"  {c.status:21} {wb.item:17} {sc:12} {c.tokens:5} tok "
                               f"{c.latency_s:5.2f}s {c.detail[:80]}")  # fmt: skip
            summaries.append(sim.summary(m, cases))
            cases_out[m] = [c.__dict__ for c in cases]
    folder = out or DATA_DIR / "reports"
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%MZ")
    path = folder / f"heal_eval_{stamp}.json"
    path.write_text(json.dumps({"summary": summaries, "cases": cases_out}, indent=2,
                               ensure_ascii=False), encoding="utf-8")  # fmt: skip
    for s in summaries:
        typer.echo(json.dumps(s))
    typer.echo(f"wrote {path}")
    if record:
        rec = sim.record(summaries, len(newest), scenario or list(sim.SCENARIOS))
        typer.echo(f"updated {rec}")
        _eval_notice("heal-eval", sim.regressions(rec))
