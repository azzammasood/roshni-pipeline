"""Places named in news headlines (export news.json `places`, since 1.13.0).

Deterministic and token-free: each headline is scanned for a gazetteer of names Roshni already
has, the eleven distribution companies with the cities and regions they serve (the site's city
pages) and K-Electric's IBC areas from dim_area. An exact word match has confidence 1.0; a
near-spelling ("Rawlpindi") is found with RapidFuzz and keeps its ratio as the confidence, shown
on the site. Only matches at or above MIN_RATIO are kept.

Precision rules, measured on a labelled set (test_news_places.py, real live headlines plus
hard cases): short all-caps names ("KE") match only in capitals; a name shared with another
place ("Hyderabad" in India) is skipped next to that place; IBC names that are also common
words ("Defence", "Garden", "SITE") need Karachi or KE in the same headline; IBCs split into
"- I" and "- II" are one place ("Layari").

A place in a headline says what the news is about. It is not a measurement and is never joined
to a feeder's schedule.
"""

import re
from dataclasses import dataclass

from rapidfuzz import fuzz

MIN_RATIO = 88.0
MIN_FUZZY_LEN = 6  # short names ("KP", "Dir") only match exactly

# Distribution company -> names that refer to its area (city page /city/<slug>/).
COMPANIES: dict[str, list[str]] = {
    "PESCO": ["PESCO", "Peshawar", "Mardan", "Abbottabad", "Swat"],
    "IESCO": ["IESCO", "Islamabad", "Rawalpindi", "Pindi", "Attock", "Jhelum", "Chakwal"],
    "GEPCO": ["GEPCO", "Gujranwala", "Sialkot", "Gujrat"],
    "FESCO": ["FESCO", "Faisalabad", "Sargodha", "Jhang"],
    "LESCO": ["LESCO", "Lahore", "Kasur", "Sheikhupura", "Okara"],
    "MEPCO": ["MEPCO", "Multan", "Bahawalpur", "Dera Ghazi Khan", "Rahim Yar Khan"],
    "QESCO": ["QESCO", "Quetta", "Balochistan"],
    "SEPCO": ["SEPCO", "Sukkur", "Larkana"],
    "HESCO": ["HESCO", "Hyderabad"],
    "TESCO": ["TESCO", "tribal districts", "FATA"],
    "K-Electric": ["K-Electric", "KElectric", "Karachi", "KE"],
}

# Name -> words that mean the headline is about another place with the same name.
ELSEWHERE = {"hyderabad": ("india", "indian", "telangana", "deccan")}
# IBC names that are also ordinary words: only with Karachi context.
GENERIC_IBCS = {"defence", "garden", "site", "saddar", "malir"}
KARACHI = re.compile(r"\b(karachi|ke|k-electric|kelectric)\b", re.I)


@dataclass(frozen=True)
class Name:
    text: str
    kind: str  # company | kelectric_ibc
    key: str  # company name, or the IBC's area_id
    label: str


def gazetteer(ibcs: list[tuple[str, str]] = ()) -> list[Name]:
    """Company names and aliases, plus K-Electric IBCs as (area_id, name like 'IBC - Korangi')."""
    out = [Name(a, "company", c, c) for c, names in COMPANIES.items() for a in names]
    merged: dict[str, list[tuple[str, str]]] = {}
    for area_id, name in ibcs:
        bare = re.sub(r"^\s*IBC\s*-?\s*", "", name).strip()
        base = re.sub(r"\s*-\s*I{1,3}$", "", bare).strip()  # "Layari - II" -> "Layari"
        if base:
            merged.setdefault(base, []).append((area_id, name))
    for base, parts in merged.items():
        key = parts[0][0] if len(parts) == 1 else f"ke_ibc:IBC - {base}"
        label = parts[0][1] if len(parts) == 1 else f"IBC - {base}"
        out.append(Name(base, "kelectric_ibc", key, label))
    return out


def _norm(s: str) -> str:
    return " ".join(re.sub(r"[^\w\s-]", " ", s.lower()).replace("-", " ").split())


def find(title: str, names: list[Name]) -> list[dict]:
    text = _norm(title)
    words = text.split()
    karachi = bool(KARACHI.search(title))
    best: dict[tuple[str, str], dict] = {}
    for n in names:
        target = _norm(n.text)
        k = len(target.split())
        if n.text.isupper() and len(n.text) <= 3:  # "KE": capitals only, never fuzzy
            if re.search(rf"(?<![\w-]){re.escape(n.text)}(?![\w-])", title.replace("’", "'")):
                ratio, method, seen = 100.0, "exact", target
            else:
                continue
        elif any(w in words for w in ELSEWHERE.get(target, ())) or (
            n.kind == "kelectric_ibc" and target in GENERIC_IBCS and not karachi
        ):
            continue
        elif re.search(rf"(?<!\w){re.escape(target)}(?!\w)", text):
            ratio, method, seen = 100.0, "exact", target
        elif len(target) >= MIN_FUZZY_LEN:
            windows = [" ".join(words[i : i + k]) for i in range(len(words) - k + 1)]
            scored = [(fuzz.ratio(target, w), w) for w in windows]
            ratio, seen = max(scored, default=(0.0, ""))
            method = "fuzzy"
            if ratio < MIN_RATIO:
                continue
        else:
            continue
        key = (n.kind, n.key)
        if key not in best or ratio > best[key]["confidence"] * 100:
            best[key] = {
                "kind": n.kind,
                "key": n.key,
                "label": n.label,
                "matched": seen,
                "method": method,
                "confidence": round(ratio / 100, 2),
            }
    # A near-spelling of one name on words that are exactly another name ("Orangi" is not
    # "Korangi") is dropped.
    exact = {p["matched"] for p in best.values() if p["method"] == "exact"}
    kept = [p for p in best.values() if p["method"] == "exact" or p["matched"] not in exact]
    return sorted(kept, key=lambda p: (-p["confidence"], p["label"]))
