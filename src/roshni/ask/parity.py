"""Parity cases for the TypeScript ports of the answer checks (Worker) and formatting (site).

`tests/fixtures/ask_parity.json` holds inputs with the outcome Python gives; the Worker's and
the site's tests assert the same outcomes, and `test_parity_file_matches_python` fails when the
Python rules change without regenerating it (`uv run python -m roshni.ask.parity`).
"""

import json
from decimal import Decimal
from pathlib import Path

from roshni.ask import engine
from roshni.paths import REPO_ROOT

PARITY_FILE = REPO_ROOT / "tests" / "fixtures" / "ask_parity.json"

FACTS = {"row_count": "2", "r1_ibc": "IBC - A", "r1_share_12h_pct": "90.0", "r2_n": "1,234"}
PROSE = [
    ("{r1_ibc} has the highest share at {r1_share_12h_pct}%.", ""),
    ("{r1_ibc} has 90% of feeders on the long schedule.", ""),
    ("{r1_ibc} is high because of losses.", ""),
    ("{r1_ibc} actually lost power most often.", ""),
    ("These are schedules, not measured outages: {r1_ibc}.", ""),
    ("{r1_ibc} is not actually dark.", ""),
    ("Feeders in {r1_ibc} were without power.", ""),
    ("Feeders in {r1_ibc} went dark at night.", ""),
    ("{r1_ibc} loses electricity daily.", ""),
    ("{r9_ibc} leads.", ""),
    ("Three areas lead, starting with {r1_ibc}.", ""),
    ("Twenty-one feeders, led by {r1_ibc}.", ""),
    ("A dozen feeders, led by {r1_ibc}.", ""),
    ("No values here.", ""),
    ("In 2024-25, the top five start with {r1_ibc}.",
     "Which five areas had the most hours in 2024-25?"),
    ("Six or twelve hours: {r1_ibc} has {r2_n}.", ""),
    ("- {r1_ibc}\n- {r2_n}", ""),
    ("1. {r1_ibc} leads", ""),
    ("## {r1_ibc}", ""),
    ("{r1_ibc} is unfair to the poor.", ""),
    ("{r1_ibc} is targeted.", ""),
    ("Schedules are driven by losses in {r1_ibc}.", ""),
    ("The result shows {r1_ibc} at {r1_share_12h_pct} and {r2_n} feeders.", ""),
    ("{r1_ibc} had 1,234.5 hours and {row_count} rows.", ""),
    ("{r1_ibc} REALLY leads.", ""),
]  # fmt: skip
FMT = [
    10.25, 2452.0, 0.125, 0.0, 1234, None, -3.45, 0.004, 99.95, 1_000_000, 0.5, -0.0, "IBC - A",
    True,
]  # fmt: skip
SLUG = ["share_12h_pct", "Share (12h) %", "n", "COUNT(*)", "  ", "Feeder-Name"]


def cases() -> dict:
    return {
        "facts": FACTS,
        "prose": [
            {"text": t, "question": q, "problems": engine.check_prose(t, FACTS, q)}
            for t, q in PROSE
        ],
        "fmt": [
            {
                "value": v,
                "decimal": isinstance(v, float),
                "shown": engine.fmt(Decimal(str(v)) if isinstance(v, float) else v),
            }
            for v in FMT
        ],
        "slug": [{"text": s, "slug": engine._slug(s)} for s in SLUG],
    }


def write(path: Path = PARITY_FILE) -> Path:
    path.write_text(json.dumps(cases(), indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    print(write())
