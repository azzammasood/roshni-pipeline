"""NEPRA PER section 3.6 parser: golden values from trimmed table excerpts (three layouts)."""

from roshni.parsers.common import Provenance
from roshni.parsers.nepra_per import parse_text
from roshni.paths import REPO_ROOT

FIXTURES = REPO_ROOT / "tests" / "fixtures" / "nepra_per"
PROV = Provenance(source_file="per.pdf", source_sha256="0" * 64, fetched_at=None)


def parsed(name: str):
    return parse_text((FIXTURES / name).read_text(encoding="utf-8"), PROV)


def grid(res) -> dict[tuple[str, str], float]:
    return {(r.fiscal_year, r.company): r.reported_hours_per_day for r in res.rows}


def test_fy2024_25_five_years_ten_companies() -> None:
    res = parsed("per-2024-25-s3.6.txt")
    assert res.quarantine == []
    assert len(res.rows) == 50
    assert {r.report_year for r in res.rows} == {"2024-25"}
    g = grid(res)
    assert sorted({fy for fy, _ in g}) == ["2020-21", "2021-22", "2022-23", "2023-24", "2024-25"]
    # The only source of FY2023-24 (its own report's link is a 404 on nepra.org.pk).
    assert g["2023-24", "PESCO"] == 11
    assert g["2023-24", "K-Electric"] == 8.52
    assert g["2024-25", "QESCO"] == 10.25
    assert g["2024-25", "LESCO"] == 0.1  # Table 10 in section 2.6 prints 0.06 (audit §10)
    # Restated by this report; the 2021-22 and 2022-23 reports print 3.4 (flagged in the mart).
    assert g["2021-22", "K-Electric"] == 2.6


def test_fy2017_18_rows_beside_prose() -> None:
    res = parsed("per-2017-18-s3.6.txt")
    assert res.quarantine == []
    g = grid(res)
    assert len(g) == 50
    assert g["2013-14", "MEPCO"] == 10
    assert g["2017-18", "GEPCO"] == 11  # as printed in four reports
    assert g["2017-18", "IESCO"] == 3.125


def test_fy2019_20_header_split_over_lines() -> None:
    res = parsed("per-2019-20-s3.6.txt")
    assert res.quarantine == []
    g = grid(res)
    assert sorted({fy for fy, _ in g}) == ["2015-16", "2016-17", "2017-18", "2018-19", "2019-20"]
    assert g["2015-16", "SEPCO"] == 1
    assert g["2019-20", "K-Electric"] == 2.73


def test_older_layout_is_quarantined_not_guessed() -> None:
    res = parse_text("2.6 Average Duration of Load Shedding  15-16\nIESCO 9.7 9.52\n", PROV)
    assert res.rows == []
    assert [q.reason for q in res.quarantine] == [
        "no section 3.6 load-shedding heading (older layout)"
    ]


def test_wrong_value_count_is_quarantined() -> None:
    text = "3.6 Load Shedding (Hours):\n DISCO 2020-21 2021-22 2022-23\n PESCO 1.8 6\n"
    res = parse_text(text, PROV)
    assert res.rows == []
    assert "2 values for 3 years" in res.quarantine[0].reason
