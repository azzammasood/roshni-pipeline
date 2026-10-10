"""Review CSVs in dbt/seeds: regenerate candidates while keeping the owner's decisions."""

import csv
from pathlib import Path

DECISIONS = ("", "accepted", "rejected")
KEY = ("subject_id", "candidate_id")


def merge_write(path: Path, rows: list[dict], columns: list[str]) -> dict[str, int]:
    """Write rows; carry over `decision` and `note` for (subject_id, candidate_id) seen before.

    Decisions for pairs that are no longer generated are kept too (appended), so nothing the
    owner reviewed is lost when matching rules change.
    """
    old: dict[tuple, dict] = {}
    if path.exists():
        with path.open(encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                if r.get("decision") or r.get("note"):
                    old[tuple(r[k] for k in KEY)] = r
    seen = set()
    for r in rows:
        k = tuple(str(r[c]) for c in KEY)
        seen.add(k)
        prev = old.get(k)
        r["decision"] = prev["decision"] if prev else ""
        r["note"] = prev["note"] if prev else r.get("note", "")
        if r["decision"] not in DECISIONS:
            raise ValueError(f"{path.name}: bad decision {r['decision']!r} for {k}")
    kept = [r for k, r in old.items() if k not in seen]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
        w.writerows(kept)
    return {"rows": len(rows), "decisions_kept": sum(1 for r in rows if r["decision"])
            + len(kept), "orphaned_decisions": len(kept)}  # fmt: skip
