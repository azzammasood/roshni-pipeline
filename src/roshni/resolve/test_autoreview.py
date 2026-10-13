import copy
import csv

import pytest

from roshni.paths import REPO_ROOT
from roshni.resolve.autoreview import decide, review_press


@pytest.mark.parametrize(
    "subject, candidate, verdict",
    [
        ("Haidri Chowk", "HAIDERI CHOWK", "match"),  # spelling variant
        ("Gulshan Sehat", "GULSHAN E SEHAT", "match"),  # izafat
        ("Dk. Chaudrian", "DHOKE CHODRIAN", "match"),  # Dk = Dhoke
        ("G-8 Markaz", "G8 MARKAZ", "match"),
        ("Ward No 08", "WARD-NO-8", "match"),
        ("Scheme-II", "SCHEME-2", "match"),  # roman = digits
        ("F-10 (Kala Base)", "KALA BASE", "match"),  # bracket names the feeder
        ("Scheme-II", "SCHEME-I", "rejected"),  # numbers differ
        ("Sector-C", "SECTOR -D", "rejected"),  # single letter differs
        ("A-Block", "B BLOCK", "rejected"),
        ("JALALA", "JALALIA", ""),  # extra syllable: overturned on 2026-10-10, never auto
        ("SOHAN", "SOHANA", ""),
        ("PHA-1", "PHA", ""),  # number on one side: judgment
        ("Askari Heights (IV)", "ASKARI HIEGHT-4", ""),  # typo + plural: judgment
    ],
)
def test_decide(subject: str, candidate: str, verdict: str) -> None:
    assert decide(subject, candidate)[0] == verdict


def row(subject: str, candidate: str, status: str = "suggested", decision: str = "") -> dict:
    return dict(subject_id=f"g:{subject}", subject_name=subject, candidate_id=candidate,
                candidate_name=candidate, status=status, decision=decision, note="")  # fmt: skip


def test_review_press_keeps_decisions_and_resolves_ambiguity() -> None:
    rows = [
        row("Haidri Chowk", "HAIDERI CHOWK"),
        row("Haidri Chowk", "CAR CHOWK"),  # loses to the accepted candidate
        row("Sector-A", "SECTOR A", status="auto_exact"),
        row("Sector-A", "SECTOR 4"),  # subject already has an exact match
        row("Sohawa", "SOHAWA"),
        row("Sohawa", "SUHAWA"),  # two candidates both match: ambiguous, both stay pending
        row("Old", "OLD", decision="rejected"),  # an earlier decision is never changed
    ]
    counts = review_press(rows)
    got = {(r["subject_name"], r["candidate_name"]): r["decision"] for r in rows}
    assert got[("Haidri Chowk", "HAIDERI CHOWK")] == "accepted"
    assert got[("Haidri Chowk", "CAR CHOWK")] == "rejected"
    assert got[("Sector-A", "SECTOR 4")] == "rejected"
    assert got[("Old", "OLD")] == "rejected"
    assert all(
        r["note"].startswith("auto-review: ")
        for r in rows
        if r["decision"] and r["subject_name"] != "Old"
    )
    assert got[("Sohawa", "SOHAWA")] == got[("Sohawa", "SUHAWA")] == ""
    assert counts == {"accepted": 1, "rejected": 2, "pending": 2}


def test_backtest_agrees_with_every_reviewed_decision() -> None:
    """On the committed seed, the rules never contradict a delegated (claude-review) decision."""
    path = REPO_ROOT / "dbt" / "seeds" / "review_press_feeder.csv"
    rows = list(csv.DictReader(path.open(encoding="utf-8", newline="")))
    reviewed = lambda r: r["status"] == "suggested" and r["note"].startswith("claude-review")  # noqa: E731
    truth = {(r["subject_id"], r["candidate_id"]): r["decision"] for r in rows if reviewed(r)}
    test = copy.deepcopy(rows)
    for r in test:
        if reviewed(r):
            r["decision"], r["note"] = "", ""
    review_press(test)
    decided = [(truth[k], r["decision"]) for r in test
               if (k := (r["subject_id"], r["candidate_id"])) in truth and r["decision"]]  # fmt: skip
    assert len(decided) > 200  # the rules decide most reviewed rows...
    assert [d for d in decided if d[0] != d[1]] == []  # ...and agree with every one of them
