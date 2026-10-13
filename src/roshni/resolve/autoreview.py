"""Automatic review of press-release feeder suggestions (owner, 2026-10-13).

Codifies the written review rules of DECISIONS 2026-10-10 for the cases they decide mechanically;
everything else stays pending for a delegated review. Only rows with status `suggested` and no
decision are touched, so every earlier decision (owner or Claude) is kept.

Rules, in order, on names normalised with numbers kept (roman numerals become digits, Dk/Dk. =
Dhoke, the izafat "e" in "Gulshan e Sehat" is dropped):
- reject: the subject already has an exact or accepted match;
- reject: both names carry numbers and they differ ("Scheme-II" vs "SCHEME-I");
- accept: the bracketed part names the feeder ("F-10 (Kala Base)" vs "KALA BASE");
- reject: the names differ only in single letters ("Sector-C" vs "SECTOR D", "A-Block" vs
  "B BLOCK");
- accept: same number of words, and every word has the same consonant skeleton (vowels, H and
  doubled letters ignored) AND the same ending vowels, and no other candidate qualifies.
  The ending check keeps out the overturned "extra syllable" cases (JALALA/JALALIA, SOHAN/SOHANA,
  BANNI/BANN) while accepting spelling variants (Haidri/Haideri, Chaudrian/Chodrian);
- otherwise left pending, e.g. a number on one side only ("PHA-1" vs "PHA", "Sector A-2" vs
  "SECTOR A"), which the earlier reviews decided case by case.
"""

import re
from collections import defaultdict

from roshni.resolve.names import normalise

ROMAN = {
    "I": "1", "II": "2", "III": "3", "IV": "4", "V": "5", "VI": "6", "VII": "7", "VIII": "8",
    "IX": "9", "X": "10", "XI": "11", "XII": "12",
}  # fmt: skip
ABBREVIATIONS = {"DK": "DHOKE", "PSR": "PESHAWAR", "CLY": "COLONY"}
VOWELS = "AEIOUY"
NOTE = "auto-review: "


def tokens(name: str) -> list[str]:
    raw = normalise(name, keep_numbers=True).split()
    # "G8" -> G 8 (as "G-8" already is); "08" -> 8; roman numerals and abbreviations expanded.
    parts = [p for t in raw for p in re.findall(r"[A-Z]+|\d+", t)]
    toks = [str(int(t)) if t.isdigit() else ROMAN.get(t, ABBREVIATIONS.get(t, t)) for t in parts]

    def izafat(i: int) -> bool:
        return 0 < i < len(toks) - 1 and len(toks[i - 1]) > 2 and len(toks[i + 1]) > 2

    return [t for i, t in enumerate(toks) if not (t == "E" and izafat(i))]


def skeleton(word: str) -> str:
    consonants = re.sub(f"[{VOWELS}H]", "", word)
    return re.sub(r"(.)\1+", r"\1", consonants)


def ending(word: str) -> str:
    return re.search(f"[{VOWELS}]*$", word).group(0)


def _same_words(a: list[str], b: list[str]) -> bool:
    return len(a) == len(b) and all(
        skeleton(x) == skeleton(y) and ending(x) == ending(y) for x, y in zip(a, b, strict=True)
    )


def decide(subject: str, candidate: str) -> tuple[str, str]:
    """('rejected' | 'match' | '', reason) for one subject/candidate pair."""
    a, b = tokens(subject), tokens(candidate)
    digits_a = sorted(t for t in a if t.isdigit())
    digits_b = sorted(t for t in b if t.isdigit())
    words_a = [t for t in a if not t.isdigit()]
    words_b = [t for t in b if not t.isdigit()]
    if digits_a and digits_b and digits_a != digits_b:
        return "rejected", "numbers differ"
    for inner in re.findall(r"\((.*?)\)", subject):  # "F-10 (Kala Base)" -> KALA BASE
        inner_words = [t for t in tokens(inner) if not t.isdigit()]
        if inner_words and not digits_b and _same_words(inner_words, words_b):
            return "match", "the bracketed name matches the feeder"
    long_a = [t for t in words_a if len(t) > 1]
    long_b = [t for t in words_b if len(t) > 1]
    if long_a == long_b and words_a != words_b:
        return "rejected", "names differ only in single letters"
    if digits_a == digits_b and _same_words(words_a, words_b):
        return "match", "same consonant skeleton and endings: spelling variant"
    # A number on one side only ("PHA-1" vs PHA, "Sector A-2" vs SECTOR A) needs judgment.
    return "", ""


def review_press(rows: list[dict]) -> dict[str, int]:
    """Fill `decision`/`note` on undecided suggested rows in place; return counts."""
    by_subject: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_subject[r["subject_id"]].append(r)
    counts = {"accepted": 0, "rejected": 0, "pending": 0}
    for subject_rows in by_subject.values():
        settled = any(
            r["status"] == "auto_exact" or r.get("decision") == "accepted" for r in subject_rows
        )
        open_rows = [r for r in subject_rows if r["status"] == "suggested" and not r["decision"]]
        if not open_rows:
            continue
        if settled:
            for r in open_rows:
                r["decision"], r["note"] = (
                    "rejected",
                    NOTE + "subject already has an exact or accepted match",
                )
                counts["rejected"] += 1
            continue
        verdicts = {id(r): decide(r["subject_name"], r["candidate_name"]) for r in open_rows}
        matches = [r for r in open_rows if verdicts[id(r)][0] == "match"]
        for r in open_rows:
            verdict, reason = verdicts[id(r)]
            if verdict == "rejected":
                r["decision"], r["note"] = "rejected", NOTE + reason
                counts["rejected"] += 1
            elif len(matches) == 1 and r is matches[0]:
                r["decision"], r["note"] = "accepted", NOTE + reason
                counts["accepted"] += 1
            elif len(matches) == 1:
                r["decision"], r["note"] = "rejected", NOTE + "another candidate matched"
                counts["rejected"] += 1
            else:
                counts["pending"] += 1
    return counts
