"""Benchmark the local DuckDB warehouse build (docs/benchmarks.md).

Scenarios, each on its own fresh DuckDB file in a temporary folder:

  overhead     `roshni build --command parse`: process start, dbt import and project parse,
               the fixed cost every build pays before any SQL runs;
  full         a full `roshni build` (seeds, models, tests) on the real parsed Parquet;
  incremental  build without the newest IESCO press release, then add that release back and
               rebuild only `fct_planned_shutdown` (the incremental model), then once more with
               nothing new; also `fct_planned_shutdown+` (the model and everything downstream);
  synthetic    a full build on synthetic data: the parsed Parquet replicated N times with new
               keys (default N = 1, 10, 100).

Every build runs `roshni build` in a child process. For each run the script records wall time,
the peak memory of that process (Windows: peak working set; elsewhere: max RSS from wait4),
the DuckDB file size and the row count of every model, seed and source view in the warehouse.
Results go to a JSON file (default: data/benchmarks/<timestamp>.json) and a short summary is
printed.

Real data and seeds are never written: inputs are copied to a temporary folder first, and dbt's
target folder is redirected there too (DBT_TARGET_PATH).

Usage:
  uv run --group bench python scripts/benchmark.py [--parsed DIR] [--factors 1,10,100]
                                                   [--only overhead,full,incremental,synthetic]
                                                   [--repeat N] [--keep]
                                                   [--timeout SECONDS] [--exclude DBT_EXPR]
"""

import argparse
import contextlib
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import psutil

from roshni.paths import DATA_DIR, REPO_ROOT

# Synthetic replication: copy k (k >= 1) of every row gets a new value in each listed key
# column, so replicas are new entities that still join to each other (copy k of a feeder joins
# copy k of its schedule) but not to the hand/LLM review seeds, which stay as they are.
# Integer keys are offset; string keys get a suffix "~k". Tables not listed (NEPRA reference
# tables, the K-Electric schedule-version summary) are fixed-size facts about documents, not
# per-entity rows, and are kept at 1x.
STRING_KEYS: dict[str, list[str]] = {
    "iesco_feeder": ["feeder_code", "feeder_code_raw", "feeder_name"],
    "iesco_schedule_slot": ["feeder_code"],
    "iesco_maintenance_window": ["feeder_code", "feeder_code_raw", "feeder_name"],
    "iesco_press_release_window": ["feeder_name"],
    "kelectric_feeder_list": ["feeder_name", "feeder_name_norm"],
    "kelectric_schedule": ["feeder_name", "feeder_name_norm"],
    "kelectric_schedule_cycle": ["feeder_name_norm"],
    "news_headline": ["title", "link"],
    "pbs_rural_population": ["area_key", "name"],
    "pbs_rural_housing": ["area_key", "name"],
    "pbs_urban_population": ["area_key", "name"],
    "pbs_urban_housing": ["area_key", "name"],
}
# Integer keys made unique per copy: offset by k * INT_OFFSET.
INT_KEYS: dict[str, list[str]] = {
    "iesco_feeder": ["sheet_row"],
    "iesco_schedule_slot": ["sheet_row"],
    "iesco_maintenance_window": ["sheet_row"],
    "iesco_press_release_window": ["seq"],
    "kelectric_feeder_list": ["serial"],
}
INT_OFFSET = 10_000_000
TIMEOUT: float | None = None  # seconds per build; set by --timeout
EXCLUDE: str | None = None  # dbt --exclude for synthetic builds; set by --exclude


def machine_spec() -> dict:
    import dbt.version

    spec = {
        "os": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "physical_cores": psutil.cpu_count(logical=False),
        "logical_cores": psutil.cpu_count(logical=True),
        "ram_bytes": psutil.virtual_memory().total,
        "python": platform.python_version(),
        "duckdb": duckdb.__version__,
        "dbt_core": dbt.version.__version__,
    }
    if sys.platform == "win32":
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_Processor).Name"],
            capture_output=True,
            text=True,
        )
        spec["cpu_name"] = out.stdout.strip()
        disk = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "(Get-PhysicalDisk | Select-Object -First 1).MediaType"],
            capture_output=True, text=True,
        )  # fmt: skip
        spec["disk_media"] = disk.stdout.strip()
    elif Path("/proc/cpuinfo").exists():
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                spec["cpu_name"] = line.split(":", 1)[1].strip()
                break
    return spec


