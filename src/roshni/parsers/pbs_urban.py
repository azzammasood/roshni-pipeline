"""PBS Census 2023 urban tables 33 (population) and 34 (housing).

Hierarchy, encoded only by row names in document order:
district > tehsil/taluka/sub-division > municipal body > charge > circle.
Each row gets a hierarchical key so tables 33 and 34 join on the key, never on row order.

Punjab and Islamabad come as XLSX; Sindh as PDF (poppler layout text). In the Sindh PDFs some
names wrap and some numbers are pushed onto their own line. A row is accepted only when its name
and a full set of numbers are on one line (a name with an unclosed "(" takes the next text-only
line as its continuation). Anything else is quarantined, never guessed. `-` means zero;
`#######` (a count of 1,000,000 or more that did not fit) becomes null and is flagged.
"""

import re
from collections.abc import Iterator
from pathlib import Path

import openpyxl
from pydantic import create_model

from roshni.parsers.common import ParseResult, Provenance, provenance
from roshni.parsers.pdftext import pdf_text

T33_COLS = [
    "pop_total", "pop_male", "pop_female", "pop_transgender",
    "literacy_pct_total", "literacy_pct_male", "literacy_pct_female", "literacy_pct_transgender",
    "edu_primary_below_matric_male", "edu_primary_below_matric_female",
    "edu_primary_below_matric_transgender",
    "edu_matric_below_degree_male", "edu_matric_below_degree_female",
    "edu_matric_below_degree_transgender",
    "edu_degree_above_male", "edu_degree_above_female", "edu_degree_above_transgender",
    "religion_muslim", "religion_non_muslim",
    "age_10_plus", "age_18_plus", "age_60_plus",
]  # fmt: skip
T34_COLS = [
    "housing_units_total", "structure_pacca", "structure_semi_pacca", "structure_kacha",
    "potable_water", "electricity", "gas", "kitchen", "bathroom", "latrine",
    "avg_household_size",
]  # fmt: skip
TABLES = {33: ("pbs_urban_population", T33_COLS), 34: ("pbs_urban_housing", T34_COLS)}
LEVELS = ("district", "tehsil", "body", "charge", "circle")


class UrbanBase(Provenance):
    table_no: int
    province: str  # punjab | islamabad | sindh
    location: str
    level: str  # one of LEVELS
    name: str
    district: str
    tehsil: str | None
    body: str | None
    charge: str | None
    circle: str | None
    area_key: str  # "district|tehsil|body|charge|circle", empty parts for higher levels
    flags: str


def _model(table_no: int):
    name, cols = TABLES[table_no]
    fields = {c: (float | None, None) for c in cols}
    return create_model(f"PbsUrbanT{table_no}", __base__=UrbanBase, **fields)


PbsUrbanPopulation = _model(33)
PbsUrbanHousing = _model(34)
MODELS = {33: PbsUrbanPopulation, 34: PbsUrbanHousing}

TOKEN_RE = re.compile(r"(?<!\S)(?:\d[\d,]*(?:\.\d+)?|-|#+)(?!\S)")
LINE_RE = re.compile(r"^(?P<name>[A-Za-z(].*?)\s{2,}(?P<nums>(?:\S+\s+)*\S+)\s*$")
FILE_RE = re.compile(r"table_(?P<t>3[34])_(?P<prov>[a-z]+)")


def classify(name: str) -> str:
    n = name.upper()
    if re.search(r"\bDISTRICT$", n):
        return "district"
    # "X CANTONMENT (Part of Y Taluka)" mentions a taluka but is a body.
    is_unit = n.startswith(("CHARGE", "CIRCLE")) or "(PART OF" in n
    if re.search(r"\b(TEHSIL|TALUKA|SUB-?DIVISION)\b", n) and not is_unit:
        return "tehsil"
    if n.startswith("CHARGE"):
        return "charge"
    if n.startswith("CIRCLE"):
        return "circle"
    return "body"


def to_value(tok: object) -> float | None:
    """Excel cell or PDF token -> number. '-' -> 0; '#######' -> None."""
    if tok is None:
        return None
    if isinstance(tok, int | float):
        return float(tok)
    s = str(tok).strip()
    if s in ("-", ""):
        return 0.0
    if set(s) == {"#"}:
        return None
    return float(s.replace(",", ""))


