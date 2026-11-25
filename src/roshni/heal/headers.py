"""Heal IESCO maintenance-workbook header drift (docs/parser-healing.md).

1. Detect: a workbook drifts when no header row is found, or when more than DRIFT_QUARANTINE of
   its rows are quarantined (with at least MIN_QUARANTINED rows).
2. Propose: an LLM sees the top rows (cell texts with column numbers) and a few rows below, and
   maps columns to the parser's known fields. It may only choose listed fields and existing
   columns; anything else is rejected before the gate.
3. Gate (deterministic): the proposal becomes header aliases (exact header text -> field) and is
   accepted only if (a) the drifted workbook now finds its header, parses rows, quarantines at
   most DRIFT_QUARANTINE and fewer than before, and (b) every other stored workbook parses
   exactly as it did without the new aliases (no regressions).
4. Learn: accepted aliases are appended to config/parser_aliases.yml with who decided and the
   evidence; rows read through one carry `header_alias_<field>`.
The LLM never writes a row: it only names which column holds which field.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path

import yaml

from roshni.llm.chain import ChainConfig, complete, parse_json
from roshni.parsers import iesco_maintenance as im
from roshni.parsers.common import ParseResult

DRIFT_QUARANTINE = 0.25
MIN_QUARANTINED = 10
TOP_ROWS = 8
SAMPLE_ROWS = 4
MAX_CELL = 40

FIELD_HELP = {
    "serial": "row serial number (Sr. No.)",
    "disco": "distribution company name, e.g. IESCO",
    "circle": "IESCO circle, e.g. Islamabad, Attock",
    "subdivision": "sub-division name",
    "division": "division name",
    "feeder_code": "numeric feeder code (often 5-6 digits)",
    "feeder_name": "feeder name",
    "grid": "grid station name",
    "date": "date of the planned shutdown",
    "start": "start time of the shutdown window (From)",
    "end": "end time of the shutdown window (To)",
    "purpose": "purpose of the shutdown, e.g. Annual Maintenance",
    "area": "area affected",
    "remarks": "remarks",
}

SYSTEM = """You repair a spreadsheet parser. A planned-shutdown schedule changed its column
headers, so the parser no longer recognises them. Map each column to one of the parser's known
fields, or "ignore". You never read or change data values; you only say which column is which.

Known fields: {fields}
Required: date, start, end, and feeder_name or feeder_code.
Start and end times are sometimes two columns under one merged heading (e.g. TIME), with From/To
labels in the row below; then give header_row as the row with the main headings.

Reply with one JSON object only:
{{"header_row": <row number as shown>, "columns": {{"<column number>": "<field or ignore>"}},
  "reason": "<one short sentence>"}}
