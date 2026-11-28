import yaml

from roshni.ask import shared


def test_merge_adds_new_drops_personal_and_duplicates(tmp_path):
    path = tmp_path / "candidates.yml"
    qs = [
        {
            "date": "2026-11-28",
            "question": "Which IBC has the most  twelve-hour feeders?",
            "reason": "wrong",
            "sql": "select 1",
        },
        {
            "date": "2026-11-28",
            "question": "which ibc has the most twelve-hour feeders?",
            "reason": "unclear",
            "sql": None,
        },
        {
            "date": "2026-11-28",
            "question": "My reference number is 04123456789, when is my light going?",
            "reason": "wrong",
            "sql": None,
        },
        {"date": "2026-11-28", "question": "mail me at a.b@example.com", "reason": "", "sql": None},
    ]
    assert shared.merge(qs, path) == (1, 2)
    assert shared.merge(qs, path) == (0, 2)  # same questions again: nothing new
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert [c["question"] for c in data["candidates"]] == [
        "Which IBC has the most twelve-hour feeders?"
    ]
    assert data["candidates"][0]["status"] == "to_review"
