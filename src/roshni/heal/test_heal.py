"""Header healing on small generated workbooks; the LLM is an httpx.MockTransport."""

import json
from datetime import date
from pathlib import Path

import httpx
import openpyxl
import pytest
import yaml

from roshni.heal import headers as h
from roshni.heal import simulate as sim
from roshni.llm import chain
from roshni.parsers import iesco_maintenance as im


def save(path: Path, rows: list[list], merge: tuple[str, ...] = ()) -> Path:
    wb = openpyxl.Workbook()
    ws = wb.active
    for r in rows:
        ws.append(r)
    for rng in merge:
        ws.merge_cells(rng)
    wb.save(path)
    return path


def data(n: int = 12) -> list[list]:
    return [
        [i, f"Feeder {i}", 10000 + i, f"{(i % 27) + 1:02d}.10.2026", "09:00", "14:00", "Annual"]
        for i in range(1, n + 1)
    ]


GOOD = ["Sr No.", "Name of Feeder", "Feeder Code", "DATE", "From", "To", "Purpose"]
DRIFTED = ["Sr No.", "Feeder Title", "Feeder Code", "Shutdown Day", "Begins", "Ends", "Purpose"]


@pytest.fixture
def books(tmp_path: Path):
    good = save(tmp_path / "good.xlsx", [GOOD, *data()])
    drifted = save(tmp_path / "drifted.xlsx", [DRIFTED, *data()])
    return h.Workbook(good, "islamabad"), h.Workbook(drifted, "attock")


def _cfg() -> chain.ChainConfig:
    return chain.ChainConfig(
        providers=[
            chain.Provider(
                "groq",
                "https://groq.test/v1",
                "GROQ_API_KEY",
                [chain.Model("m1"), chain.Model("m2")],
            )
        ]  # fmt: skip
    )


