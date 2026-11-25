"""Ask Roshni: guard -> plan SQL -> check -> run (self-correct once) -> narrate -> validate.

Numbers never come from the LLM. The planner writes SQL; DuckDB computes the figures; the
narrator writes one to three sentences with {placeholders} for result cells, which are rendered
from the result and validated (no digits of its own, no causal or 'actual outage' wording).
If no narration passes, a fixed template is used. Caveats for every table touched, the row
count and the warehouse build time are always appended by code, never by the model.
"""

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import duckdb
import httpx

from roshni.ask import semantic, sqlguard
from roshni.llm.chain import Attempt, ChainConfig, complete, guard_score, parse_json
from roshni.narrate.validate import CAUSAL, NUMBER, NUMBER_WORDS, PLACEHOLDER

PKT = ZoneInfo("Asia/Karachi")
NOT_MEASURED = re.compile(
    r"(?i)(?<!not )\b(actual(ly)?|really|measured|real)\b"
    r"|\b(lost|losing|loses|lose)\s+(power|electricity|supply)\b"
    r"|\b(was|were|went|been)\s+(without power|dark|off)\b"
)
MAX_FACT_ROWS = 10
# Feedback for the planner's one corrected try (also used by the site's Worker via ask/bundle.py).
FEEDBACK_ERROR = "That query failed in DuckDB: {err}. Fix it."
FEEDBACK_EMPTY = (
    "That query returned no rows. Check every filter value against the listed "
    "Values for that column and try again; if the data truly has none, keep it."
)
FEEDBACK_GUARD = "That query was refused by the SQL guard: {problems}. Fix it."

PLANNER = """You translate questions about Pakistan electricity load-shedding SCHEDULES into one
DuckDB SELECT query over the tables below, and nothing else.
{context}

Reply with one JSON object only:
{{"answerable": true|false, "sql": "<one SELECT, or null>", "reason": "<one short sentence>"}}
- answerable=false (sql null) when the tables cannot answer it: measured/actual outages,
  forecasts, causes or motives, individual consumers, income or wealth, other countries.
- Use only listed tables and columns; no SELECT *; alias every computed column in snake_case.
- When aggregating, also return the number of rows behind each figure as `n`.
- Round averages and percentages to 1 decimal place. Limit to at most 20 rows unless asked."""

NARRATOR = """Write one to three short sentences answering the question from the query result.
Rules, all mandatory:
1. Never write a digit or a number word. Every value comes from the result as a placeholder:
   the fact id in curly braces, e.g. {r1_ibc} or {row_count}. Use only ids from the list.
2. Descriptive only: no causal language (because, due to, leads to, caused), no claims of
   unfairness or motives.
3. These are published schedules or reported figures, never measured or actual outages.
4. Plain text, no lists, no headings, no markdown table."""


@dataclass
class AskResult:
    question: str
    status: str  # answered | refused | blocked | failed
    answer: str = ""
    sql: str | None = None
    columns: list[str] = field(default_factory=list)
    rows: list[list] = field(default_factory=list)
    truncated: bool = False
    tables: list[str] = field(default_factory=list)
    caveats: list[str] = field(default_factory=list)
    reason: str = ""
    guard: float | None = None
    narrated_by: str = "template"
    attempts: list[dict] = field(default_factory=list)

    @property
    def tokens(self) -> int:
        return sum(a["tokens_in"] + a["tokens_out"] for a in self.attempts)

    @property
    def latency_s(self) -> float:
        return round(sum(a["latency_s"] for a in self.attempts), 3)

    def to_json(self) -> dict:
        return asdict(self) | {"tokens": self.tokens, "latency_s": self.latency_s}


def fmt(v) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):  # before int: bool is an int subclass and would print as 1
        return "true" if v else "false"
    if isinstance(v, float | Decimal):
        # Half-up on the decimal text (as DuckDB ROUND does): 10.25 -> 10.3, not 10.2.
        d = Decimal(str(v))
        q = Decimal("0.1") if abs(d) >= 1 or d == 0 else Decimal("0.01")
        return f"{d.quantize(q, rounding=ROUND_HALF_UP) + 0:,}"
    if isinstance(v, int):
        return f"{v:,}"
    if isinstance(v, datetime):
        return v.astimezone(PKT).strftime("%Y-%m-%d %H:%M PKT")
    return str(v)


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_") or "col"


def facts_from(res: sqlguard.Result) -> dict[str, str]:
    facts = {"row_count": fmt(len(res.rows))}
    for i, row in enumerate(res.rows[:MAX_FACT_ROWS], start=1):
        for c, v in zip(res.columns, row, strict=True):
            facts[f"r{i}_{_slug(c)}"] = fmt(v)
    return facts


