import json
from datetime import date
from pathlib import Path

from roshni import evalrecord
from roshni.ask import evaluate
from roshni.heal import simulate


def test_append_replaces_same_day_and_keeps_order() -> None:
    d: dict = {}
    evalrecord.append(d, [evalrecord.point(date(2026, 11, 30), "m", 9, 10)])
    evalrecord.append(d, [evalrecord.point(date(2026, 11, 23), "m", 10, 10)])
    evalrecord.append(d, [evalrecord.point(date(2026, 11, 30), "m", 8, 10)])
    assert [(p["date"], p["passed"]) for p in d["history"]] == [
        ("2026-11-23", 10),
        ("2026-11-30", 8),
    ]
    assert d["history"][1]["score_pct"] == 80.0


def test_history_is_capped() -> None:
    d: dict = {}
    for i in range(evalrecord.HISTORY + 5):
        evalrecord.append(d, [evalrecord.point(date.fromordinal(700000 + i), "m", 1, 1)])
    assert len(d["history"]) == evalrecord.HISTORY


def test_regressions_floor_and_drop() -> None:
    d: dict = {}
    evalrecord.append(d, [evalrecord.point(date(2026, 11, 23), "a", 10, 10),
                          evalrecord.point(date(2026, 11, 23), "b", 10, 10)])  # fmt: skip
    evalrecord.append(d, [evalrecord.point(date(2026, 11, 30), "a", 10, 10),
                          evalrecord.point(date(2026, 11, 30), "b", 8, 10)])  # fmt: skip
    lines = evalrecord.regressions(d, date(2026, 11, 30), 90, "x")
    assert len(lines) == 2  # b: below the floor, and down from last week
    assert all(", b:" in line for line in lines)
    assert evalrecord.regressions(d, date(2026, 11, 23), 90, "x") == []


def _score(model: str, results: list[tuple[str, bool]]) -> evaluate.ModelScore:
    s = evaluate.ModelScore(model)
    for expect, ok in results:
        s.items.append(evaluate.ItemScore("i", expect, "answered", ok, True, 10, 1.0))
    return s


def test_ask_record_writes_rows_and_history(tmp_path: Path) -> None:
    path = tmp_path / "ask.json"
    s = _score("groq/x", [("answer", True), ("refuse", True), ("reject", False), ("block", True)])
    assert s.summary()["guard_accuracy_pct"] == 50.0  # reject is scored with the guard items
    _, lines = evaluate.record([s], path, date(2026, 11, 30))
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["run_on"] == "2026-11-30"
    assert data["models"][0]["overall_pct"] == 75.0
    assert data["history"] == [{"date": "2026-11-30", "model": "groq/x", "passed": 3,
                                "total": 4, "score_pct": 75.0}]  # fmt: skip
    assert lines and "below the 90% floor" in lines[0]


def test_heal_record_appends_history(tmp_path: Path) -> None:
    path = tmp_path / "heal.json"
    summary = {"model": "groq/y", "cases": 27, "recovered": 27, "healed_but_different": 0,
               "failed": 0, "tokens_total": 5, "latency_mean_s": 0.5}  # fmt: skip
    simulate.record([summary], 9, ["renamed"], path, date(2026, 11, 23))
    simulate.record([{**summary, "recovered": 26, "failed": 1}], 9, ["renamed"], path,
                    date(2026, 11, 30))  # fmt: skip
    data = json.loads(path.read_text(encoding="utf-8"))
    assert [p["passed"] for p in data["history"]] == [27, 26]
    lines = simulate.regressions(path, date(2026, 11, 30))
    assert len(lines) == 1 and "down from 27/27" in lines[0]


def test_committed_records_have_history() -> None:
    rec = json.loads(simulate.EVAL_RECORD.read_text(encoding="utf-8"))
    assert {p["model"] for p in rec["history"]} >= {m["model"] for m in rec["models"]}


def test_wilson_interval():
    assert evalrecord.wilson(0, 0) is None
    low, high = evalrecord.wilson(34, 35)
    assert 85 < low < 92 and high > 99


def test_rolling_pools_the_last_week():
    data = {"history": [evalrecord.point(date(2026, 11, d), "m", 14, 15) for d in range(20, 28)]}
    r = evalrecord.rolling(data, "m", date(2026, 11, 27))
    assert r["runs"] == 7 and r["total"] == 105 and r["passed"] == 98
    assert r["from_date"] == "2026-11-21"
    assert evalrecord.rolling_regressions(data, date(2026, 11, 27), 95, "Ask") != []
    assert evalrecord.rolling_regressions(data, date(2026, 11, 27), 90, "Ask") == []
