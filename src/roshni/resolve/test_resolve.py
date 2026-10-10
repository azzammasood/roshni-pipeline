import csv
from pathlib import Path

import pytest
from rapidfuzz import fuzz

from roshni.resolve.names import best_candidates, normalise, variants
from roshni.resolve.review import merge_write

COLS = ["subject_id", "candidate_id", "score", "status", "decision", "note"]


def test_normalise() -> None:
    assert normalise("BHARAKHAU 1") == "BHARAKHAU"
    assert normalise("ATTOCK MC") == "ATTOCK"
    assert normalise("Islamabad Club-2", keep_numbers=True) == "ISLAMABAD CLUB 2"
    assert normalise("Askari-XI") == "ASKARI"
    assert normalise("Askari-XI", keep_numbers=True) == "ASKARI XI"
    assert variants("ABDUL RAHEEM (F-7/2)") == {"ABDUL RAHEEM F", "ABDUL RAHEEM"}


def test_exact_ranks_first_and_numbers_matter() -> None:
    pool = {"a": "ISLAMABAD CLUB 1", "b": "ISLAMABAD CLUB 2", "c": "CLUB ROAD"}
    (top, *_) = best_candidates("Islamabad Club-2", pool, 70, 3, keep_numbers=True)
    assert (top.candidate_id, top.exact) == ("b", True)


def test_token_set_exact_means_identical_name() -> None:
    pool = {"v1": "HASAN ABDAL MC", "v2": "HASAN ABDAL KALAN"}
    cands = best_candidates("HASAN ABDAL", pool, 85, 3, scorer=fuzz.token_set_ratio)
    assert [(c.candidate_id, c.exact) for c in cands] == [("v1", True), ("v2", False)]


def test_no_candidate_below_cutoff() -> None:
    assert best_candidates("KRL", {"x": "QADEER ROAD"}, 70, 3) == []


def read(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_merge_keeps_decisions_and_orphans(tmp_path: Path) -> None:
    p = tmp_path / "review.csv"
    rows = [
        dict(subject_id="f1", candidate_id="a1", score=100, status="auto_exact"),
        dict(subject_id="f2", candidate_id="a2", score=90, status="suggested"),
    ]
    merge_write(p, [dict(r) for r in rows], COLS)
    edited = read(p)
    edited[1]["decision"] = "accepted"
    edited.append(dict(subject_id="f3", candidate_id="owner", score="", status="no_candidate",
                       decision="accepted", note="added by owner"))  # fmt: skip
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(edited)
    stats = merge_write(p, [dict(r) for r in rows], COLS)
    out = {(r["subject_id"], r["candidate_id"]): r for r in read(p)}
    assert out[("f2", "a2")]["decision"] == "accepted"
    assert out[("f3", "owner")]["note"] == "added by owner"
    assert stats["orphaned_decisions"] == 1


def test_merge_rejects_bad_decision(tmp_path: Path) -> None:
    p = tmp_path / "review.csv"
    p.write_text("subject_id,candidate_id,score,status,decision,note\nf1,a1,90,suggested,maybe,\n")
    with pytest.raises(ValueError, match="bad decision"):
        merge_write(
            p, [dict(subject_id="f1", candidate_id="a1", score=90, status="suggested")], COLS
        )
