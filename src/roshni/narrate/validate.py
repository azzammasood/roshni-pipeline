"""Prose validation: the writer (LLM or template) may not state numbers itself.

Rules for a draft:
- numbers appear only as {fact_id} placeholders; any digit outside a placeholder is rejected;
- a number written as words ("two", "twenty-one") must equal a fact value, except the schedule
  bands ("twelve hours", "six") and the small-n threshold ("at least ten");
- every placeholder names a known fact;
- no causal or accusatory wording (statistics here are descriptive only);
- units are respected: a percentage is followed by "%", a sample size follows "n =", a
  correlation sits next to "rho" or "correlation", a count is never followed by "%" or "hour";
- no headings;
- the highest/lowest IBC facts only cover areas with at least ten scheduled feeders, so a draft
  that names one must say "at least ten" (otherwise a smaller area on the chart looks lower).
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

_UNITS = [
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
    "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen",
    "nineteen",
]  # fmt: skip
_TENS = ["twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
WORD_VALUE = {w: i for i, w in enumerate(_UNITS)} | {w: 20 + 10 * i for i, w in enumerate(_TENS)}
SCALE = {"hundred": 100, "thousand": 1000, "million": 1_000_000}
_WORD = "|".join([*WORD_VALUE, *SCALE])
# A run of number words: "two", "twenty-one", "two hundred and fifteen"; "half"/"dozen" too.
NUMBER_WORDS = re.compile(
    rf"(?i)\b(?:(?:{_WORD})(?:[\s-]+(?:and[\s-]+)?(?:{_WORD}))*|half|dozen)\b"
)
# Constants the prose may name in words: the two K-Electric schedule bands, and the threshold.
BAND = re.compile(r"(?i)^\s*(?:-\s*)?hours?\b|^\s*(?:[(),.;:]|$)")
THRESHOLD = re.compile(r"(?i)\b(?:at least|fewer than|more than)\s+$")


def words_to_number(text: str) -> float | None:
    """Value of a run of English number words; None for words without a single value."""
    words = [w for w in re.split(r"[\s-]+", text.lower()) if w and w != "and"]
    if words in (["half"], ["dozen"]):
        return {"half": 0.5, "dozen": 12.0}[words[0]]
    total = current = 0
    for w in words:
        if w in WORD_VALUE:
            current += WORD_VALUE[w]
        elif w == "hundred":
            current = max(current, 1) * 100
        else:  # thousand / million
            total += max(current, 1) * SCALE[w]
            current = 0
    return float(total + current)


def _number_word_problems(draft: str, facts: list[Fact]) -> list[str]:
    values = {float(f.value) for f in facts if isinstance(f.value, int | float)}
    problems = []
    for m in NUMBER_WORDS.finditer(draft):
        word, after, before = m.group(0), draft[m.end() : m.end() + 12], draft[: m.start()]
        if re.search(r"(?i)\bno\s+$", before) and word.lower() == "one":
            continue  # "no one"
        value = words_to_number(word)
        if value in (6.0, 12.0) and word.lower() in ("six", "twelve") and BAND.match(after):
            continue
        if value == 10.0 and THRESHOLD.search(before[-20:]):
            continue
        if value not in values:
            problems.append(f"number word {word!r} is not a fact value")
    return problems


class InvalidDraft(ValueError):
    pass


def check_draft(draft: str, facts: list[Fact]) -> list[str]:
    known = {f.id for f in facts}
    problems = []
    stripped = PLACEHOLDER.sub("", draft)
    if (m := NUMBER.search(stripped)) is not None:
        problems.append(f"number written outside a placeholder: {m.group(0)!r}")
    problems += _number_word_problems(stripped, facts)
    if (m := re.search(r"[{}][^{}]{0,30}", stripped)) is not None:  # e.g. cut off mid-placeholder
        problems.append(f"broken placeholder: {m.group(0)!r}")
    unknown = sorted(set(PLACEHOLDER.findall(draft)) - known)
    if unknown:
        problems.append(f"unknown placeholders: {unknown}")
    if (m := CAUSAL.search(draft)) is not None:
        problems.append(f"causal or accusatory wording: {m.group(0)!r}")
    if not draft.strip():
        problems.append("empty draft")
    if re.search(r"(?m)^\s*#", draft):
        problems.append("headings are not allowed")
    named_ibc = re.search(r"\{ibc_(highest|lowest)_", draft)
    if named_ibc and not re.search(r"(?i)\bat least ten\b", draft):
        problems.append("highest/lowest IBC named without 'at least ten scheduled feeders'")
    units = {f.id: f.unit for f in facts}
    for m in PLACEHOLDER.finditer(draft):
        unit = units.get(m.group(1))
        before, after = draft[max(0, m.start() - 60) : m.start()], draft[m.end() : m.end() + 12]
        if unit == "%" and not after.startswith("%"):
            problems.append(f"percentage {{{m.group(1)}}} not followed by '%'")
        elif unit == "n" and not re.search(r"(?:^|[^a-z])n\s*=\s*$", before):
            problems.append(f"sample size {{{m.group(1)}}} not written as 'n = ...'")
        elif unit == "rho" and not re.search(r"(?i)rho|correlation", before):
            problems.append(f"correlation {{{m.group(1)}}} not introduced as rho/correlation")
        elif unit == "count" and re.match(r"\s*(%|-?\s*hours?(?![a-z]))", after, re.I):
            problems.append(f"count {{{m.group(1)}}} used as a percentage or hours")
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