def run_build(db: Path, parsed: Path, target_dir: Path, log: Path, *extra: str) -> dict:
    """Run `roshni build` in a child process; return wall time, peak memory, exit code."""
    env = dict(os.environ, DBT_TARGET_PATH=str(target_dir), PYTHONIOENCODING="utf-8")
    env["DBT_SEND_ANONYMOUS_USAGE_STATS"] = "False"  # no network call inside the timing
    cmd = [sys.executable, "-c", "from roshni.cli import app; app()", "build",
           "--parsed", str(parsed), "--db", str(db), *extra]  # fmt: skip
    # Other work on the machine skews timings; record how busy the CPU was just before.
    busy = psutil.cpu_percent(interval=1.0)
    started_utc = datetime.now(UTC).isoformat(timespec="seconds")
    with log.open("w", encoding="utf-8") as out:
        start = time.perf_counter()
        proc = subprocess.Popen(cmd, stdout=out, stderr=subprocess.STDOUT, env=env, cwd=REPO_ROOT)
        peak = 0
        timed_out = False
        root = psutil.Process(proc.pid)
        peaks: dict[int, int] = {}
        # The poll runs every 50 ms; a much longer gap means the machine slept or suspended the
        # process, and the timing is not valid.
        last, max_gap = start, 0.0
        while True:
            now = time.perf_counter()
            max_gap, last = max(max_gap, now - last), now
            if sys.platform == "win32":
                if proc.poll() is not None:
                    code = proc.returncode
                    break
                # A uv venv's python.exe is a launcher that starts the real interpreter as a
                # child, so watch the whole process tree. peak_wset is the OS-kept peak working
                # set of each process; the largest one is the interpreter running dbt and DuckDB.
                with contextlib.suppress(psutil.Error):
                    for p in [root, *root.children(recursive=True)]:
                        with contextlib.suppress(psutil.Error):
                            peaks[p.pid] = max(peaks.get(p.pid, 0), p.memory_info().peak_wset)
            else:
                pid, status, usage = os.wait4(proc.pid, os.WNOHANG)
                if pid:
                    proc.returncode = code = os.waitstatus_to_exitcode(status)
                    peaks[pid] = usage.ru_maxrss * (1 if sys.platform == "darwin" else 1024)
                    break
            if TIMEOUT and time.perf_counter() - start > TIMEOUT:
                timed_out = True
                for p in [*root.children(recursive=True), root]:
                    with contextlib.suppress(psutil.Error):
                        p.kill()
                proc.wait()
                code = None
                break
            time.sleep(0.05)
        peak = max(peaks.values(), default=0)
        wall = time.perf_counter() - start
    text = log.read_text(encoding="utf-8", errors="replace")
    done = [ln for ln in text.splitlines() if "Done. PASS=" in ln]
    started = re.findall(r"START \S+(?: \S+)* model main\.(\w+)", text)
    finished = set(
        re.findall(r"(?:OK created|ERROR creating) \S+(?: \S+)* model main\.(\w+)", text)
    )
    return {
        "args": list(extra),
        "started_utc": started_utc,
        "finished_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "exit_code": code,
        "timed_out": timed_out,
        "longest_poll_gap_seconds": round(max_gap, 3),
        "models_running_when_stopped": sorted(set(started) - finished) if timed_out else [],
        "wall_seconds": round(wall, 3),
        "peak_memory_bytes": peak,
        "cpu_busy_percent_before": busy,
        "dbt_summary": done[-1].split("Done. ", 1)[1].strip() if done else None,
        "log": str(log),
        **node_timings(target_dir / "run_results.json"),
    }


def node_timings(path: Path) -> dict:
    """Per-node execution time from dbt's run_results.json (excludes dbt startup and parse)."""
    if not path.exists():
        return {}
    res = json.loads(path.read_text(encoding="utf-8"))
    nodes = {r["unique_id"]: round(r["execution_time"], 3) for r in res["results"]}
    by_kind: dict[str, float] = {}
    for uid, t in nodes.items():
        kind = uid.split(".", 1)[0]
        by_kind[kind] = round(by_kind.get(kind, 0) + t, 3)
    return {
        "dbt_elapsed_seconds": round(res.get("elapsed_time", 0), 3),
        "node_seconds_by_kind": by_kind,
        "node_seconds": nodes,
    }


def warehouse_stats(db: Path, views: bool = True) -> dict:
    """File size and row counts. views=False skips views: counting a view re-runs its query,
    which at large synthetic factors can take far longer than the build itself."""
    con = duckdb.connect(str(db), read_only=True)
    try:
        rels = con.execute(
            "select table_name, table_type from information_schema.tables "
            "where table_schema = 'main' order by table_name"
        ).fetchall()
        rows = {}
        for name, kind in rels:
            if kind == "VIEW" and not views:
                rows[name] = {"type": "view", "rows": None}
                continue
            n = con.execute(f'select count(*) from "{name}"').fetchone()[0]
            rows[name] = {"type": "view" if kind == "VIEW" else "table", "rows": n}
    finally:
        con.close()
    return {"duckdb_file_bytes": db.stat().st_size, "relations": rows}


