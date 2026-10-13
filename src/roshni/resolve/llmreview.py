"""LLM review of press-release names that the written rules leave pending (owner, 2026-10-13).

Runs after `autoreview.review_press`, only on undecided `suggested` rows, through the same
OpenRouter chain and spend cap as the report narrator. The model may only choose among the
candidate feeders already listed for a name (or reject them all); it can never invent a feeder.
A reply is used only if it parses and validates completely; otherwise the names stay pending.
Each decision is written with a note `llm-review <date> <model>: <reason>`; the publish job
commits the seed, so a decision is made once and stays stable.
"""

import json
import re
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

import httpx

from roshni.narrate.openrouter import CACHE_DIR, NarratorConfig, ask

MAX_SUBJECTS = 40  # per run; the rest wait for the next day
SYSTEM = """You review name matches for a public data project. Each item is a feeder name as
printed in an IESCO (Islamabad/Rawalpindi electricity) press release, with candidate feeders from
IESCO's own feeder list in the same circle. Decide which candidate, if any, is the same feeder.
Rules (from the project's written review rules):
- Accept spelling variants of the same name (vowels, H and doubled letters vary in romanised
  Urdu), obvious typos, standard abbreviations (Dk = Dhoke, Col = Colonel, Cly = Colony) and
  roman numerals written as digits (II = 2).
- A bracketed part may name the place: "F-10 (Kala Base)" can be KALA BASE.
- Reject when the names differ in substance, when a number or letter differs (Sector A-2 is not
  SECTOR A; Club-1 is not CLUB-2), when an extra syllable makes a different name (JALALA is not
  JALALIA), or when two candidates are equally plausible.
- When unsure, reject. A wrong match is worse than no match.
Answer with JSON only, no prose, no code fences: a list of objects
{"subject_id": "...", "accept": "<candidate_id or null>", "reason": "<under 15 words>"}
with one object per item you can decide. Use only the ids given."""


def _items(rows: list[dict]) -> dict[str, dict]:
    """Pending subjects -> {name, circle, candidates: {candidate_id: (name, score)}}."""
    by_subject: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_subject[r["subject_id"]].append(r)
    items = {}
    for sid, subject_rows in by_subject.items():
        if any(r["decision"] == "accepted" or r["status"] == "auto_exact" for r in subject_rows):
            continue
        open_rows = [r for r in subject_rows if r["status"] == "suggested" and not r["decision"]]
        if open_rows:
            first = open_rows[0]
            items[sid] = {
                "name": first["subject_name"],
                "circle": first["subject_group"],
                "candidates": {
                    r["candidate_id"]: (r["candidate_name"], r["score"]) for r in open_rows
                },
            }
    return dict(list(items.items())[:MAX_SUBJECTS])


def build_prompt(items: dict[str, dict]) -> str:
    listing = [
        {"subject_id": sid, "printed_name": it["name"], "circle": it["circle"],
         "candidates": [{"candidate_id": cid, "name": n, "similarity": s}
                        for cid, (n, s) in it["candidates"].items()]}
        for sid, it in items.items()
    ]  # fmt: skip
    return "Items:\n" + json.dumps(listing, indent=1)


def parse(reply: str, items: dict[str, dict]) -> tuple[list[dict], list[str]]:
    """Decisions and problems; any problem rejects the whole reply."""
    text = re.sub(r"^\s*```(?:json)?|```\s*$", "", reply.strip())
    try:
        data = json.loads(text)
    except ValueError as e:
        return [], [f"not JSON ({e})"]
    if not isinstance(data, list):
        return [], ["not a JSON list"]
    problems, seen, out = [], set(), []
    for d in data:
        if not isinstance(d, dict) or set(d) != {"subject_id", "accept", "reason"}:
            problems.append(f"bad item {str(d)[:60]}")
            continue
        sid, acc, reason = d["subject_id"], d["accept"], d["reason"]
        if sid not in items:
            problems.append(f"unknown subject {str(sid)[:40]}")
        elif sid in seen:
            problems.append(f"subject decided twice: {sid}")
        elif acc is not None and acc not in items[sid]["candidates"]:
            problems.append(f"{sid}: candidate {str(acc)[:30]} was not offered")
        elif not isinstance(reason, str) or not reason.strip() or len(reason) > 200:
            problems.append(f"{sid}: missing or overlong reason")
        else:
            seen.add(sid)
            out.append({"subject_id": sid, "accept": acc, "reason": reason.strip()})
    return out, problems


def review_with_llm(
    rows: list[dict],
    api_key: str | None,
    cfg: NarratorConfig | None = None,
    transport: httpx.BaseTransport | None = None,
    today: str | None = None,
    cache_dir: Path = CACHE_DIR,
) -> dict[str, int]:
    """Decide still-pending press names in place. No key, no valid reply: nothing changes."""
    items = _items(rows)
    counts = {"llm_accepted": 0, "llm_rejected": 0, "llm_pending": len(items)}
    if not items or not api_key:
        return counts
    prompt = build_prompt(items)
    try:
        check = lambda reply: parse(reply, items)[1]  # noqa: E731
        cfg = cfg or NarratorConfig.load()
        result = ask(SYSTEM, prompt, check, cfg, api_key, transport, cache_dir)
    except (httpx.HTTPError, KeyError, ValueError, TypeError):
        return counts  # OpenRouter unavailable: names stay pending
    if result.draft is None:
        return counts
    decisions, _ = parse(result.draft, items)
    stamp = f"llm-review {today or datetime.now(UTC).date().isoformat()} {result.model}: "
    for d in decisions:
        for r in rows:
            if r["subject_id"] != d["subject_id"] or r["status"] != "suggested" or r["decision"]:
                continue
            if r["candidate_id"] == d["accept"]:
                r["decision"], r["note"] = "accepted", stamp + d["reason"]
                counts["llm_accepted"] += 1
            else:
                why = "another candidate accepted" if d["accept"] else d["reason"]
                r["decision"], r["note"] = "rejected", stamp + why
                counts["llm_rejected"] += 1
        counts["llm_pending"] -= 1
    return counts