Use each field at most once. Only use column numbers that appear in the rows shown."""


@dataclass
class Health:
    rows: int
    quarantined: int
    header_found: bool

    @property
    def quarantine_rate(self) -> float:
        total = self.rows + self.quarantined
        return self.quarantined / total if total else 1.0

    @property
    def drifted(self) -> bool:
        if not self.header_found:
            return True
        return self.quarantine_rate > DRIFT_QUARANTINE and self.quarantined >= MIN_QUARANTINED

    def __str__(self) -> str:
        head = "header found" if self.header_found else "NO HEADER"
        return (
            f"{head}, {self.rows} rows, {self.quarantined} quarantined ({self.quarantine_rate:.0%})"
        )


def health(res: ParseResult) -> Health:
    no_header = any(q.reason.startswith("no header row") for q in res.quarantine)
    return Health(len(res.rows), len(res.quarantine), not no_header)


def _text(v: object) -> str:
    s = im._clean(v) or ""
    return s[:MAX_CELL]


def sheet_preview(path: Path) -> tuple[list[list[str]], str]:
    """(top rows as texts, prompt table): rows 1..TOP_ROWS+SAMPLE_ROWS, 1-based numbering."""
    import openpyxl

    wb = openpyxl.load_workbook(path, data_only=True)
    grid = im._unmerged(wb.worksheets[0])[: TOP_ROWS + SAMPLE_ROWS]
    rows = [[_text(c) for c in r] for r in grid]
    lines = []
    for i, r in enumerate(rows, start=1):
        cells, j = [], 0
        while j < len(r):  # merged cells repeat their text: show a run once, as [a-b]
            k = j
            while k + 1 < len(r) and r[k + 1] == r[j]:
                k += 1
            if r[j]:
                cells.append(f"[{j + 1}] {r[j]}" if k == j else f"[{j + 1}-{k + 1}] {r[j]}")
            j = k + 1
        lines.append(f"row {i}: " + (" | ".join(cells) if cells else "(blank)"))
    return rows, "\n".join(lines)


@dataclass
class Proposal:
    header_row: int  # 1-based
    columns: dict[int, str]  # 1-based column -> field
    reason: str = ""


def check_proposal(text: str, rows: list[list[str]]) -> tuple[Proposal | None, list[str]]:
    try:
        raw = parse_json(text)
        hr = int(raw["header_row"])
        cols = {int(k): str(v).strip() for k, v in dict(raw["columns"]).items()}
    except (json.JSONDecodeError, ValueError, KeyError, TypeError, AttributeError):
        return None, ["reply is not the requested JSON"]
    problems = []
    if not 1 <= hr <= min(TOP_ROWS, len(rows)):
        problems.append(f"header_row {hr} outside rows 1-{min(TOP_ROWS, len(rows))}")
    width = max((len(r) for r in rows), default=0)
    used = [f for f in cols.values() if f != "ignore"]
    for c, f in cols.items():
        if not 1 <= c <= width:
            problems.append(f"column {c} does not exist")
        if f != "ignore" and f not in im.FIELDS:
            problems.append(f"unknown field {f!r}")
    dupes = sorted({f for f in used if used.count(f) > 1})
    if dupes:
        problems.append(f"fields used twice: {dupes}")
    if not {"date", "start", "end"} <= set(used) or not {"feeder_name", "feeder_code"} & set(used):
        problems.append("required fields missing (date, start, end, feeder_name/feeder_code)")
    if problems:
        return None, problems
    return Proposal(
        hr, {c: f for c, f in cols.items() if f != "ignore"}, str(raw.get("reason", ""))
    ), []


def aliases_from(p: Proposal, rows: list[list[str]], known: dict[str, str]) -> dict[str, str]:
    """Header texts -> field for the proposal. A column's text is taken from the header row, or,
    for start/end under a merged heading, from the row below. Texts the parser already maps to
    that field (by alias or regex) are left out; a text needed for two fields is refused."""
    out: dict[str, str] = {}
    head = rows[p.header_row - 1]
    below = rows[p.header_row] if p.header_row < len(rows) else []
    for c, f in sorted(p.columns.items()):
        text = head[c - 1] if c - 1 < len(head) else ""
        label = below[c - 1] if c - 1 < len(below) else ""
        neighbours = [head[k] for k in (c - 2, c) if 0 <= k < len(head)]
        if f in ("start", "end") and (not text or text in neighbours):
            if label and im.parse_time(label) is None and not im.parse_date(label)[0]:
                text = label  # From/To labels under a merged heading
            elif f == "end" and p.columns.get(c - 1) == "start":
                continue  # one merged heading over start and end: the parser pairs them
        if not text:
            continue
        key = im.header_key(text)
        if known.get(key) == f or _regex_field(text) == f:
            continue
        if out.get(key, f) != f:
            return {}
        out[key] = f
    return out


def _regex_field(text: str) -> str | None:
    for name, rx in im.HEADERS:
        if rx.search(text):
            return name
    return None


def _fingerprint(res: ParseResult) -> tuple:
    rows = tuple(
        tuple(sorted(r.model_dump(exclude={"source_file", "source_sha256", "fetched_at"}).items()))
        for r in res.rows
    )
    return rows, tuple(sorted((q.location, q.reason) for q in res.quarantine))


@dataclass
class Workbook:
    path: Path
    item: str


def stored_workbooks(store: Path) -> list[Workbook]:
    """Every distinct maintenance workbook in a snapshot store, oldest first."""
    import csv

    log = store / "raw_snapshots.csv"
    if not log.exists():
        return []
    seen: set[str] = set()
    out = []
    with log.open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            ok = r["source"] == "iesco_maintenance_xlsx" and r["changed"] == "true" and r["path"]
            if ok and r["sha256"] not in seen and (store / r["path"]).exists():
                seen.add(r["sha256"])
                out.append(Workbook(store / r["path"], r["item_key"]))
    return out


def _cell_texts(path: Path) -> frozenset[str]:
    import openpyxl

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    out = set()
    for row in wb.worksheets[0].iter_rows(values_only=True):
        out.update(im.header_key(t) for t in (im._clean(c) for c in row) if t)
    wb.close()
    return frozenset(out)


class Corpus:
    """Stored workbooks with their parse fingerprints under the known aliases, cached.

    An alias only acts where a cell's normalised text equals it exactly, so a workbook that
    contains none of a candidate's texts cannot change; only the others are re-parsed."""

    def __init__(self, workbooks: list[Workbook], known: dict[str, str]):
        self.workbooks, self.known = workbooks, known
        self._fp: dict[Path, tuple] = {}
        self._texts: dict[Path, frozenset[str]] = {}

    def texts(self, wb: Workbook) -> frozenset[str]:
        if wb.path not in self._texts:
            self._texts[wb.path] = _cell_texts(wb.path)
        return self._texts[wb.path]

    def fingerprint(self, wb: Workbook) -> tuple:
        if wb.path not in self._fp:
            self._fp[wb.path] = _fingerprint(im.parse_workbook(wb.path, wb.item, self.known))
        return self._fp[wb.path]

    def regressions(self, candidate: dict[str, str], skip: Path) -> list[str]:
        merged = {**self.known, **candidate}
        out = []
        for wb in self.workbooks:
            if wb.path == skip or not (set(candidate) & self.texts(wb)):
                continue
            if _fingerprint(im.parse_workbook(wb.path, wb.item, merged)) != self.fingerprint(wb):
                out.append(wb.path.name)
        return out