def copy_parsed(src: Path, dst: Path) -> None:
    dst.mkdir(parents=True)
    for f in src.glob("*.parquet"):
        shutil.copy2(f, dst / f.name)


def replicate(src: Path, dst: Path, factor: int) -> dict:
    """Write each parsed table replicated `factor` times with new keys; return row counts."""
    dst.mkdir(parents=True)
    counts = {}
    con = duckdb.connect()
    try:
        for f in sorted(src.glob("*.parquet")):
            name = f.stem
            desc = con.execute(f"describe select * from '{f.as_posix()}'").fetchall()
            cols = [r[0] for r in desc]
            if factor == 1 or name not in STRING_KEYS and name not in INT_KEYS:
                shutil.copy2(f, dst / f.name)
            else:
                exprs = []
                for c in cols:
                    if c in STRING_KEYS.get(name, []):
                        exprs.append(
                            f"case when k = 0 then {c} else {c} || '~' || cast(k as varchar) end"
                            f' as "{c}"'
                        )
                    elif c in INT_KEYS.get(name, []):
                        exprs.append(f'{c} + k * {INT_OFFSET} as "{c}"')
                    else:
                        exprs.append(f'"{c}"')
                con.execute(
                    f"copy (select {', '.join(exprs)} from '{f.as_posix()}', "
                    f"range({factor}) t(k) order by k) to '{(dst / f.name).as_posix()}' "
                    "(format parquet)"
                )
            counts[name] = con.execute(
                f"select count(*) from '{(dst / f.name).as_posix()}'"
            ).fetchone()[0]
    finally:
        con.close()
    return counts


def newest_release(parsed: Path) -> dict:
    f = (parsed / "iesco_press_release_window.parquet").as_posix()
    sha, release_no, fetched, n = duckdb.sql(
        f"select source_sha256, any_value(release_no), max(fetched_at), count(*) from '{f}' "
        "group by source_sha256 order by max(fetched_at) desc, source_sha256 limit 1"
    ).fetchone()
    return {"source_sha256": sha, "release_no": release_no, "fetched_at": str(fetched), "rows": n}


def scenario_overhead(parsed: Path, work: Path, repeat: int) -> list[dict]:
    """`roshni build --command parse`: interpreter start, dbt import and project parse only."""
    runs = []
    for i in range(repeat):
        d = work / f"overhead-{i}"
        d.mkdir(parents=True)
        r = run_build(d / "roshni.duckdb", parsed, d / "target", d / "parse.log",
                      "--command", "parse")  # fmt: skip
        runs.append(r)
        print(f"overhead[{i}]: {r['wall_seconds']} s")
    return runs


def scenario_full(parsed: Path, work: Path, repeat: int) -> list[dict]:
    runs = []
    for i in range(repeat):
        d = work / f"full-{i}"
        copy_parsed(parsed, d / "parsed")
        db = d / "roshni.duckdb"
        r = run_build(db, d / "parsed", d / "target", d / "build.log")
        r |= warehouse_stats(db) if r["exit_code"] == 0 else {}
        runs.append(r)
        print(f"full[{i}]: {r['wall_seconds']} s, peak {r['peak_memory_bytes'] / 2**20:.0f} MiB, "
              f"{r['dbt_summary']}")  # fmt: skip
    return runs


def scenario_incremental(parsed: Path, work: Path, repeat: int) -> dict:
    new = newest_release(parsed)
    out: dict = {"new_release": new, "runs": []}
    pr = "iesco_press_release_window.parquet"
    for i in range(repeat):
        d = work / f"incremental-{i}"
        copy_parsed(parsed, d / "parsed")
        # Base warehouse: everything except the newest release.
        duckdb.sql(
            f"copy (select * from '{(parsed / pr).as_posix()}' "
            f"where source_sha256 <> '{new['source_sha256']}') "
            f"to '{(d / 'parsed' / pr).as_posix()}' (format parquet)"
        )
        db = d / "roshni.duckdb"
        base = run_build(db, d / "parsed", d / "target", d / "base.log")
        base_rows = warehouse_stats(db)["relations"]["fct_planned_shutdown"]["rows"]
        # The new release arrives.
        shutil.copy2(parsed / pr, d / "parsed" / pr)
        sel = ["--select", "fct_planned_shutdown"]
        inc = run_build(db, d / "parsed", d / "target", d / "incremental.log", *sel)
        inc_rows = warehouse_stats(db)["relations"]["fct_planned_shutdown"]["rows"]
        noop = run_build(db, d / "parsed", d / "target", d / "noop.log", *sel)
        down = run_build(db, d / "parsed", d / "target", d / "downstream.log", "--select",
                         "fct_planned_shutdown+")  # fmt: skip
        stats = warehouse_stats(db)
        run = {
            "base_full_build": base,
            "fct_rows_before": base_rows,
            "incremental_new_release": inc,
            "fct_rows_after": inc_rows,
            "incremental_nothing_new": noop,
            "model_and_downstream": down,
            "duckdb_file_bytes": stats["duckdb_file_bytes"],
        }
        out["runs"].append(run)
        print(f"incremental[{i}]: base {base['wall_seconds']} s; +release {inc['wall_seconds']} s "
              f"({base_rows} -> {inc_rows} rows); nothing new {noop['wall_seconds']} s; "
              f"model+downstream {down['wall_seconds']} s")  # fmt: skip
    return out