def _transport(*replies: dict):
    it = iter(replies)

    def handler(_req: httpx.Request) -> httpx.Response:
        body = {"choices": [{"message": {"content": json.dumps(next(it))},
                             "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 20}}  # fmt: skip
        return httpx.Response(200, json=body)

    return httpx.MockTransport(handler)


@pytest.fixture(autouse=True)
def key(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test")


RIGHT = {"header_row": 1, "columns": {"1": "serial", "2": "feeder_name", "3": "feeder_code",
         "4": "date", "5": "start", "6": "end", "7": "purpose"}, "reason": "renamed"}  # fmt: skip


def test_detects_drift(books):
    good, drifted = books
    assert not h.health(im.parse_workbook(good.path, good.item, {})).drifted
    hd = h.health(im.parse_workbook(drifted.path, drifted.item, {}))
    assert hd.drifted and not hd.header_found


@pytest.mark.parametrize(
    ("reply", "problem"),
    [
        ({"header_row": 1, "columns": {"4": "when"}}, "unknown field"),
        ({"header_row": 1, "columns": {"40": "date"}}, "does not exist"),
        ({"header_row": 9, "columns": {}}, "header_row"),
        (RIGHT | {"columns": RIGHT["columns"] | {"7": "date"}}, "twice"),
        ({"header_row": 1, "columns": {"4": "date"}}, "required"),
    ],
)
def test_check_proposal_rejects(books, reply, problem):
    rows, _ = h.sheet_preview(books[1].path)
    p, problems = h.check_proposal(json.dumps(reply), rows)
    assert p is None and any(problem in x for x in problems), problems


def test_aliases_skip_headers_the_parser_already_knows(books):
    rows, _ = h.sheet_preview(books[1].path)
    p, _ = h.check_proposal(json.dumps(RIGHT), rows)
    assert h.aliases_from(p, rows, {}) == {
        "feeder title": "feeder_name", "shutdown day": "date", "begins": "start", "ends": "end",
    }  # fmt: skip


def test_merged_time_heading_learns_the_labels_underneath(tmp_path):
    rows = [["Sr", "Feeder Title", "Day", "TIME", None], [None, None, None, "Start", "Stop"],
            *[[i, f"F{i}", "01.10.2026", "09:00", "10:00"] for i in range(1, 12)]]  # fmt: skip
    path = save(tmp_path / "t.xlsx", rows, merge=("D1:E1",))
    grid, _ = h.sheet_preview(path)
    p = h.Proposal(1, {2: "feeder_name", 3: "date", 4: "start", 5: "end"})
    assert h.aliases_from(p, grid, {}) == {
        "feeder title": "feeder_name", "day": "date", "start": "start", "stop": "end",
    }  # fmt: skip


def test_heal_learns_aliases_and_flags_rows(books):
    good, drifted = books
    corpus = h.Corpus([good, drifted], {})
    res = h.heal(drifted, _cfg(), corpus, transport=_transport(RIGHT))
    assert res.status == "healed" and res.model == "groq/m1"
    assert res.after.rows == 12 and res.after.quarantined == 0
    rows = im.parse_workbook(drifted.path, drifted.item, res.aliases).rows
    assert rows[0].outage_date == date(2026, 10, 2)
    assert "header_alias_date" in rows[0].flags


def test_wrong_mapping_fails_gate_and_next_model_is_tried(books):
    _, drifted = books
    wrong = RIGHT | {"columns": RIGHT["columns"] | {"4": "start", "5": "date"}}
    res = h.heal(drifted, _cfg(), h.Corpus([drifted], {}), transport=_transport(wrong, RIGHT))
    assert res.status == "healed" and res.model == "groq/m2"
    assert res.attempts[0]["outcome"].startswith("rejected:")


def test_gate_refuses_an_alias_that_changes_another_workbook(tmp_path, books):
    _, drifted = books
    # Another workbook already has a "Shutdown Day" column (a weekday) before its real DATE:
    # learning "shutdown day" -> date would make it read the weekday as the date.
    other_rows = [["Shutdown Day", *GOOD], *[["Monday", *r] for r in data()]]
    other = h.Workbook(save(tmp_path / "other.xlsx", other_rows), "jhelum")
    corpus = h.Corpus([other, drifted], {})
    g = h.gate(drifted, {"feeder title": "feeder_name", "shutdown day": "date",
                         "begins": "start", "ends": "end"}, corpus)  # fmt: skip
    assert not g.ok and g.regressions == ["other.xlsx"]


def test_healthy_workbook_makes_no_llm_call(books):
    good, _ = books

    def boom(_req):
        raise AssertionError("no call expected")

    res = h.heal(good, _cfg(), h.Corpus([good], {}), transport=httpx.MockTransport(boom))
    assert res.status == "healthy"


def test_save_aliases_appends_and_keeps_the_comment_header(tmp_path, books):
    cfg_file = tmp_path / "aliases.yml"
    cfg_file.write_text("# keep me\niesco_maintenance: []\n", encoding="utf-8")
    r = h.HealResult(books[1], h.Health(0, 1, False), "healed", {"shutdown day": "date"},
                     h.Health(12, 0, True), "groq/m1")  # fmt: skip
    assert h.save_aliases([r, r], cfg_file, date(2026, 11, 24)) == 1
    text = cfg_file.read_text(encoding="utf-8")
    assert text.startswith("# keep me\n")
    (entry,) = yaml.safe_load(text)["iesco_maintenance"]
    assert entry["field"] == "date" and entry["by"] == "llm-heal 2026-11-24 groq/m1"
    assert im.load_aliases(cfg_file) == {"shutdown day": "date"}


def test_parser_ignores_aliases_for_unknown_fields(tmp_path):
    f = tmp_path / "a.yml"
    f.write_text("iesco_maintenance:\n- {header: X, field: nonsense}\n", encoding="utf-8")
    assert im.load_aliases(f) == {}


@pytest.mark.parametrize("scenario", list(sim.SCENARIOS))
def test_simulated_drift_breaks_the_parser_and_healing_recovers_it(tmp_path, books, scenario):
    good, _ = books
    dst = tmp_path / "mut.xlsx"
    renamed = sim.mutate(good.path, dst, scenario)
    assert len(renamed) >= 4
    assert h.health(im.parse_workbook(dst, good.item, {})).drifted
    rows, _ = h.sheet_preview(dst)
    p, problems = h.check_proposal(json.dumps(RIGHT), rows)
    assert not problems
    learned = h.aliases_from(p, rows, {})
    healed = sim._comparable(im.parse_workbook(dst, good.item, learned))
    assert healed == sim._comparable(im.parse_workbook(good.path, good.item, {}))


def test_merged_heading_with_data_underneath_learns_the_heading_once(tmp_path):
    rows = [["Sr", "Feeder Title", "Day", "Hours", None],
            *[[i, f"F{i}", "01.10.2026", "09:00", "10:00"] for i in range(1, 12)]]  # fmt: skip
    path = save(tmp_path / "m.xlsx", rows, merge=("D1:E1",))
    grid, table = h.sheet_preview(path)
    assert "[4-5] Hours" in table
    p = h.Proposal(1, {2: "feeder_name", 3: "date", 4: "start", 5: "end"})
    learned = h.aliases_from(p, grid, {})
    assert learned == {"feeder title": "feeder_name", "day": "date", "hours": "start"}
    res = im.parse_workbook(path, "x", learned)
    assert len(res.rows) == 11 and (res.rows[0].start_local, res.rows[0].end_local) == (
        "09:00", "10:00",
    )  # fmt: skip


def test_gate_drops_an_optional_alias_that_changes_another_workbook(tmp_path, books):
    _, drifted = books
    # A sibling has an unread "Ref" column; learning "ref" -> serial would start reading it.
    sib_rows = [["Ref", *GOOD[1:]], *data()]
    sibling = h.Workbook(save(tmp_path / "sib.xlsx", sib_rows), "islamabad")
    cand = {"feeder title": "feeder_name", "shutdown day": "date", "begins": "start",
            "ends": "end", "ref": "serial"}  # fmt: skip
    rows = [["Ref", *DRIFTED[1:]], *data()]
    target = h.Workbook(save(tmp_path / "t.xlsx", rows), "islamabad")
    g = h.gate(target, cand, h.Corpus([sibling, target], {}))
    assert g.ok and g.dropped == {"ref": "serial"} and "ref" not in g.accepted


def test_network_error_moves_to_the_next_model(books):
    _, drifted = books
    calls = {"n": 0}

    def handler(req):
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ConnectError("getaddrinfo failed")
        body = {"choices": [{"message": {"content": json.dumps(RIGHT)}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1}}  # fmt: skip
        return httpx.Response(200, json=body)

    res = h.heal(drifted, _cfg(), h.Corpus([drifted], {}), transport=httpx.MockTransport(handler))
    assert res.status == "healed" and res.model == "groq/m2"
    assert res.attempts[0]["outcome"] == "network error: ConnectError"


def test_write_status_counts_outcomes(tmp_path, books):
    from datetime import UTC, datetime

    wb = books[0]
    ok = h.HealResult(wb, h.Health(1, 0, True), "healthy")
    bad = h.HealResult(wb, h.Health(1, 0, True), "failed")
    out = h.write_status([ok, bad], 0, tmp_path / "s.json", datetime(2026, 11, 25, tzinfo=UTC))
    assert (out["workbooks"], out["drifted"], out["healed"]) == (2, 1, 0)
    assert json.loads((tmp_path / "s.json").read_text())["checked_at"].startswith("2026-11-25")
