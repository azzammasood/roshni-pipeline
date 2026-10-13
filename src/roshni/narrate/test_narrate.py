import json
from pathlib import Path

import httpx
import pytest

from roshni.narrate.facts import Fact
from roshni.narrate.openrouter import NarratorConfig, narrate
from roshni.narrate.template import TEMPLATE
from roshni.narrate.validate import PLACEHOLDER, InvalidDraft, check_draft, render

FACTS = [
    Fact("coverage_listed_feeders", "listed feeders", 623, "count", "coverage"),
    Fact("hours_split_share_12h_pct", "hours_split.share_12h_pct", 79.7, "%", "hours_split"),
    Fact("ibc_highest_name", "ibc_highest.name", "IBC - Clifton", "text", "ibc_highest"),
    Fact("rho_literacy_rho", "rho_literacy.rho", -0.39, "rho", "rho_literacy"),
    Fact("rho_literacy_n", "sub-divisions in the correlation", 13, "n", "rho_literacy"),
]
GOOD = (
    "Among {coverage_listed_feeders} listed feeders, {hours_split_share_12h_pct}% are scheduled "
    "for twelve hours; the highest share is in {ibc_highest_name}. Rho is {rho_literacy_rho} "
    "(n = {rho_literacy_n}), exploratory only."
)


def test_render_fills_and_traces_numbers() -> None:
    text = render(GOOD, FACTS)
    assert "623 listed feeders" in text and "79.7%" in text and "-0.39" in text


@pytest.mark.parametrize(
    "draft,problem",
    [
        ("About 600 feeders are listed.", "number written outside a placeholder"),
        ("See {made_up_fact}.", "unknown placeholders"),
        ("Hours are high because losses are high.", "causal"),
        ("Clifton is discriminated against.", "causal"),
        ("", "empty draft"),
    ],
)
def test_bad_drafts_rejected(draft: str, problem: str) -> None:
    problems = check_draft(draft, FACTS)
    assert any(problem in p for p in problems)
    with pytest.raises(InvalidDraft):
        render(draft, FACTS)


# The first real LLM draft (2026-10-11) passed the digit check but misused units: a percentage
# as hours, a percentage as a count, a heading. Its patterns must now be rejected.
@pytest.mark.parametrize(
    "draft,problem",
    [
        ("# Report\nAmong {coverage_listed_feeders} feeders.", "headings"),
        ("Feeders follow {hours_split_share_12h_pct}-hour schedules.", "not followed by '%'"),
        ("Clifton shows {hours_split_share_12h_pct} of its feeders.", "not followed by '%'"),
        ("There are {coverage_listed_feeders}% feeders.", "used as a percentage or hours"),
        ("Feeders run {coverage_listed_feeders} hours.", "used as a percentage or hours"),
        ("Based on {rho_literacy_n} feeders.", "not written as 'n = ...'"),
        ("A value of {rho_literacy_rho} was seen.", "not introduced as rho"),
    ],
)
def test_unit_misuse_rejected(draft: str, problem: str) -> None:
    assert any(problem in p for p in check_draft(draft, FACTS))


def test_disclaimer_wording_is_allowed() -> None:
    assert check_draft("Descriptive only; no causal reading.", FACTS) == []


def test_template_only_uses_placeholders() -> None:
    stripped = PLACEHOLDER.sub("", TEMPLATE)
    assert not any(ch.isdigit() for ch in stripped)


class FakeOpenRouter:
    def __init__(self, replies: dict[str, str], prices: dict[str, float]) -> None:
        self.replies, self.prices, self.calls = replies, prices, []

    def handler(self, req: httpx.Request) -> httpx.Response:
        if req.url.path.endswith("/models"):
            data = [{"id": m, "pricing": {"prompt": str(p), "completion": str(p)}}
                    for m, p in self.prices.items()]  # fmt: skip
            return httpx.Response(200, json={"data": data})
        body = json.loads(req.content)
        self.calls.append(body["model"])
        assert req.headers["authorization"] == "Bearer test-key"
        return httpx.Response(200, json={
            "choices": [{"message": {"content": self.replies[body["model"]]}}],
            "usage": {"prompt_tokens": 1000, "completion_tokens": 200},
        })  # fmt: skip


def run(fake: FakeOpenRouter, cfg: NarratorConfig, tmp_path: Path):
    return narrate(FACTS, cfg, "test-key", httpx.MockTransport(fake.handler), tmp_path)


