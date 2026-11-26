"""History and regression checks for the committed eval records (evals/*.json).

Both evals (`roshni ask-eval --record`, `roshni heal-eval --record`) keep, besides the latest
per-model table, one history point per model and run: date, cases passed, cases run, score. The
weekly run in publish.yml appends a point and calls `regressions`: a score below the floor, or
lower than that model's previous point, becomes a "Pipeline notices" entry (the run still
succeeds). Points are never edited; at most HISTORY are kept per record.
"""

from datetime import date

HISTORY = 104  # two years of weekly points across a few models


def point(day: date, model: str, passed: int, total: int) -> dict:
    return {
        "date": str(day),
        "model": model,
        "passed": passed,
        "total": total,
        "score_pct": round(100 * passed / total, 1) if total else None,
    }


def append(data: dict, points: list[dict]) -> dict:
    """Add these points; a second run on the same date replaces that model's point."""
    new = {(p["date"], p["model"]) for p in points}
    old = [p for p in data.get("history", []) if (p["date"], p["model"]) not in new]
    data["history"] = sorted([*old, *points], key=lambda p: (p["date"], p["model"]))[-HISTORY:]
    return data


def regressions(data: dict, day: date, floor_pct: float, name: str) -> list[str]:
    """Notice lines for this run's points: below the floor, or below the model's last point."""
    lines = []
    history = data.get("history", [])
    for p in [p for p in history if p["date"] == str(day)]:
        before = [q for q in history if q["model"] == p["model"] and q["date"] < p["date"]]
        score = p["score_pct"]
        if score is None:
            continue
        if score < floor_pct:
            lines.append(f"- {name}, {p['model']}: {p['passed']}/{p['total']} ({score}%) is "
                         f"below the {floor_pct:g}% floor.")  # fmt: skip
        if before and before[-1]["score_pct"] is not None and score < before[-1]["score_pct"]:
            b = before[-1]
            lines.append(f"- {name}, {p['model']}: {p['passed']}/{p['total']} ({score}%), down "
                         f"from {b['passed']}/{b['total']} on {b['date']}.")  # fmt: skip
    return lines
