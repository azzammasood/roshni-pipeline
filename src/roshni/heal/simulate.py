"""Chaos testing for the header healer: rename a real workbook's headers, then heal it.

Each scenario renames the headers of the fields the parser needs, in a copy of a stored
workbook, so the parser no longer recognises them (verified: the copy must drift). The healer
then gets one chance per model; a case counts as RECOVERED only if the healed parse equals the
original parse row for row (ignoring the `header_alias_*` flags and file provenance).
Nothing here writes config/parser_aliases.yml.
"""

import json
import shutil
import statistics
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import openpyxl

from roshni import evalrecord
from roshni.heal import headers as h
from roshni.llm.chain import ChainConfig
from roshni.parsers import iesco_maintenance as im
from roshni.paths import REPO_ROOT

# field -> new header text. Chosen so that no parser regex matches them.
SCENARIOS: dict[str, dict[str, str]] = {
    "renamed": {
        "date": "Shutdown Day",
        "start": "Begins",
        "end": "Ends",
        "feeder_name": "Feeder Title",
        "feeder_code": "Fdr Ref",
        "purpose": "Work Type",
    },
    "abbreviated": {
        "date": "Dt.",
        "start": "Fr.",
        "end": "Upto",
        "feeder_name": "Fdr.",
        "feeder_code": "Fdr No",
        "purpose": "Nature of Work",
    },
    "urdu": {
        "date": "تاریخ",
        "start": "شروع",
        "end": "اختتام",
        "feeder_name": "فیڈر کا نام",
        "feeder_code": "فیڈر نمبر",
        "purpose": "مقصد",
    },
}


def _write(ws, row: int, col: int, text: str) -> None:
    """Write to a cell, or to the top-left cell of the merged range that holds it (1-based)."""
    for rng in ws.merged_cells.ranges:
        if rng.min_row <= row <= rng.max_row and rng.min_col <= col <= rng.max_col:
            row, col = rng.min_row, rng.min_col
            break
    ws.cell(row=row, column=col).value = text


def mutate(src: Path, dst: Path, scenario: str) -> list[str]:
    """Copy `src` to `dst` with the scenario's headers; returns what was renamed."""
    shutil.copyfile(src, dst)
    wb = openpyxl.load_workbook(dst)
    ws = wb.worksheets[0]
    grid = im._unmerged(ws)
    head = im._header([tuple(r) for r in grid], {})
    if head is None:
        return []
    hi, cols, _ = head
    done = []
    for fld, new in SCENARIOS[scenario].items():
        if fld not in cols:
            continue
        c = cols[fld]
        # start/end labels may sit in the row under a merged TIME heading
        row = hi
        if fld in ("start", "end") and hi + 1 < len(grid) and c < len(grid[hi + 1]):
            below = im._clean(grid[hi + 1][c])
            if below and h._regex_field(below) == fld:
                row = hi + 1
        old = im._clean(grid[row][c])
        if old and old.upper() in ("TIME", "TIMING") and fld == "end":
            continue  # a lone TIME heading: renaming it once (for start) is enough
        _write(ws, row + 1, c + 1, new)
        done.append(f"{fld}: {old!r} -> {new!r}")
    wb.save(dst)
    return done


_ORIGINAL: dict[Path, tuple] = {}  # original parse per stored workbook (eval run cache)


def _comparable(res) -> tuple:
    rows = []
    for r in res.rows:
        d = r.model_dump(exclude={"source_file", "source_sha256", "fetched_at"})
        d["flags"] = ";".join(
            f for f in d["flags"].split(";") if f and not f.startswith("header_alias_")
        )
        rows.append(tuple(sorted(d.items())))
    return tuple(rows)


@dataclass
class Case:
    item: str
    workbook: str
    scenario: str
    status: str  # recovered | healed_but_different | failed | no_drift
    tokens: int = 0
    latency_s: float = 0.0
    model: str | None = None
    renamed: list[str] = field(default_factory=list)
    learned: dict[str, str] = field(default_factory=dict)
    detail: str = ""


def run_case(wb: h.Workbook, scenario: str, cfg: ChainConfig, corpus: h.Corpus, tmp: Path) -> Case:
    dst = tmp / f"{wb.item}-{scenario}.xlsx"
    renamed = mutate(wb.path, dst, scenario)
    case = Case(wb.item, wb.path.name, scenario, "no_drift", renamed=renamed)
    if wb.path not in _ORIGINAL:
        _ORIGINAL[wb.path] = _comparable(im.parse_workbook(wb.path, wb.item, corpus.known))
    original = _ORIGINAL[wb.path]
    res = h.heal(h.Workbook(dst, wb.item), cfg, corpus)
    case.tokens, case.latency_s, case.model = res.tokens, res.latency_s, res.model
    if res.status == "healthy":
        return case
    if res.status == "failed":
        case.status, case.detail = "failed", res.reason
        return case
    case.learned = res.aliases
    healed = _comparable(im.parse_workbook(dst, wb.item, {**corpus.known, **res.aliases}))
    case.status = "recovered" if healed == original else "healed_but_different"
    if healed != original:
        case.detail = f"{len(healed)} rows healed vs {len(original)} original"
    return case


def summary(model: str, cases: list[Case]) -> dict:
    drifted = [c for c in cases if c.status != "no_drift"]
    rec = sum(c.status == "recovered" for c in drifted)
    lat = [c.latency_s for c in drifted if c.tokens]
    return {
        "model": model,
        "cases": len(cases),
        "drifted": len(drifted),
        "recovered": rec,
        "recovered_pct": round(100 * rec / len(drifted), 1) if drifted else None,
        "healed_but_different": sum(c.status == "healed_but_different" for c in drifted),
        "failed": sum(c.status == "failed" for c in drifted),
        "tokens_total": sum(c.tokens for c in cases),
        "latency_mean_s": round(statistics.mean(lat), 2) if lat else None,
    }


EVAL_RECORD = REPO_ROOT / "evals" / "parser_healing.json"
FLOOR_PCT = 85.0  # a weekly recovery rate below this is posted as a notice


def record(
    summaries: list[dict],
    workbooks: int,
    scenarios: list[str],
    path: Path = EVAL_RECORD,
    today: date | None = None,
) -> Path:
    """Replace these models' rows in the committed eval record (other models are kept)."""
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"models": []}
    keep = {s["model"] for s in summaries}
    data["models"] = [r for r in data["models"] if r["model"] not in keep] + [
        {k: s[k] for k in ("model", "cases", "recovered", "healed_but_different", "failed",
                           "tokens_total", "latency_mean_s")}
        for s in summaries
    ]  # fmt: skip
    data["models"].sort(key=lambda r: (-r["recovered"], r["model"]))
    day = today or date.today()
    data.update(run_on=str(day), workbooks=workbooks, scenarios=scenarios)
    evalrecord.append(
        data, [evalrecord.point(day, s["model"], s["recovered"], s["cases"]) for s in summaries]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return path


def regressions(path: Path = EVAL_RECORD, today: date | None = None) -> list[str]:
    """Notice lines for this run (evalrecord.regressions over the record)."""
    data = json.loads(path.read_text(encoding="utf-8"))
    day = today or date.today()
    return evalrecord.regressions(data, day, FLOOR_PCT, "Parser-healing chaos test")