def test_fallback_chain_skips_invalid_and_unknown_models(tmp_path: Path) -> None:
    fake = FakeOpenRouter(
        {"a/digits:free": "There are 623 feeders.", "b/good:free": GOOD},
        {"a/digits:free": 0.0, "b/good:free": 0.0},
    )
    cfg = NarratorConfig(models=["x/missing", "a/digits:free", "b/good:free"])
    res = run(fake, cfg, tmp_path)
    assert res.model == "b/good:free" and res.draft == GOOD
    assert res.attempts[0].startswith("x/missing: not in OpenRouter model list")
    assert "rejected" in res.attempts[1] and "accepted" in res.attempts[2]


def test_spend_cap_and_cache(tmp_path: Path) -> None:
    pricey = FakeOpenRouter({"p/expensive": GOOD}, {"p/expensive": 0.01})
    res = run(pricey, NarratorConfig(models=["p/expensive"], spend_cap_usd=0.05), tmp_path)
    assert res.draft is None and pricey.calls == [] and "exceeds remaining cap" in res.attempts[0]

    cheap = FakeOpenRouter({"c/cheap": GOOD}, {"c/cheap": 1e-7})
    cfg = NarratorConfig(models=["c/cheap"], spend_cap_usd=0.05)
    first = run(cheap, cfg, tmp_path)
    assert first.draft == GOOD and first.spent_usd == pytest.approx(1200 * 1e-7)
    second = run(cheap, cfg, tmp_path)
    assert cheap.calls == ["c/cheap"] and "cache" in second.attempts[0] and second.spent_usd == 0


def test_zero_cap_runs_only_free_models(tmp_path: Path) -> None:
    """The daily job's $0 cap: paid models are skipped, a free model still runs."""
    fake = FakeOpenRouter(
        {"p/paid": GOOD, "f/free:free": GOOD}, {"p/paid": 1e-7, "f/free:free": 0.0}
    )
    res = run(fake, NarratorConfig(models=["p/paid", "f/free:free"], spend_cap_usd=0.0), tmp_path)
    assert fake.calls == ["f/free:free"] and res.model == "f/free:free" and res.spent_usd == 0
    assert "exceeds remaining cap" in res.attempts[0]


def test_auto_falls_back_to_template_when_openrouter_is_down(monkeypatch, tmp_path: Path) -> None:
    from roshni.narrate import report

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(report.facts_mod, "collect", lambda con: FACTS)
    monkeypatch.setattr(report, "TEMPLATE", GOOD)  # a template valid for the small FACTS set
    down = httpx.MockTransport(lambda req: httpx.Response(503, json={"error": "down"}))
    rep = report.build_report(None, engine="auto", transport=down)
    assert rep.data["engine"] == "template"
    assert any("openrouter unavailable" in a for a in rep.data["narrator_log"])
    with pytest.raises(httpx.HTTPError):
        report.build_report(None, engine="openrouter", transport=down)


def test_empty_reply_is_skipped_not_fatal(tmp_path: Path) -> None:
    """Regression (publish 2026-10-13): a free model returned content null -> TypeError."""
    fake = FakeOpenRouter({"r/thinker:free": None, "b/good:free": GOOD},
                          {"r/thinker:free": 0.0, "b/good:free": 0.0})  # fmt: skip
    res = run(fake, NarratorConfig(models=["r/thinker:free", "b/good:free"]), tmp_path)
    assert res.model == "b/good:free"
    assert res.attempts[0].startswith("r/thinker:free: empty response")


