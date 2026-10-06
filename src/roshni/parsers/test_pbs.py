import pytest

from roshni.parsers import pbs_rural, pbs_urban
from roshni.parsers.pbs_urban import classify, to_value


@pytest.mark.parametrize(
    "name,level",
    [
        ("KARACHI WEST DISTRICT", "district"),
        ("ORANGI SUB-DIVISION", "tehsil"),
        ("BADIN TALUKA", "tehsil"),
        ("HYDERABAD CANTONMENT (Part of Hyderabad City Taluka)", "body"),
        ("ATTOCK MC", "body"),
        ("CHARGE NO 01 (PART)", "charge"),
        ("CIRCLE NO 06", "circle"),
    ],
)
def test_urban_classify(name: str, level: str) -> None:
    assert classify(name) == level


def test_to_value() -> None:
    assert to_value("1,234") == 1234.0
    assert to_value("-") == 0.0
    assert to_value("#######") is None
    assert to_value(5.5) == 5.5


def nums(n: int, first: str = "100") -> str:
    return "   ".join([first] + ["1"] * (n - 1))


def test_urban_sindh_pdf_rules(fake_pdf) -> None:
    n = len(pbs_urban.T34_COLS)
    text = "\n".join(
        [
            "TABLE 34- SELECTED HOUSING STATISTICS",
            f"KARACHI WEST DISTRICT              {nums(n, '900')}",
            f"ORANGI SUB-DIVISION                {nums(n, '500')}",
            "DISTRICT MUNICIPAL CORPORATION",  # wrapped body name: quarantined
            f"Orangi Sub-Division)               {nums(n, '500')}",  # tail fragment: quarantined
            f"CHARGE NO 01                       {nums(n, '200')}",
            f"CIRCLE NO 01                       {nums(n, '50')}",
            f"HYDERABAD CANTONMENT (Part of      {nums(n, '40')}",
            "Hyderabad City Taluka)",  # continuation of an unclosed parenthesis
            f"CHARGE NO 02                       {nums(n - 1, '30')}",  # split numbers
        ]
    )
    res = pbs_urban.parse_urban(fake_pdf("table_34_sindh_districts.pdf", text))
    got = [(r.level, r.name, r.flags) for r in res.rows]
    assert got == [
        ("district", "KARACHI WEST DISTRICT", ""),
        ("tehsil", "ORANGI SUB-DIVISION", ""),
        ("charge", "CHARGE NO 01", "parent_body_unresolved"),
        ("circle", "CIRCLE NO 01", "parent_body_unresolved"),
        ("body", "HYDERABAD CANTONMENT (Part of Hyderabad City Taluka)", ""),
    ]
    assert res.rows[2].area_key == "KARACHI WEST DISTRICT|ORANGI SUB-DIVISION||CHARGE NO 01|"
    assert res.rows[0].housing_units_total == 900
    assert len(res.quarantine) == 3


@pytest.mark.parametrize(
    "line,expected",
    [
        ("ATHAL                        0000227     9,422   4,931", ("ATHAL", "0000227")),
        ("CHATTAR PC                                16,426   8,716", ("CHATTAR PC", None)),
        ("PIR SHAH WASAN MEH 0000319               1,000   2", ("PIR SHAH WASAN MEH", "0000319")),
        ("046/FATEH PC                              10,001   5,188", ("046/FATEH PC", None)),
        ("CHAK 12          12/A.A.                  7   -", ("CHAK 12", "12/A.A.")),
    ],
)
def test_rural_split_line(line: str, expected) -> None:
    name, hadbast, toks = pbs_rural.split_line(line, 2)
    assert (name, hadbast) == expected and len(toks) == 2


def test_rural_split_rejects_short_lines() -> None:
    assert pbs_rural.split_line("CHAK MANAK KAMBOH JAMUNWACCHAL", 2) is None
    assert pbs_rural.split_line("0000322", 2) is None


@pytest.mark.parametrize(
    "name,hadbast,level",
    [
        ("ATTOCK DISTRICT", None, "district"),
        ("ATTOCK TEHSIL", None, "tehsil"),
        ("MOHRA NOOR QH", None, "qh"),
        ("CHHATTAR(TRET)PC", None, "pc"),
        ("ATHAL", "0000227", "mauza"),
        ("RAKH KOT NATIL", None, "mauza"),
    ],
)
def test_rural_classify(name, hadbast, level) -> None:
    assert pbs_rural.classify(name, hadbast) == level


def test_rural_hierarchy(fake_pdf) -> None:
    n = len(pbs_rural.T32_COLS)
    page = "\n".join(
        [
            "TABLE 32- SELECTED HOUSING STATISTICS",
            "                  1               2       3              4",
            f"ISLAMABAD DISTRICT                        {nums(n, '226,022')}",
            f"ISLAMABAD TEHSIL                          {nums(n, '226,022')}",
            f"MOHRA NOOR QH                             {nums(n, '62,520')}",
            f"CHATTAR PC                                {nums(n, '2,706')}",
            f"ATHAL                        0000227      {nums(n, '1,476')}",
            f"DOHALA                       0000067      {nums(n, '-')}",
        ]
    )
    res = pbs_rural.parse_rural(fake_pdf("table_32_islamabad.pdf", page))
    athal = next(r for r in res.rows if r.name == "ATHAL")
    assert (
        athal.area_key
        == "ISLAMABAD DISTRICT|ISLAMABAD TEHSIL|MOHRA NOOR QH|CHATTAR PC|ATHAL|0000227"
    )
    assert (athal.qh, athal.pc, athal.housing_units_total) == ("MOHRA NOOR QH", "CHATTAR PC", 1476)
    assert next(r for r in res.rows if r.name == "DOHALA").housing_units_total == 0
    assert [r.level for r in res.rows] == ["district", "tehsil", "qh", "pc", "mauza", "mauza"]