def check_prose(text: str, facts: dict[str, str], question: str = "") -> list[str]:
    """Problems with a narration; numbers quoted from the question itself are allowed."""
    problems = []
    ids = PLACEHOLDER.findall(text)
    unknown = sorted({i for i in ids if i not in facts})
    if unknown:
        problems.append(f"unknown placeholders {unknown[:5]}")
    bare = PLACEHOLDER.sub("", text)
    for quoted in sorted(set(NUMBER.findall(question)), key=len, reverse=True):
        bare = bare.replace(quoted, "")
    if NUMBER.search(bare):
        problems.append("contains a number not taken from the result")
    allowed_words = {w.lower() for w in NUMBER_WORDS.findall(question)} | {"six", "twelve"}
    if any(w.lower() not in allowed_words for w in NUMBER_WORDS.findall(bare)):
        problems.append("contains a number word not in the question")
    if CAUSAL.search(text):
        problems.append("causal or accusatory wording")
    if NOT_MEASURED.search(text):
        problems.append("calls a schedule an actual/measured outage")
    if re.search(r"(?m)^\s*([#|*-]|\d+\.)", text):
        problems.append("lists, headings or tables are not allowed")
    if not ids:
        problems.append("no values from the result")
    return problems


def render(text: str, facts: dict[str, str]) -> str:
    return PLACEHOLDER.sub(lambda m: facts[m.group(1)], text).strip()


def _attempts(atts: list[Attempt], stage: str) -> list[dict]:
    return [asdict(a) | {"stage": stage} for a in atts]


def built_at(con: duckdb.DuckDBPyConnection) -> str | None:
    try:
        (ts,) = con.execute("select max(built_at) from mart_build_info").fetchone()
    except duckdb.Error:
        return None
    return fmt(ts) if ts else None


def ask(
    question: str,
    con: duckdb.DuckDBPyConnection,
    cfg: ChainConfig,
    layer: semantic.SemanticLayer | None = None,
    *,
    narrate: bool = True,
    transport: httpx.BaseTransport | None = None,
) -> AskResult:
    layer = layer or semantic.load()
    out = AskResult(question=question.strip(), status="failed")
    if not out.question or len(out.question) > 500:
        out.reason = "Questions must be 1 to 500 characters."
        return out

    # 1. Prompt-injection screen (skipped, and noted, when the guard model is unreachable).
    out.guard = guard_score(out.question, cfg, transport)
    if out.guard is not None and out.guard >= float(cfg.guard.get("threshold", 0.5)):
        out.status, out.reason = "blocked", "The question looks like a prompt-injection attempt."
        return out

    # 2. Plan: the reply must be JSON and its SQL must pass the guard, else the next model.
    system = PLANNER.format(context=layer.prompt_context(con))
    messages = [{"role": "system", "content": system}, {"role": "user", "content": out.question}]
    checked: dict = {}

    def plan_ok(text: str) -> list[str]:
        try:
            plan = parse_json(text)
        except (json.JSONDecodeError, ValueError):
            return ["reply is not JSON"]
        if not plan.get("answerable"):
            checked.clear()
            checked["refused"] = str(plan.get("reason") or "")
            return []
        c = sqlguard.check(str(plan.get("sql") or ""), layer)
        if not c.ok:
            return c.problems
        checked.clear()
        checked["c"] = c
        return []

    res = None
    for round_ in (1, 2):  # second round only after a DuckDB error, with the error as feedback
        comp = complete(messages, cfg, plan_ok, json_mode=True, transport=transport)
        out.attempts += _attempts(comp.attempts, f"plan{round_}")
        if comp.text is None:
            out.reason = "No model produced a valid, allowed query."
            return out
        if "refused" in checked:
            out.status, out.reason = "refused", checked["refused"] or "Not answerable from Roshni."
            return out
        c: sqlguard.Checked = checked["c"]
        out.sql, out.tables = c.sql, sorted(c.tables)
        try:
            res = sqlguard.run(con, c.sql)
        except duckdb.Error as e:
            err = str(e).splitlines()[0][:300]
            out.reason = f"Query failed: {err}"
            feedback = FEEDBACK_ERROR.format(err=err)
        else:
            if res.rows or round_ == 2:
                break
            # Empty result: usually a filter value in the wrong format. One corrected try.
            feedback = FEEDBACK_EMPTY
        messages += [
            {"role": "assistant", "content": comp.text},
            {"role": "user", "content": feedback},
        ]
    if res is None:
        return out

    out.columns, out.truncated = res.columns, res.truncated
    out.rows = [[fmt(v) for v in r] for r in res.rows]
    out.status, out.reason = "answered", ""

    # 3. Narration: placeholders only, validated; template otherwise.
    facts = facts_from(res)
    out.answer = render("The query returned {row_count} row(s).", facts)
    if narrate and res.rows:
        listing = "\n".join(f"{k} = {v}" for k, v in facts.items())
        comp = complete(
            [
                {"role": "system", "content": NARRATOR},
                {
                    "role": "user",
                    "content": f"Question: {out.question}\nColumns: {res.columns}\n"
                    f"Facts (id = value; write the id, never the value):\n{listing}",
                },
            ],
            cfg,
            lambda t: check_prose(t, facts, out.question),
            transport=transport,
        )
        out.attempts += _attempts(comp.attempts, "narrate")
        if comp.text is not None:
            prose = " ".join(render(comp.text, facts).split())
            out.answer, out.narrated_by = prose, comp.accepted.label

    # 4. Caveats, always from code.
    out.caveats = layer.caveats_for(set(out.tables))
    out.caveats.append(f"n = {len(res.rows)} result rows" + (" (capped)" if res.truncated else ""))
    if b := built_at(con):
        out.caveats.append(f"Warehouse built {b}.")
    return out


def default_db() -> Path:
    from roshni.paths import DATA_DIR

    return DATA_DIR / "roshni.duckdb"
