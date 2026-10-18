"""Write `roshni dark-now` results for a fixed set of instants, the oracle for the web port.

Output: data/oracle/dark_now.json (git-ignored). web/src/lib/darkNow.oracle.test.ts compares
the TypeScript port against it row for row (it skips when the file is absent, e.g. in CI).
Usage: uv run python scripts/dark_now_oracle.py
"""

import json
import re
from datetime import UTC, date, datetime, timedelta

import duckdb

from roshni.live.dark_now import IESCO_LEVELS, dark_now
from roshni.paths import DATA_DIR

EDGES = ("00:00", "02:04", "02:05", "05:30", "12:00", "13:59", "14:00", "22:34", "22:35", "23:59")
TIMES = ("06:17", "09:45", "11:00", "15:30")
MAINT_TIMES = ("08:59", "09:00", "11:30", "14:00", "16:59")


def instants() -> list[datetime]:
    out = [datetime.fromisoformat(f"2026-10-06T{t}") for t in EDGES]
    out += [datetime(2026, 8, 4, 23, 0), datetime(2026, 8, 5, 0, 0)]  # K-Electric effective date
    d = date(2026, 7, 16)
    while d <= date(2026, 10, 8):  # planned-shutdown period
        out += [datetime.fromisoformat(f"{d}T{t}") for t in TIMES]
        d += timedelta(days=6)
    d = date(2026, 9, 28)
    while d <= date(2027, 3, 31):  # announced-maintenance period
        out += [datetime.fromisoformat(f"{d}T{t}") for t in MAINT_TIMES]
        d += timedelta(days=5)
    return out


def _count(notes: list[str], pattern: str) -> int:
    return next((int(m[1]) for n in notes if (m := re.match(pattern, n))), 0)


def main() -> None:
    con = duckdb.connect(str(DATA_DIR / "roshni.duckdb"), read_only=True)
    cases = []
    for i, at in enumerate(instants()):
        for level in (None, IESCO_LEVELS[i % len(IESCO_LEVELS)]):
            r = dark_now(con, at, iesco_level=level)
            cases.append({
                "at_utc": r.at_local.astimezone(UTC).isoformat().replace("+00:00", "Z"),
                "level": level,
                "rows": [
                    [x.kind, x.feeder_id, x.feeder_name, x.window_local, x.area,
                     x.effective_from.isoformat() if x.effective_from else None]
                    for x in r.rows
                ],
                "not_yet": sum(n.startswith("not applicable") for n in r.notes),
                "unmatched": _count(r.notes, r"(\d+) planned shutdown"),
                "unlinked": _count(r.notes, r"(\d+) announced maintenance"),
            })  # fmt: skip
    out = DATA_DIR / "oracle" / "dark_now.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(cases, indent=1) + "\n", encoding="utf-8")
    rows = sum(len(c["rows"]) for c in cases)
    print(f"wrote {len(cases)} cases, {rows} rows -> {out.relative_to(DATA_DIR.parent)}")


if __name__ == "__main__":
    main()
