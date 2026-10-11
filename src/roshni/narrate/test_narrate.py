import json
from pathlib import Path

import httpx
import pytest

from roshni.narrate.facts import Fact
from roshni.narrate.openrouter import NarratorConfig, narrate
from roshni.narrate.template import TEMPLATE
from roshni.narrate.validate import PLACEHOLDER, InvalidDraft, check_draft, render

FACTS = [
    Fact("coverage_listed_feeders", "coverage.listed_feeders", 623, "feeders", "coverage"),
    Fact("hours_split_share_12h_pct", "hours_split.share_12h_pct", 79.7, "%", "hours_split"),
    Fact("ibc_highest_name", "ibc_highest.name", "IBC - Clifton", "text", "ibc_highest"),
    Fact("rho_literacy_rho", "rho_literacy.rho", -0.39, "rho", "rho_literacy"),
    Fact("rho_literacy_n", "rho_literacy.n", 13, "feeders", "rho_literacy"),
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