@dataclass
class GateResult:
    ok: bool
    before: Health
    after: Health | None = None
    problems: list[str] = field(default_factory=list)
    regressions: list[str] = field(default_factory=list)
    accepted: dict[str, str] = field(default_factory=dict)  # the aliases that passed
    dropped: dict[str, str] = field(default_factory=dict)  # optional aliases that regressed


REQUIRED_FIELDS = {"date", "start", "end", "feeder_name", "feeder_code"}


def gate(
    target: Workbook, candidate: dict[str, str], corpus: Corpus, before: Health | None = None
) -> GateResult:
    """Accept `candidate` if the target heals and no other stored workbook changes.

    When some aliases change other workbooks, those that name an optional field (a column the
    parser may never have read, e.g. a serial number) are dropped one by one and the rest is
    gated again; an alias for a required field that regresses fails the proposal."""
    known = corpus.known
    before = before or health(im.parse_workbook(target.path, target.item, known))
    if not candidate:
        return GateResult(False, before, problems=["no new header text to learn"])
    g = _gate_once(target, candidate, corpus, before)
    if g.ok or not g.regressions:
        return g
    offenders = {k: v for k, v in candidate.items() if corpus.regressions({k: v}, target.path)}
    if not offenders or REQUIRED_FIELDS & set(offenders.values()):
        return g
    reduced = {k: v for k, v in candidate.items() if k not in offenders}
    g2 = _gate_once(target, reduced, corpus, before)
    g2.dropped = offenders
    return g2


def _gate_once(
    target: Workbook, candidate: dict[str, str], corpus: Corpus, before: Health
) -> GateResult:
    known = corpus.known
    if not candidate:
        return GateResult(False, before, problems=["no new header text to learn"])
    res = im.parse_workbook(target.path, target.item, {**known, **candidate})
    after = health(res)
    g = GateResult(False, before, after)
    if not after.header_found:
        g.problems.append("header still not found")
    if not res.rows:
        g.problems.append("no rows parsed")
    if after.quarantine_rate > DRIFT_QUARANTINE:
        g.problems.append(f"quarantine {after.quarantine_rate:.0%} above {DRIFT_QUARANTINE:.0%}")
    if before.header_found and after.quarantine_rate >= before.quarantine_rate:
        g.problems.append("quarantine did not improve")
    if g.problems:
        return g
    g.regressions = corpus.regressions(candidate, target.path)
    if g.regressions:
        g.problems.append(f"changes {len(g.regressions)} other workbook(s)")
    g.ok = not g.problems
    g.accepted = candidate if g.ok else {}
    return g