def scenario_synthetic(parsed: Path, work: Path, factors: list[int], repeat: int) -> list[dict]:
    results = []
    for factor in factors:
        d = work / f"synthetic-{factor}x"
        try:
            inputs = replicate(parsed, d / "parsed", factor)
        except (duckdb.OutOfMemoryException, MemoryError) as e:
            results.append({"factor": factor, "error": f"replication failed: {e}"})
            print(f"synthetic {factor}x: replication failed: {e}")
            continue
        entry: dict = {"factor": factor, "input_rows": inputs, "runs": []}
        for i in range(repeat):
            db = d / f"roshni-{i}.duckdb"
            ex = ["--exclude", EXCLUDE] if EXCLUDE else []
            r = run_build(db, d / "parsed", d / f"target-{i}", d / f"build-{i}.log", *ex)
            if db.exists():
                try:
                    r |= warehouse_stats(db, views=factor <= 10)
                except duckdb.Error as e:
                    r["stats_error"] = str(e)
            entry["runs"].append(r)
            print(f"synthetic {factor}x[{i}]: {r['wall_seconds']} s, "
                  f"peak {r['peak_memory_bytes'] / 2**20:.0f} MiB, exit {r['exit_code']}, "
                  f"{r['dbt_summary']}")  # fmt: skip
            if i + 1 < repeat:
                db.unlink(missing_ok=True)
        results.append(entry)
    return results


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--parsed", type=Path, default=DATA_DIR / "parsed")
    ap.add_argument("--factors", default="1,10,100")
    ap.add_argument("--only", default="overhead,full,incremental,synthetic")
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--work", type=Path, default=None, help="Work folder (default: a temp dir).")
    ap.add_argument("--keep", action="store_true", help="Keep the work folder.")
    ap.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="Stop a build after this many seconds and record it as timed out.",
    )
    ap.add_argument("--exclude", default=None,
                    help="dbt --exclude expression for the synthetic builds.")  # fmt: skip
    a = ap.parse_args()
    global TIMEOUT, EXCLUDE
    TIMEOUT, EXCLUDE = a.timeout, a.exclude

    parsed = a.parsed.resolve()
    if not any(parsed.glob("*.parquet")):
        print(f"no parsed Parquet in {parsed}: run `uv run roshni parse` first", file=sys.stderr)
        return 2
    only = set(a.only.split(","))
    work = Path(a.work or tempfile.mkdtemp(prefix="roshni-bench-")).resolve()
    work.mkdir(parents=True, exist_ok=True)
    started = datetime.now(UTC)
    report: dict = {
        "started_utc": started.isoformat(timespec="seconds"),
        "machine": machine_spec(),
        "git_commit": subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True
        ).stdout.strip(),  # fmt: skip
        "parsed_dir": str(parsed),
        "parsed_inputs": {
            f.stem: {
                "rows": duckdb.sql(f"select count(*) from '{f.as_posix()}'").fetchone()[0],
                "sha256": hashlib.sha256(f.read_bytes()).hexdigest(),
            }
            for f in sorted(parsed.glob("*.parquet"))
        },  # fmt: skip
        "work_dir": str(work),
        "timeout_seconds": a.timeout,
        "synthetic_exclude": a.exclude,
    }
    try:
        if "overhead" in only:
            report["overhead"] = scenario_overhead(parsed, work, a.repeat)
        if "full" in only:
            report["full"] = scenario_full(parsed, work, a.repeat)
        if "incremental" in only:
            report["incremental"] = scenario_incremental(parsed, work, a.repeat)
        if "synthetic" in only:
            factors = [int(x) for x in a.factors.split(",")]
            report["synthetic"] = scenario_synthetic(parsed, work, factors, a.repeat)
    finally:
        report["finished_utc"] = datetime.now(UTC).isoformat(timespec="seconds")
        out = a.out or DATA_DIR / "benchmarks" / f"{started:%Y%m%dT%H%M%SZ}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"results: {out}")
        if not a.keep:
            shutil.rmtree(work, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
