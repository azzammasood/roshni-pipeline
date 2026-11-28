from decimal import Decimal

from roshni.ask import evaluate, prepared
from roshni.ask.engine import AskResult


class FakeCon:
    def execute(self, *_a, **_k):
        raise RuntimeError("no warehouse in this test")


def test_prepared_keeps_answered_questions_only(monkeypatch):
    monkeypatch.setattr(prepared.engine, "built_at", lambda con: "2026-11-27 08:00 PKT")
    items = [{"id": "a", "tag": "K-Electric", "question": "q1"}, {"id": "b", "question": "q2"}]

    def ask(q, con, cfg, layer):
        if q == "q2":
            return AskResult(question=q, status="failed")
        return AskResult(question=q, status="answered", answer="IBC A leads with 10.",
                         sql="select 1", columns=["ibc", "n"], rows=[["IBC A", Decimal("10.25")]],
                         narrated_by="groq/qwen/qwen3.8-27b")  # fmt: skip

    from types import SimpleNamespace

    golden = [{"question": "q1", "sql": "ref", "expect": "answer"}]
    monkeypatch.setattr(prepared.evaluate, "load_items", lambda paraphrases=True: golden)
    ref = SimpleNamespace(columns=["ibc", "n"], rows=[("IBC A", Decimal("10.25"))])
    doc = prepared.prepare(FakeCon(), None, items, layer=object(), ask=ask, log=lambda *_: None,
                           reference=lambda sql: ref)  # fmt: skip
    assert [i["id"] for i in doc["items"]] == ["a"]
    assert doc["items"][0]["rows"] == [["IBC A", "10.3"]]
    assert doc["items"][0]["narrated"] and doc["built_at"] == "2026-11-27 08:00 PKT"
    wrong = SimpleNamespace(columns=["ibc", "n"], rows=[("IBC B", 3)])
    doc = prepared.prepare(FakeCon(), None, items, layer=object(), ask=ask, log=lambda *_: None,
                           reference=lambda sql: wrong)  # fmt: skip
    assert doc["items"] == []  # a wrong answer is dropped, never published


def test_every_prepared_question_is_in_the_golden_set():
    golden = {i["question"] for i in evaluate.load_items(paraphrases=False)}
    assert {i["question"] for i in prepared.load()} <= golden


def test_paraphrases_inherit_the_reference_and_slices_cover_the_set():
    from datetime import date, timedelta

    items = evaluate.load_items()
    by_id = {i["id"]: i for i in items}
    for it in items:
        if "variant_of" in it:
            base = by_id[it["variant_of"]]
            assert it["expect"] == base["expect"] and it.get("sql") == base.get("sql")
            assert it["question"] != base["question"]
    week = [evaluate.daily_slice(items, date(2026, 11, 23) + timedelta(days=d)) for d in range(7)]
    ids = [i["id"] for s in week for i in s]
    assert sorted(ids) == sorted(by_id) and len(ids) == len(set(ids))
    assert max(len(s) for s in week) <= 16  # about 3K tokens each: under 50K a day
