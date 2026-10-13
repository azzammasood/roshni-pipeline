"""OpenRouter narrator (OpenAI-compatible API): prose only, validated, cached, spend-capped.

- API key from OPENROUTER_API_KEY; models from config/narrator.yml (fallback chain, first that
  exists in the live model list and passes validation wins); ROSHNI_NARRATOR_MODEL prepends one.
- Prices are read live from GET /models (never hardcoded); a call is skipped if its worst-case
  cost would exceed what is left of the per-run cap.
- Responses are cached by a hash of (model, prompt) under data/cache/narrate/.
- A cheap paid model uses prepaid credits first; free (":free") models end the chain and take over
  when credits run out (HTTP 402). Owner, 2026-10-13. Tests use a mocked API.
"""

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx
import yaml

from roshni.narrate.facts import Fact
from roshni.narrate.validate import check_draft
from roshni.paths import CONFIG_DIR, DATA_DIR

_sleep = time.sleep  # patched in tests

API = "https://openrouter.ai/api/v1"
CACHE_DIR = DATA_DIR / "cache" / "narrate"
SYSTEM = """You write short, neutral prose for a public data report about PUBLISHED electricity
load-shed SCHEDULES in Karachi (not measured outages). Rules, all mandatory:
1. Never write any digit. Every number must be a placeholder: the id of a fact from the list
   inside curly braces, e.g. {coverage_listed_feeders}. Do not invent placeholders. The two
   K-Electric schedule bands are written as words: "twelve hours" and "six hours".
2. Descriptive only: no causal language (no "because", "due to", "caused", "leads to"), no
   claims of discrimination or unfairness, no speculation about motives.
3. Say that shares are among listed feeders only, that schedules are not measurements, and
   that the correlations are exploratory with their n.
4. Use each fact ONLY with the meaning given for it. Formats, shown with real ids from the list:
   a percentage as {hours_split_share_12h_pct}% ; a sample size as n = {rho_loss_hours_n} ; a
   correlation as rho = {rho_loss_hours_rho} . Counts are numbers of feeders or areas, never
   hours or percentages. Do not expand abbreviations such as IBC or ATC.
   Facts whose meaning ends with "(its n)" are sample sizes: write each one ONLY as
   "n = {id}" in brackets right after the figure it belongs to, e.g.
   "rho = {rho_loss_hours_rho} (n = {rho_loss_hours_n})" or "{ibc_highest_share_12h_pct}%
   (n = {ibc_highest_n})". Never write a sample size as a plain count ("across {id} feeders").
5. Three or four short paragraphs, plain English, no headings (no '#'), no lists."""


@dataclass
class NarratorConfig:
    models: list[str]
    max_tokens: int = 4000
    temperature: float = 0.2
    spend_cap_usd: float = 0.05

    @classmethod
    def load(cls, path: Path | None = None) -> "NarratorConfig":
        data = yaml.safe_load((path or CONFIG_DIR / "narrator.yml").read_text(encoding="utf-8"))
        cfg = cls(**data)
        if m := os.environ.get("ROSHNI_NARRATOR_MODEL"):
            cfg.models = [m, *[x for x in cfg.models if x != m]]
        if cap := os.environ.get("ROSHNI_NARRATOR_SPEND_CAP_USD"):
            cfg.spend_cap_usd = float(cap)
        return cfg


@dataclass
class NarrationResult:
    draft: str | None
    model: str | None
    spent_usd: float
    attempts: list[str] = field(default_factory=list)  # one line per model tried


def build_prompt(facts: list[Fact]) -> str:
    listing = [{"id": f.id, "meaning": f.label, "value": f.value, "unit": f.unit} for f in facts]
    return (
        "Facts (use only these, as {id} placeholders; the values are shown so you can choose "
        "what to say, never copy them):\n" + json.dumps(listing, default=str, indent=1)
    )


def _price(model_info: dict) -> tuple[float, float]:
    p = model_info.get("pricing", {})
    return float(p.get("prompt", 0) or 0), float(p.get("completion", 0) or 0)


