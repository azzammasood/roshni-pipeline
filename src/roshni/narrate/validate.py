"""Prose validation: the writer (LLM or template) may not state numbers itself.

Rules for a draft:
- numbers appear only as {fact_id} placeholders; any digit outside a placeholder is rejected;
- every placeholder names a known fact;
- no causal or accusatory wording (statistics here are descriptive only).
After rendering, every number in the text must be a rendered fact value.
"""

import re

from roshni.narrate.facts import Fact

PLACEHOLDER = re.compile(r"\{([a-z0-9_]+)\}")
CAUSAL = re.compile(
    r"(?i)\b(because|caus(e|es|ed|ing)|due to|result(s|ed)? (in|from)|leads? to|"
    r"driv(e|es|en|ing) by|"
    r"discriminat\w*|unfair\w*|punish\w*|deliberate\w*|target(s|ed|ing)?)\b"
)
NUMBER = re.compile(r"\d+(?:[.,]\d+)*")


class InvalidDraft(ValueError):
    pass


def check_draft(draft: str, facts: list[Fact]) -> list[str]:
    known = {f.id for f in facts}
    problems = []
    stripped = PLACEHOLDER.sub("", draft)
    if (m := NUMBER.search(stripped)) is not None:
        problems.append(f"number written outside a placeholder: {m.group(0)!r}")
    unknown = sorted(set(PLACEHOLDER.findall(draft)) - known)
    if unknown:
        problems.append(f"unknown placeholders: {unknown}")
    if (m := CAUSAL.search(draft)) is not None:
        problems.append(f"causal or accusatory wording: {m.group(0)!r}")
    if not draft.strip():
        problems.append("empty draft")
    return problems


def render(draft: str, facts: list[Fact]) -> str:
    """Fill placeholders, then verify every number in the result comes from a fact."""
    problems = check_draft(draft, facts)
    if problems:
        raise InvalidDraft("; ".join(problems))
    by_id = {f.id: f for f in facts}
    text = PLACEHOLDER.sub(lambda m: by_id[m.group(1)].rendered(), draft)
    allowed: set[str] = set()
    for f in facts:
        allowed.update(NUMBER.findall(f.rendered()))
    stray = [n for n in NUMBER.findall(text) if n not in allowed]
    if stray:
        raise InvalidDraft(f"numbers not traceable to facts: {stray}")
    return text