def _norm(s: object) -> str:
    return re.sub(r"\s+", " ", str(s)).strip()


def iter_xlsx(path: Path, ncols: int) -> Iterator[tuple[str, str, list]]:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.worksheets[0]
    for r, row in enumerate(ws.iter_rows(values_only=True), start=1):
        if r < 9 or row[0] is None or isinstance(row[0], int | float):
            continue
        yield f"row {r}", _norm(row[0]), list(row[1 : 1 + ncols])
    wb.close()


def iter_pdf(path: Path, ncols: int, res: ParseResult, prov: Provenance):
    """Yield (location, name, tokens) for clean lines; quarantine the rest of the data region."""
    for pno, page in enumerate(pdf_text(path).split("\f"), start=1):
        lines = page.splitlines()
        start = next(
            (i for i, ln in enumerate(lines) if (m := LINE_RE.match(ln)) and
             len(TOKEN_RE.findall(m["nums"])) == ncols and not m["name"][0].isdigit()),
            None,
        )  # fmt: skip
        if start is None:
            continue
        pending: tuple[str, str, list] | None = None
        for lno in range(start, len(lines)):
            line = lines[lno]
            loc = f"page {pno} line {lno + 1}"
            if not line.strip():
                continue
            m = LINE_RE.match(line)
            toks = TOKEN_RE.findall(m["nums"]) if m else []
            full = m is not None and len(toks) == ncols and m["nums"].split() == toks
            if full and m["name"].count(")") > m["name"].count("("):
                # Tail of a wrapped name ("Nazimabad Sub-Division)") sharing a numbers line.
                if pending:
                    yield pending
                    pending = None
                res.reject(prov, loc, line.strip(), "name fragment of a wrapped name")
                continue
            if full:
                if pending:
                    yield pending
                pending = (loc, _norm(m["name"]), toks)
                continue
            if (
                pending
                and not TOKEN_RE.search(line)
                and pending[1].count("(") > pending[1].count(")")
            ):
                pending = (pending[0], _norm(pending[1] + " " + line), pending[2])
                continue
            if pending:
                yield pending
                pending = None
            res.reject(prov, loc, line.strip(), "unparseable line (wrapped name or split numbers)")
        if pending:
            yield pending


def parse_urban(path: Path) -> ParseResult:
    m = FILE_RE.search(path.name)
    if not m:
        raise ValueError(f"not a PBS urban table file: {path.name}")
    table_no, province = int(m["t"]), m["prov"].replace("_districts", "")
    table, cols = TABLES[table_no]
    model = MODELS[table_no]
    prov = provenance(path)
    res: ParseResult = ParseResult(table)
    source = (
        iter_xlsx(path, len(cols))
        if path.suffix.lower() == ".xlsx"
        else iter_pdf(path, len(cols), res, prov)
    )

    state: dict[str, str | None] = dict.fromkeys(LEVELS)
    body_lost = False  # a body row was quarantined since the last tehsil/district
    seen: set[str] = set()
    last_qcount = 0
    for loc, name, raw in source:
        if len(res.quarantine) > last_qcount and state["tehsil"]:
            body_lost = True
        last_qcount = len(res.quarantine)
        level = classify(name)
        i = LEVELS.index(level)
        state[level] = name
        for lower in LEVELS[i + 1 :]:
            state[lower] = None
        if level in ("district", "tehsil", "body"):
            body_lost = False
        if state["district"] is None:
            res.reject(prov, loc, name, "row before any district")
            continue
        try:
            values = [to_value(v) for v in raw]
        except ValueError as e:
            res.reject(prov, loc, f"{name} | {raw}", f"bad number: {e}")
            continue
        flags = []
        if any(v is None for v in values):
            flags.append("overflow_cells")
        if level in ("charge", "circle") and state["body"] is None:
            flags.append("parent_body_unresolved" if body_lost else "no_body_level")
        key = "|".join(state[k] or "" for k in LEVELS)
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
                district=state["district"],
                tehsil=state["tehsil"],
                body=state["body"],
                charge=state["charge"],
                circle=state["circle"],
                area_key=key,
                flags=";".join(flags),
                **dict(zip(cols, values, strict=True)),
            )
        )
    return res