def narrate(
    facts: list[Fact],
    cfg: NarratorConfig,
    api_key: str,
    transport: httpx.BaseTransport | None = None,
    cache_dir: Path = CACHE_DIR,
) -> NarrationResult:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "https://github.com/azzammasood/roshni-pipeline",
        "X-Title": "roshni-pipeline",
    }
    prompt = build_prompt(facts)
    result = NarrationResult(None, None, 0.0)
    with httpx.Client(base_url=API, headers=headers, timeout=60, transport=transport) as http:
        live = {m["id"]: m for m in http.get("/models").raise_for_status().json()["data"]}
        for model in cfg.models:
            if model not in live:
                result.attempts.append(f"{model}: not in OpenRouter model list, skipped")
                continue
            key = hashlib.sha256(json.dumps([model, SYSTEM, prompt]).encode()).hexdigest()
            cached = cache_dir / f"{key}.json"
            draft = None
            if cached.exists():
                draft = json.loads(cached.read_text(encoding="utf-8"))["draft"]
                note = "cache"
                if check_draft(draft, facts):  # stale or bad cache (e.g. stricter rules): ask again
                    cached.unlink()
                    result.attempts.append(f"{model}: cached draft no longer valid, discarded")
                    draft = None
            if draft is None:
                p_in, p_out = _price(live[model])
                worst = (len(SYSTEM) + len(prompt)) / 3 * p_in + cfg.max_tokens * p_out
                if result.spent_usd + worst > cfg.spend_cap_usd:
                    result.attempts.append(
                        f"{model}: worst-case ${worst:.4f} exceeds remaining cap, skipped"
                    )
                    continue
                request = {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": SYSTEM},
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": cfg.max_tokens,
                    "temperature": cfg.temperature,
                    # Reasoning models (free ones, and Haiku 5.5 by default) otherwise spend most
                    # of the budget thinking and return null or cut-off text.
                    "reasoning": {"effort": "low"},
                }
                resp = http.post("/chat/completions", json=request)
                if resp.status_code == 429:  # busy free endpoint: one retry after a short wait
                    _sleep(min(float(resp.headers.get("retry-after") or 15), 20))
                    resp = http.post("/chat/completions", json=request)
                if resp.status_code != 200:
                    why = " (out of credits)" if resp.status_code == 402 else ""
                    result.attempts.append(f"{model}: HTTP {resp.status_code}{why}")
                    continue
                body = resp.json()
                usage = body.get("usage", {})
                result.spent_usd += (
                    usage.get("prompt_tokens", 0) * p_in + usage.get("completion_tokens", 0) * p_out
                )
                if not body.get("choices"):  # OpenRouter can answer 200 with an error object
                    err = (body.get("error") or {}).get("message", "no choices")
                    result.attempts.append(f"{model}: provider error ({str(err)[:120]}), skipped")
                    continue
                choice = body["choices"][0]
                draft = choice["message"].get("content")
                if not isinstance(draft, str) or not draft.strip():
                    # e.g. a reasoning model that spent max_tokens thinking: content is null
                    why = choice.get("finish_reason") or "no finish_reason"
                    result.attempts.append(f"{model}: empty response ({why}), skipped")
                    continue
                if choice.get("finish_reason") == "length":  # cut off: never publish half a text
                    result.attempts.append(f"{model}: truncated at max_tokens, skipped")
                    continue
                tokens_in, tokens_out = (
                    usage.get("prompt_tokens", "?"),
                    usage.get("completion_tokens", "?"),
                )
                note = f"{tokens_in}+{tokens_out} tokens"
            problems = check_draft(draft, facts)
            if problems:
                result.attempts.append(f"{model}: rejected ({'; '.join(problems)})")
                continue
            if note != "cache":
                cached.parent.mkdir(parents=True, exist_ok=True)
                cached.write_text(json.dumps({"model": model, "draft": draft}), encoding="utf-8")
            result.attempts.append(f"{model}: accepted ({note})")
            result.draft, result.model = draft, model
            return result
    return result
