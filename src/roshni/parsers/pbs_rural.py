"""PBS Census 2023 rural tables 31 (population) and 32 (housing), PDF via poppler layout text.

Hierarchy in document order: district > tehsil > QH (qanungo halqa) > PC (patwar circle, an
aggregate) > mauza (named locality with a free-form hadbast number, e.g. 0000227, 00S-226, 12/A.A.).
Each line is parsed by peeling exactly N numeric tokens from the right ('-' means zero); the
remainder splits on 2+ spaces into name and hadbast. Lines that do not fit are quarantined.
"""

import re
from pathlib import Path

from pydantic import create_model

from roshni.parsers.common import ParseResult, Provenance, provenance
from roshni.parsers.pbs_urban import to_value
from roshni.parsers.pdftext import pdf_text

T31_COLS = [
    "pop_total", "pop_male", "pop_female", "pop_transgender",
    "literacy_pct_total", "literacy_pct_male", "literacy_pct_female", "literacy_pct_transgender",
    "edu_primary_below_matric_male", "edu_primary_below_matric_female",
    "edu_primary_below_matric_transgender",
    "edu_matric_below_degree_male", "edu_matric_below_degree_female",
    "edu_matric_below_degree_transgender",
    "edu_degree_above_male", "edu_degree_above_female", "edu_degree_above_transgender",
    "religion_muslim", "religion_others",
    "age_10_plus", "age_18_plus", "age_60_plus",
    "area_acres",
]  # fmt: skip
T32_COLS = [
    "housing_units_total", "structure_pacca", "structure_semi_pacca", "structure_kacha",
    "potable_water", "electricity", "gas", "kitchen", "bathroom", "latrine",
    "avg_household_size",
]  # fmt: skip
TABLES = {31: ("pbs_rural_population", T31_COLS), 32: ("pbs_rural_housing", T32_COLS)}
LEVELS = ("district", "tehsil", "qh", "pc", "mauza")
NUM_RE = re.compile(r"^(?:\d[\d,]*(?:\.\d+)?|-|#+)$")
FILE_RE = re.compile(r"table_(?P<t>3[12])_(?P<prov>[a-z]+)")
# Only the unambiguous 7-character shapes (0000319, 00S-226) are split off a name.
TIGHT_HADBAST_RE = re.compile(r"^(?P<name>.*\S) (?P<hadbast>\d{7}|\d{2}[A-Z]-\d{3})$")
HEADER_WORDS = ("TABLE", "POPULATION", "HOUSING", "NAME OF", "DEH", "SETTLMENT", "NUMBER")


class RuralBase(Provenance):
    table_no: int
    province: str
    location: str
    level: str  # one of LEVELS
    name: str
    hadbast: str | None
    district: str
    tehsil: str | None
    qh: str | None
    pc: str | None
    area_key: str  # district|tehsil|qh|pc|name|hadbast
    flags: str


def _model(table_no: int):
    _, cols = TABLES[table_no]
    return create_model(
        f"PbsRuralT{table_no}", __base__=RuralBase, **{c: (float | None, None) for c in cols}
    )


MODELS = {31: _model(31), 32: _model(32)}


def classify(name: str, hadbast: str | None) -> str:
    n = name.upper()
    if hadbast:
        return "mauza"
    if n.endswith(" DISTRICT"):
        return "district"
    if n.endswith(" TEHSIL"):
        return "tehsil"
    if re.search(r"[\s)]QH$", n):
        return "qh"
    if re.search(r"[\s)]PC$", n):  # also "CHHATTAR(TRET)PC"
        return "pc"
    return "mauza"


def split_line(line: str, ncols: int) -> tuple[str, str | None, list[str]] | None:
    """Peel ncols numeric tokens from the right. Returns (name, hadbast, tokens) or None."""
    toks = line.split()
    if len(toks) <= ncols or not all(NUM_RE.match(t) for t in toks[-ncols:]):
        return None
    nums = toks[-ncols:]
    # Cut the line before the first peeled token, then split name and hadbast on 2+ spaces.
    cut = len(line.rstrip())
    for t in reversed(nums):
        cut = line.rstrip().rfind(t, 0, cut)
    left = line[:cut].strip()
    parts = re.split(r"\s{2,}", left)
    if not left or len(parts) > 2:
        return None
    name = re.sub(r"\s+", " ", parts[0]).strip()
    hadbast = parts[1].strip() if len(parts) == 2 else None
    if hadbast is None and (m := TIGHT_HADBAST_RE.match(name)):
        # Hadbast printed one space after the name ("PIR SHAH WASAN MEH BEHRAMPUR 0000319").
        name, hadbast = m["name"], m["hadbast"]
    return name, hadbast, nums


def parse_rural(path: Path) -> ParseResult:
    m = FILE_RE.search(path.name)
    if not m:
        raise ValueError(f"not a PBS rural table file: {path.name}")
    table_no, province = int(m["t"]), m["prov"]
    table, cols = TABLES[table_no]
    model = MODELS[table_no]
    prov = provenance(path)
    res: ParseResult = ParseResult(table)
    state: dict[str, str | None] = dict.fromkeys(LEVELS)
    seen: set[str] = set()

    for pno, page in enumerate(pdf_text(path).split("\f"), start=1):
        lines = page.splitlines()
        hdr = next((i for i, ln in enumerate(lines) if re.match(r"^\s+1\s+2\s+3\s", ln)), None)
        if hdr is None:
            continue
        for lno in range(hdr + 1, len(lines)):
            line = lines[lno]
            if not line.strip():
                continue
            loc = f"page {pno} line {lno + 1}"
            parsed = split_line(line, len(cols))
            if parsed is None:
                res.reject(prov, loc, line.strip(), "unparseable line")
                continue
            name, hadbast, nums = parsed
            level = classify(name, hadbast)
            i = LEVELS.index(level)
            if level != "mauza":
                state[level] = name
                for lower in LEVELS[i + 1 : -1]:
                    state[lower] = None
            if state["district"] is None:
                res.reject(prov, loc, line.strip(), "row before any district")
                continue
            values = [to_value(t) for t in nums]
            flags = []
            if level == "mauza" and not hadbast:
                flags.append("no_hadbast")
            if any(v is None for v in values):
                flags.append("overflow_cells")
            parts = [state["district"], state["tehsil"], state["qh"], state["pc"]]
            parts = parts[: i + 1] if level != "mauza" else parts
            key = "|".join(p or "" for p in parts)
            if level == "mauza":
                key += f"|{name}|{hadbast or ''}"
            if key in seen:
                flags.append("duplicate_key")
            seen.add(key)
            res.rows.append(
                model(
                    **prov.model_dump(),
                    table_no=table_no,
                    province=province,
                    location=loc,
                    level=level,
                    name=name,
                    hadbast=hadbast,
                    district=state["district"],
                    tehsil=state["tehsil"],
                    qh=state["qh"] if level in ("qh", "pc", "mauza") else None,
                    pc=state["pc"] if level in ("pc", "mauza") else None,
                    area_key=key,
                    flags=";".join(flags),
                    **dict(zip(cols, values, strict=True)),
                )
            )
    return res