@dataclass
class HealResult:
    workbook: Workbook
    before: Health
    status: str  # healthy | healed | failed
    aliases: dict[str, str] = field(default_factory=dict)
    after: Health | None = None
    model: str | None = None
    attempts: list[dict] = field(default_factory=list)
    reason: str = ""

    @property
    def tokens(self) -> int:
        return sum(a["tokens_in"] + a["tokens_out"] for a in self.attempts)

    @property
    def latency_s(self) -> float:
        return round(sum(a["latency_s"] for a in self.attempts), 3)


def heal(target: Workbook, cfg: ChainConfig, corpus: Corpus, transport=None) -> HealResult:
    """Detect drift in `target`; if drifted, walk the model chain until a proposal passes the
    gate. The gate runs inside the chain's check, so a rejected proposal moves to the next model."""
    known = corpus.known
    before = health(im.parse_workbook(target.path, target.item, known))
    out = HealResult(target, before, "healthy")
    if not before.drifted:
        return out
    rows, table = sheet_preview(target.path)
    fields = ", ".join(f"{k} ({v})" for k, v in FIELD_HELP.items())
    messages = [
        {"role": "system", "content": SYSTEM.format(fields=fields)},
        {"role": "user", "content": f"Parser status: {before}.\nTop of the sheet:\n{table}"},
    ]
    found: dict = {}

    def check(text: str) -> list[str]:
        p, problems = check_proposal(text, rows)
        if p is None:
            return problems
        cand = aliases_from(p, rows, known)
        g = gate(target, cand, corpus, before)
        if not g.ok:
            return g.problems + [f"regressions: {g.regressions[:3]}"] * bool(g.regressions)
        reason = p.reason + (f" (dropped, changed other workbooks: {g.dropped})" * bool(g.dropped))
        found.update(aliases=g.accepted, after=g.after, reason=reason)
        return []

    comp = complete(messages, cfg, check, json_mode=True, transport=transport)
    out.attempts = [a.__dict__ | {"stage": "heal"} for a in comp.attempts]
    if comp.text is None:
        out.status = "failed"
        out.reason = "; ".join(a["outcome"] for a in out.attempts)[:500]
        return out
    out.status, out.aliases, out.after = "healed", found["aliases"], found["after"]
    out.model, out.reason = comp.accepted.label, found["reason"]
    return out


def save_aliases(
    results: list[HealResult], path: Path = im.ALIASES_FILE, today: date | None = None
) -> int:
    """Append accepted aliases to config/parser_aliases.yml; returns how many were added."""
    data = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}
    data = data or {}
    entries = data.setdefault("iesco_maintenance", []) or []
    data["iesco_maintenance"] = entries
    have = {im.header_key(e["header"]) for e in entries}
    added = 0
    for r in results:
        if r.status != "healed":
            continue
        for text, f in sorted(r.aliases.items()):
            if text in have:
                continue
            entries.append(
                {
                    "header": text,
                    "field": f,
                    "added": str(today or date.today()),
                    "by": f"llm-heal {today or date.today()} {r.model}",
                    "evidence": f"{r.workbook.path.name}: {r.before} -> {r.after}; "
                    "all other stored workbooks unchanged",
                }
            )
            have.add(text)
            added += 1
    header = (
        path.read_text(encoding="utf-8").split("iesco_maintenance:")[0] if path.exists() else ""
    )
    body = yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=100)
    path.write_text(header + body, encoding="utf-8")
    return added


def write_status(
    results: list[HealResult], added: int, path: Path, now: datetime | None = None
) -> dict:
    """The check's outcome for the health page (export reads it; data/heal/status.json)."""
    status = {
        "checked_at": (now or datetime.now(UTC)).replace(microsecond=0).isoformat(),
        "workbooks": len(results),
        "drifted": sum(r.status != "healthy" for r in results),
        "healed": sum(r.status == "healed" for r in results),
        "aliases_added": added,
        "results": [{"item": r.workbook.item, "status": r.status} for r in results],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(status, indent=2), encoding="utf-8")
    return status


def report(results: list[HealResult], log: Callable[[str], None] = print) -> list[str]:
    lines = []
    for r in results:
        if r.status == "healthy":
            continue
        line = f"- {r.workbook.item} `{r.workbook.path.name}`: {r.status}; before: {r.before}"
        if r.status == "healed":
            pairs = ", ".join(f"'{t}' -> {f}" for t, f in r.aliases.items())
            line += f"; after: {r.after}; learned {pairs} ({r.model})"
        else:
            line += f"; {r.reason[:300]}"
        lines.append(line)
        log(line)
    return lines
