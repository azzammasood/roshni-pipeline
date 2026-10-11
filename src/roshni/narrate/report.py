"""Weekly equity report: facts from SQL, prose from the narrator (or template), all traceable."""

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import duckdb

from roshni.narrate import facts as facts_mod
from roshni.narrate.openrouter import NarratorConfig, narrate
from roshni.narrate.template import TEMPLATE
from roshni.narrate.validate import InvalidDraft, render


@dataclass
class Report:
    markdown: str
    data: dict
    engine: str


def build_report(
    con: duckdb.DuckDBPyConnection,
    engine: str = "auto",
    now: datetime | None = None,
    transport=None,
) -> Report:
    now = now or datetime.now(UTC)
    facts = facts_mod.collect(con)
    attempts: list[str] = []
    spent = 0.0
    draft, used = None, "template"
    key = os.environ.get("OPENROUTER_API_KEY")
    if engine == "openrouter" or (engine == "auto" and key):
        if not key:
            raise RuntimeError("OPENROUTER_API_KEY is not set")
        res = narrate(facts, NarratorConfig.load(), key, transport=transport)
        attempts, spent = res.attempts, res.spent_usd
        if res.draft is not None:
            draft, used = res.draft, f"openrouter:{res.model}"
    if draft is None:
        draft = TEMPLATE
    try:
        prose = render(draft, facts)
    except InvalidDraft as e:  # an accepted LLM draft that still fails after rendering
        attempts.append(f"{used}: failed final check ({e}); template used")
        prose, used = render(TEMPLATE, facts), "template"

    year, week, _ = now.isocalendar()
    lines = [
        f"# Roshni weekly equity report, {year}-W{week:02d}",
        "",
        f"Generated {now:%Y-%m-%d %H:%M} UTC. Narrative: {used}. Every number below comes from a "
        "named SQL query against the warehouse (appendix). Schedule data, not measured outages; "
        "shares are among listed K-Electric feeders only; statistics are descriptive.",
        "",
        prose,
        "",
        "## Facts",
        "",
        "| Fact | Value | Unit | Query |",
        "|---|---|---|---|",
        *[f"| `{f.id}` | {f.rendered()} | {f.unit} | `{f.query_id}` |" for f in facts],
        "",
        "## Appendix: queries",
        "",
    ]
    for qid, sql in facts_mod.QUERIES.items():
        lines += [f"**{qid}**", "```sql", " ".join(sql.split()), "```", ""]
    if attempts:
        lines += ["## Narrator log", "", *[f"- {a}" for a in attempts], ""]
    data = {
        "generated_at": now.isoformat(),
        "iso_week": f"{year}-W{week:02d}",
        "engine": used,
        "spent_usd": round(spent, 6),
        "narrative": prose,
        "facts": [
            {"id": f.id, "value": f.value, "unit": f.unit, "query_id": f.query_id} for f in facts
        ],
        "queries": facts_mod.QUERIES,
        "narrator_log": attempts,
    }
    return Report("\n".join(lines), data, used)


def write_report(report: Report, out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"equity-{report.data['iso_week']}"
    md, js = out_dir / f"{stem}.md", out_dir / f"{stem}.json"
    md.write_text(report.markdown, encoding="utf-8", newline="\n")
    js.write_text(json.dumps(report.data, default=str, indent=2), encoding="utf-8", newline="\n")
    return md, js
