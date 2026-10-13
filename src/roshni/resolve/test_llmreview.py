import json
from pathlib import Path

import httpx

from roshni.narrate.openrouter import NarratorConfig
from roshni.resolve.llmreview import review_with_llm


def row(subject: str, candidate: str, cid: str, decision: str = "", status: str = "suggested"):
    return dict(subject_id=f"Rawalpindi Cantt:{subject}", subject_name=subject,
                subject_group="Rawalpindi Cantt", candidate_id=cid, candidate_name=candidate,
                score=80.0, status=status, decision=decision, note="")  # fmt: skip


def fake(reply: str):
    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "m/free:free", "pricing": {}}]})
        return httpx.Response(200, json={"choices": [
            {"message": {"content": reply}, "finish_reason": "stop"}]})  # fmt: skip

    return httpx.MockTransport(handler)


CFG = NarratorConfig(models=["m/free:free"])
SID_A, SID_B = "Rawalpindi Cantt:Askari Heights (IV)", "Rawalpindi Cantt:Sector A-2"


def rows() -> list[dict]:
    return [
        row("Askari Heights (IV)", "ASKARI HIEGHT-4", "f1"),
        row("Sector A-2", "SECTOR A", "f2"),
        row("Sector A-2", "SECTOR A (DHA)", "f3"),
        row("Old", "OLD", "f4", decision="rejected"),  # decided before: not offered, unchanged
    ]


def test_valid_reply_is_applied(tmp_path: Path) -> None:
    reply = json.dumps([
        {"subject_id": SID_A, "accept": "f1", "reason": "roman IV = 4, typo of Heights"},
        {"subject_id": SID_B, "accept": None, "reason": "number dropped; two candidates"},
    ])  # fmt: skip
    rs = rows()
    counts = review_with_llm(rs, "k", CFG, fake(reply), today="2026-10-13", cache_dir=tmp_path)
    got = {(r["subject_name"], r["candidate_id"]): (r["decision"], r["note"]) for r in rs}
    assert got[("Askari Heights (IV)", "f1")] == (
        "accepted",
        "llm-review 2026-10-13 m/free:free: roman IV = 4, typo of Heights",
    )
    assert got[("Sector A-2", "f2")][0] == got[("Sector A-2", "f3")][0] == "rejected"
    assert got[("Old", "f4")] == ("rejected", "")
    assert counts == {"llm_accepted": 1, "llm_rejected": 2, "llm_pending": 0}


def test_invented_candidate_rejects_the_whole_reply(tmp_path: Path) -> None:
    reply = json.dumps([
        {"subject_id": SID_A, "accept": "f1", "reason": "variant"},
        {"subject_id": SID_B, "accept": "f999", "reason": "made up"},
    ])  # fmt: skip
    rs = rows()
    counts = review_with_llm(rs, "k", CFG, fake(reply), cache_dir=tmp_path)
    assert all(r["decision"] == "" for r in rs[:3]) and counts["llm_pending"] == 2


def test_no_key_or_prose_reply_changes_nothing(tmp_path: Path) -> None:
    rs = rows()
    assert review_with_llm(rs, None, CFG, cache_dir=tmp_path)["llm_pending"] == 2
    review_with_llm(rs, "k", CFG, fake("I think the first one matches."), cache_dir=tmp_path)
    assert all(r["decision"] == "" for r in rs[:3])


def test_partial_answer_leaves_the_rest_pending(tmp_path: Path) -> None:
    reply = json.dumps([{"subject_id": SID_A, "accept": "f1", "reason": "variant"}])
    rs = rows()
    counts = review_with_llm(rs, "k", CFG, fake(reply), cache_dir=tmp_path)
    assert counts["llm_pending"] == 1 and rs[1]["decision"] == rs[2]["decision"] == ""
