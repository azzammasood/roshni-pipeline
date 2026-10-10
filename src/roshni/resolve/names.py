"""Name normalisation and candidate scoring shared by all matchers."""

import re
from dataclasses import dataclass

from rapidfuzz import fuzz, process

# Tokens that carry no identity for matching (utility and census boilerplate).
STOP = {
    "FEEDER", "FDR", "GRID", "NO", "THE", "AND",
    "MC", "TC", "MCI", "CANTONMENT", "CANTT", "MUNICIPAL", "COMMITTEE", "CORPORATION",
    "METROPOLITAN", "TOWN", "SUB", "DIVISION",
}  # fmt: skip
ROMAN = {
    "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X",
    "XI", "XII", "XIII", "XIV", "XV", "XVI", "XVII", "XVIII", "XIX", "XX",
}  # fmt: skip


def normalise(name: str, keep_numbers: bool = False) -> str:
    """Uppercase, alphanumerics only, boilerplate dropped.

    Numbers and roman numerals are dropped unless keep_numbers (feeder-to-feeder matching must
    keep them: "Club-1" and "Club-2" are different feeders; "BHARAKHAU 1" still names a village).
    """
    s = re.sub(r"[^A-Z0-9]+", " ", name.upper().replace("&", " AND "))
    toks = [
        t for t in s.split()
        if t not in STOP and (keep_numbers or (t not in ROMAN and not t.isdigit()))
    ]  # fmt: skip
    return " ".join(toks)


def variants(name: str, keep_numbers: bool = False) -> set[str]:
    """The full name and the name without any parenthetical part, normalised."""
    out = {
        normalise(name, keep_numbers),
        normalise(re.sub(r"\(.*?\)", " ", name), keep_numbers),
    }
    return {v for v in out if v}


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    candidate_name: str
    score: float  # 0..100 from the scorer on normalised names
    exact: bool  # normalised names are identical (not merely score 100)


def best_candidates(
    name: str,
    pool: dict[str, str],  # candidate_id -> candidate name
    min_score: float,
    limit: int,
    scorer=fuzz.ratio,
    keep_numbers: bool = False,
) -> list[Candidate]:
    """Top candidates by the best score over the name's variants; exact matches rank first."""
    if not pool:
        return []
    norm_pool = {cid: normalise(n, keep_numbers) for cid, n in pool.items()}
    vs = variants(name, keep_numbers)
    best: dict[str, float] = {}
    for v in vs:
        for _, score, cid in process.extract(
            v, norm_pool, scorer=scorer, limit=limit * 3, score_cutoff=min_score
        ):
            best[cid] = max(best.get(cid, 0.0), score)
    for cid, n in norm_pool.items():  # exact names always qualify
        if n in vs:
            best[cid] = 100.0
    ranked = sorted(best.items(), key=lambda kv: (norm_pool[kv[0]] not in vs, -kv[1], pool[kv[0]]))[
        :limit
    ]
    return [Candidate(cid, pool[cid], round(sc, 1), norm_pool[cid] in vs) for cid, sc in ranked]
