"""Visitors' shared questions -> eval candidates (`roshni ask-shared`, in publish).

A visitor who votes an answer down may tick "Also share this question" (opt-in; the Worker keeps
only those, 30 days). The publish job reads them with the admin token and adds new ones to
evals/candidates.yml with the reason and the query that was written. Questions that look like
they carry personal details (long digit runs such as phone or reference numbers, e-mail
addresses) are dropped, never stored. Claude or the owner reviews the candidates and moves good
ones into config/ask_golden.yml with a hand-written reference; nothing is added automatically.
"""

import re
from pathlib import Path

import httpx
import yaml

from roshni.paths import REPO_ROOT

CANDIDATES = REPO_ROOT / "evals" / "candidates.yml"
WORKER = "https://roshni-ask.ahmaduzzammasood.workers.dev"
ORIGIN = "https://azzammasood.github.io"
PERSONAL = re.compile(r"\d{7,}|\d{4}[\s-]\d{7}|[\w.+-]+@[\w-]+\.[\w.]+")


def fetch(token: str, base: str = WORKER, client: httpx.Client | None = None) -> list[dict]:
    c = client or httpx.Client(timeout=30)
    r = c.get(f"{base}/v1/shared", headers={"Authorization": f"Bearer {token}", "Origin": ORIGIN})
    r.raise_for_status()
    return r.json()["questions"]


def merge(shared: list[dict], path: Path = CANDIDATES) -> tuple[int, int]:
    """Add new shared questions to the candidates file; returns (added, dropped as personal)."""
    data = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else None
    items = (data or {}).get("candidates") or []
    seen = {i["question"].strip().lower() for i in items}
    added = dropped = 0
    for q in shared:
        text = " ".join(str(q.get("question", "")).split())[:500]
        if not text or text.lower() in seen:
            continue
        if PERSONAL.search(text):
            dropped += 1
            continue
        items.append({"date": q.get("date"), "question": text, "reason": q.get("reason") or "",
                      "sql": q.get("sql"), "status": "to_review"})  # fmt: skip
        seen.add(text.lower())
        added += 1
    head = ("# Questions visitors shared with a down vote (opt-in), from `roshni ask-shared`.\n"
            "# Review: move good ones into config/ask_golden.yml with a hand-written reference,\n"
            "# then set status to added or rejected. Pipeline: add only.\n")  # fmt: skip
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(head + yaml.safe_dump({"candidates": items}, allow_unicode=True,
                                          sort_keys=False, width=100),
                    encoding="utf-8", newline="\n")  # fmt: skip
    return added, dropped
