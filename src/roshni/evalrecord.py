"""History and regression checks for the committed eval records (evals/*.json).

Both evals (`roshni ask-eval --record`, `roshni heal-eval --record`) keep, besides the latest
per-model table, one history point per model and run: date, cases passed, cases run, score. The
weekly run in publish.yml appends a point and calls `regressions`: a score below the floor, or
lower than that model's previous point, becomes a "Pipeline notices" entry (the run still
succeeds). Points are never edited; at most HISTORY are kept per record.
"""

import math
from datetime import date, timedelta

HISTORY = 400  # about a year of daily points (Ask Roshni scores a slice every day)
WINDOW_DAYS = 7


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


def wilson(passed: int, total: int, z: float = 1.96) -> tuple[float, float] | None:
    """95% Wilson score interval for a pass rate, in percent."""
    if not total:
        return None
    p = passed / total
    d = 1 + z * z / total
    c = (p + z * z / (2 * total)) / d
    h = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / d
    return round(100 * max(0.0, c - h), 1), round(100 * min(1.0, c + h), 1)


def rolling(data: dict, model: str, day: date, days: int = WINDOW_DAYS) -> dict | None:
    """Pooled score of `model` over the `days` days ending on `day`, with its interval."""
    start = str(day - timedelta(days=days - 1))
    pts = [p for p in data.get("history", [])
           if p["model"] == model and start <= p["date"] <= str(day)]  # fmt: skip
    passed, total = sum(p["passed"] for p in pts), sum(p["total"] for p in pts)
    if not total:
        return None
    low, high = wilson(passed, total)
    return {"from_date": min(p["date"] for p in pts), "to_date": max(p["date"] for p in pts),
            "model": model, "runs": len(pts), "passed": passed, "total": total,
            "score_pct": round(100 * passed / total, 1), "ci_low_pct": low,
            "ci_high_pct": high}  # fmt: skip


def rolling_regressions(data: dict, day: date, floor_pct: float, name: str) -> list[str]:
    """A notice when a model's pooled score over the last week is below the floor."""
    lines = []
    for model in sorted({p["model"] for p in data.get("history", []) if p["date"] == str(day)}):
        r = rolling(data, model, day)
        if r and r["score_pct"] < floor_pct:
            lines.append(
                f"- {name}, {model}: {r['passed']}/{r['total']} ({r['score_pct']}%, "
                f"95% CI {r['ci_low_pct']}-{r['ci_high_pct']}) over "
                f"{r['from_date']}..{r['to_date']} is below the {floor_pct:g}% floor."
            )
    return lines


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