def test_busy_endpoint_is_retried_once(monkeypatch, tmp_path: Path) -> None:
    from roshni.narrate import openrouter

    waits: list[float] = []
    monkeypatch.setattr(openrouter, "_sleep", waits.append)
    fake = FakeOpenRouter({"g/busy:free": GOOD}, {"g/busy:free": 0.0})
    hits = {"n": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path.endswith("/chat/completions"):
            hits["n"] += 1
            if hits["n"] == 1:
                return httpx.Response(429, headers={"retry-after": "3"})
            assert json.loads(req.content)["reasoning"] == {"effort": "low"}
        return fake.handler(req)

    cfg = NarratorConfig(models=["g/busy:free"])
    res = narrate(FACTS, cfg, "test-key", httpx.MockTransport(handler), tmp_path)
    assert res.model == "g/busy:free" and waits == [3.0] and hits["n"] == 2


def test_error_body_with_http_200_moves_to_next_model(tmp_path: Path) -> None:
    """Regression (publish 2026-10-13): 200 with {"error": ...} and no choices stopped the chain."""
    fake = FakeOpenRouter({"b/good:free": GOOD}, {"e/err:free": 0.0, "b/good:free": 0.0})

    def handler(req: httpx.Request) -> httpx.Response:
        if (
            req.url.path.endswith("/chat/completions")
            and json.loads(req.content)["model"] == "e/err:free"
        ):
            return httpx.Response(200, json={"error": {"message": "Provider returned error"}})
        return fake.handler(req)

    cfg = NarratorConfig(models=["e/err:free", "b/good:free"])
    res = narrate(FACTS, cfg, "test-key", httpx.MockTransport(handler), tmp_path)
    assert res.model == "b/good:free"
    assert res.attempts[0] == "e/err:free: provider error (Provider returned error), skipped"


WORD_FACTS = [*FACTS, Fact("medium_12h", "Medium feeders at 12 h", 2, "count", "medium_12h")]


@pytest.mark.parametrize(
    "text",
    [
        "Two Medium-category feeders are scheduled at twelve hours.",  # 2 is a fact value
        "{coverage_listed_feeders} feeders: most at twelve hours, the rest for six (see above).",
        "a six-hour band and a twelve-hour band",
        "Among IBC areas with at least ten scheduled feeders, the share varies.",
        "No one area dominates; this is often described as uneven.",  # "often", "no one"
    ],
)
def test_number_words_allowed(text: str) -> None:
    assert not [p for p in check_draft(text, WORD_FACTS) if "number word" in p]


@pytest.mark.parametrize(
    "text, word",
    [
        ("Three IBC areas have every feeder at twelve hours.", "Three"),  # 3 is no fact value
        ("Twenty-one feeders are exempt.", "Twenty-one"),
        ("About half of the feeders are scheduled.", "half"),
        ("six feeders have no schedule row", "six"),  # band word used as a count
        ("ten IBC areas are listed", "ten"),  # threshold word used as a count
    ],
)
def test_number_words_rejected(text: str, word: str) -> None:
    assert f"number word {word!r} is not a fact value" in check_draft(text, WORD_FACTS)


def test_published_narrative_style_passes() -> None:
    """The accepted 2026-W42 draft wrote "Two Medium loss-category feeders": still valid."""
    draft = "Two Medium loss-category feeders are scheduled at twelve hours instead of six."
    assert check_draft(draft, WORD_FACTS) == []


def test_out_of_credits_falls_through_to_free_models(tmp_path: Path) -> None:
    """Owner: prepaid credits first; when they run out (402), free models take over."""
    fake = FakeOpenRouter({"f/free:free": GOOD}, {"p/cheap": 1e-7, "f/free:free": 0.0})
    sent: dict[str, dict] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path.endswith("/chat/completions"):
            body = json.loads(req.content)
            sent[body["model"]] = body
            if body["model"] == "p/cheap":
                return httpx.Response(402, json={"error": {"message": "Insufficient credits"}})
        return fake.handler(req)

    cfg = NarratorConfig(models=["p/cheap", "f/free:free"], spend_cap_usd=0.01)
    res = narrate(FACTS, cfg, "test-key", httpx.MockTransport(handler), tmp_path)
    assert res.model == "f/free:free"
    assert res.attempts[0] == "p/cheap: HTTP 402 (out of credits)"
    assert sent["p/cheap"]["reasoning"] == sent["f/free:free"]["reasoning"] == {"effort": "low"}


def test_cut_off_draft_is_rejected(tmp_path: Path) -> None:
    """Regression (publish 2026-10-13): Haiku hit max_tokens mid-placeholder and was published."""
    cut = "Rho is {rho_literacy_rho} (n = {rho_literacy_n}). Then rho = {rho_loss_hours_r"
    assert any("broken placeholder" in p for p in check_draft(cut, FACTS))

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "h/haiku", "pricing": {}}]})
        return httpx.Response(200, json={"choices": [
            {"message": {"content": GOOD}, "finish_reason": "length"}]})  # fmt: skip

    res = narrate(FACTS, NarratorConfig(models=["h/haiku"]), "test-key",
                  httpx.MockTransport(handler), tmp_path)  # fmt: skip
    assert res.draft is None and res.attempts == ["h/haiku: truncated at max_tokens, skipped"]


def test_invalid_cached_draft_is_discarded_and_model_asked_again(tmp_path: Path) -> None:
    """Regression (publish 2026-10-13): a bad cached draft blocked the model on every run."""
    fake = FakeOpenRouter({"c/cheap": GOOD}, {"c/cheap": 1e-7})
    cfg = NarratorConfig(models=["c/cheap"], spend_cap_usd=0.05)
    run(fake, cfg, tmp_path)  # caches GOOD
    (cache_file,) = tmp_path.glob("*.json")
    cache_file.write_text(json.dumps({"model": "c/cheap", "draft": "rho = {rho_lo"}), "utf-8")
    res = run(fake, cfg, tmp_path)
    assert res.draft == GOOD and fake.calls == ["c/cheap", "c/cheap"]
    assert res.attempts[0] == "c/cheap: cached draft no longer valid, discarded"
