"""Provider chain: Groq first, OpenRouter as fallback (config/llm.yml).

- One OpenAI-compatible `/chat/completions` call per attempt; the first reply that `check`
  accepts wins. A provider whose key env var is unset is skipped, not an error.
- HTTP 429: one retry after Retry-After when it is at most `max_wait_s`, else the next model.
- Every attempt is recorded (provider, model, outcome, tokens, latency) so callers can report
  cost and speed; the eval harness aggregates these.
- `only` pins the chain to one "provider/model" (used by `roshni ask-eval`).
"""

import json
import os
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import httpx
import yaml

from roshni.paths import CONFIG_DIR

_sleep = time.sleep  # patched in tests


@dataclass
class Model:
    id: str
    params: dict = field(default_factory=dict)


@dataclass
class Provider:
    name: str
    base_url: str
    key_env: str
    models: list[Model]
    headers: dict = field(default_factory=dict)


@dataclass
class ChainConfig:
    providers: list[Provider]
    max_tokens: int = 2000
    temperature: float = 0.0
    max_wait_s: float = 20
    guard: dict = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path | None = None) -> "ChainConfig":
        raw = yaml.safe_load((path or CONFIG_DIR / "llm.yml").read_text(encoding="utf-8"))
        providers = [
            Provider(
                name=p["name"],
                base_url=p["base_url"],
                key_env=p["key_env"],
                headers=p.get("headers") or {},
                models=[Model(m["id"], m.get("params") or {}) for m in p["models"]],
            )
            for p in raw.pop("providers")
        ]
        return cls(providers=providers, **raw)

    def pinned(self, only: str) -> "ChainConfig":
        """A copy with just one 'provider/model' (model ids may contain '/')."""
        name, _, model_id = only.partition("/")
        for p in self.providers:
            if p.name == name:
                models = [m for m in p.models if m.id == model_id] or [Model(model_id)]
                prov = Provider(p.name, p.base_url, p.key_env, models, p.headers)
                return ChainConfig([prov], self.max_tokens, self.temperature, self.max_wait_s,
                                   self.guard)  # fmt: skip
        raise ValueError(f"unknown provider in {only!r}")

    def labels(self) -> list[str]:
        return [f"{p.name}/{m.id}" for p in self.providers for m in p.models]


@dataclass
class Attempt:
    provider: str
    model: str
    outcome: str  # accepted | rejected: ... | HTTP 429 | skipped: ...
    tokens_in: int = 0
    tokens_out: int = 0
    latency_s: float = 0.0

    @property
    def label(self) -> str:
        return f"{self.provider}/{self.model}"


@dataclass
class Completion:
    text: str | None
    attempts: list[Attempt]

    @property
    def accepted(self) -> Attempt | None:
        return next((a for a in self.attempts if a.outcome == "accepted"), None)

    @property
    def tokens(self) -> int:
        return sum(a.tokens_in + a.tokens_out for a in self.attempts)


def _client(p: Provider, key: str, transport: httpx.BaseTransport | None) -> httpx.Client:
    headers = {"Authorization": f"Bearer {key}", **p.headers}
    return httpx.Client(base_url=p.base_url, headers=headers, timeout=60, transport=transport)


def complete(
    messages: list[dict],
    cfg: ChainConfig,
    check: Callable[[str], list[str]] = lambda _t: [],
    *,
    json_mode: bool = False,
    transport: httpx.BaseTransport | None = None,
) -> Completion:
    """Walk providers and models; return the first reply `check` finds no problems with."""
    attempts: list[Attempt] = []
    for p in cfg.providers:
        key = os.environ.get(p.key_env)
        if not key:
            attempts.append(Attempt(p.name, "*", f"skipped: {p.key_env} not set"))
            continue
        with _client(p, key, transport) as http:
            for m in p.models:
                body = {
                    "model": m.id,
                    "messages": messages,
                    "max_tokens": cfg.max_tokens,
                    "temperature": cfg.temperature,
                    **m.params,
                }
                if json_mode:
                    body["response_format"] = {"type": "json_object"}
                t0 = time.perf_counter()
                resp = http.post("/chat/completions", json=body)
                if resp.status_code == 429:
                    wait = float(resp.headers.get("retry-after") or cfg.max_wait_s + 1)
                    if wait <= cfg.max_wait_s:
                        _sleep(wait)
                        t0 = time.perf_counter()
                        resp = http.post("/chat/completions", json=body)
                latency = time.perf_counter() - t0
                att = Attempt(p.name, m.id, "", latency_s=round(latency, 3))
                attempts.append(att)
                if resp.status_code != 200:
                    att.outcome = f"HTTP {resp.status_code}"
                    continue
                data = resp.json()
                usage = data.get("usage") or {}
                att.tokens_in = usage.get("prompt_tokens", 0)
                att.tokens_out = usage.get("completion_tokens", 0)
                choice = (data.get("choices") or [{}])[0]
                text = (choice.get("message") or {}).get("content")
                if not isinstance(text, str) or not text.strip():
                    att.outcome = f"rejected: empty ({choice.get('finish_reason')})"
                    continue
                if choice.get("finish_reason") == "length":
                    att.outcome = "rejected: truncated"
                    continue
                problems = check(text)
                if problems:
                    att.outcome = "rejected: " + "; ".join(problems)[:300]
                    continue
                att.outcome = "accepted"
                return Completion(text, attempts)
    return Completion(None, attempts)


def guard_score(
    text: str, cfg: ChainConfig, transport: httpx.BaseTransport | None = None
) -> float | None:
    """Prompt-injection probability from the guard model; None when it cannot be reached."""
    g = cfg.guard
    prov = next((p for p in cfg.providers if p.name == g.get("provider")), None)
    key = prov and os.environ.get(prov.key_env)
    if not prov or not key:
        return None
    with _client(prov, key, transport) as http:
        resp = http.post(
            "/chat/completions",
            json={"model": g["model"], "messages": [{"role": "user", "content": text}]},
        )
    if resp.status_code != 200:
        return None
    try:
        return float(resp.json()["choices"][0]["message"]["content"].strip())
    except (KeyError, IndexError, ValueError, AttributeError):
        return None


def parse_json(text: str) -> dict:
    """JSON object from a reply, tolerating a ```json fence."""
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`")
        t = t[t.find("{") :]
    return json.loads(t)
