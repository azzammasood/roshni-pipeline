"""Golden tests: parsed source files against the audit oracles in docs/data-audit.md.

These are regression tests. If a number changes because a source was republished, surface it;
never silently edit the expected value. Where the parser and the original audit differ for an
explained reason, the assertion states what the parser finds and points to data-audit.md §8.
"""

from collections import Counter

import pytest

from roshni.paths import DATA_SOURCES_DIR as D

pytestmark = pytest.mark.needs_data_sources

CIRCLES = ("islamabad", "rawalpindi", "attock", "jhelum", "chakwal", "ajk")
IESCO_DISTRICTS = {
    "ATTOCK DISTRICT", "CHAKWAL DISTRICT", "ISLAMABAD DISTRICT", "JHELUM DISTRICT",
    "RAWALPINDI DISTRICT",
}  # fmt: skip


@pytest.fixture(scope="module")
def iesco():
    from roshni.parsers.iesco_xlsx import parse_iesco_xlsx

    feeders, slots = [], []
    for c in CIRCLES:
        f, s = parse_iesco_xlsx(D / f"iesco-{c}-sep26.xlsx", c)
        assert f.quarantine == []
        feeders += f.rows
        slots += s.rows
    return feeders, slots


def test_iesco_row_counts(iesco) -> None:
    feeders, _ = iesco
    assert Counter(f.circle for f in feeders) == {
        "islamabad": 272, "rawalpindi": 352, "attock": 164, "jhelum": 90, "chakwal": 102, "ajk": 125,
    }  # fmt: skip
    assert len(feeders) == 1105
    assert len({(f.circle, f.feeder_code_raw) for f in feeders}) == 1103
    assert sum(f.circle != "ajk" for f in feeders) == 980


def test_iesco_known_anomalies(iesco) -> None:
    feeders, _ = iesco
    assert sum(f.feeder_code_raw == "NOT ALLOTED" for f in feeders) == 3
    # "one code in two circles" in the audit is the NOT ALLOTED placeholder (Islamabad + Rawalpindi).
    assert {f.circle for f in feeders if f.feeder_code_raw == "NOT ALLOTED"} == {
        "islamabad", "rawalpindi"
    }  # fmt: skip
    dup = [f for f in feeders if f.feeder_code == "059704"]
    assert [f.circle for f in dup] == ["chakwal", "chakwal"]
    assert any("FESCO" in f.feeder_name for f in dup)
    kohala = next(f for f in feeders if f.feeder_name == "KOHALA")
    assert kohala.flags == "slot_count_mismatch:L10=11"
    assert sum(bool(f.flags) for f in feeders) == 4
    (b,) = [f for f in feeders if f.feeder_code == "089201"]
    assert (b.feeder_name, b.grid_name, b.circle) == ("BHARAKHAU 1", "UNIVERSTY", "islamabad")


def test_iesco_cohort_patterns(iesco) -> None:
    _, slots = iesco
    pats: dict[int, set] = {}
    by_feeder: dict[tuple, list] = {}
    for s in slots:
        by_feeder.setdefault((s.circle, s.sheet_row, s.level_hours), []).append(s.slot_start_hour)
    for (_, _, lvl), hours in by_feeder.items():
        pats.setdefault(lvl, set()).add(tuple(sorted(hours)))
    assert len(pats[2]) == 12 and len(pats[12]) == 2


@pytest.fixture(scope="module")
def press():
    from roshni.parsers.iesco_press import parse_press_release

    return {
        n: parse_press_release(D / f"iesco-press-release-eng-{n}.pdf") for n in ("oct3", "oct5")
    }


def _groups(rows):
    return Counter((str(r.outage_date), r.circle, r.start_local, r.end_local) for r in rows)


def test_press_release_02(press) -> None:
    r = press["oct3"]
    assert r.quarantine == [] and {x.release_no for x in r.rows} == {"02"}
    assert Counter(str(x.outage_date) for x in r.rows) == {"2026-10-03": 29, "2026-10-04": 45}
    assert _groups(r.rows) == {
        ("2026-10-03", "Islamabad", "08:00", "14:00"): 8,
        ("2026-10-03", "Islamabad", "07:00", "14:00"): 1,
        ("2026-10-03", "GSO", "06:00", "09:00"): 20,
        ("2026-10-04", "Islamabad", "08:00", "14:00"): 8,
        ("2026-10-04", "Islamabad", "07:00", "14:00"): 13,
        ("2026-10-04", "Attock", "07:00", "14:00"): 4,
        ("2026-10-04", "GSO", "06:00", "09:00"): 20,
    }
    attock = [x.feeder_name for x in r.rows if x.circle == "Attock"]
    assert attock == ["Lala Zar", "POF", "Munirabad", "Karnel Sher Khan"]


def test_press_release_03(press) -> None:
    r = press["oct5"]
    assert r.quarantine == [] and {x.release_no for x in r.rows} == {"03"}
    assert _groups(r.rows) == {
        ("2026-10-05", "Rawalpindi City", "07:00", "14:00"): 2,
        ("2026-10-05", "Rawalpindi City", "08:00", "12:00"): 5,
        ("2026-10-05", "Islamabad", "08:00", "12:00"): 8,
    }
    assert [x.feeder_name for x in r.rows][:7] == [
        "Qadeer Road", "KRL", "Millatabad", "Dhoke Chaudhrian", "Peshawar Road", "Askari-XI",
        "Coblane",
    ]  # fmt: skip


@pytest.fixture(scope="module")
def ke():
    from roshni.parsers.kelectric import parse_feeder_list, parse_schedule

    lst = parse_feeder_list(D / "kelectric-feeder-list.pdf")
    sched, cycles = parse_schedule(D / "kelectric-load-shed-schedule.pdf")
    assert lst.quarantine == [] and sched.quarantine == []
    return lst.rows, sched.rows, cycles.rows


def test_ke_feeder_list(ke) -> None:
    lst, _, _ = ke
    assert len(lst) == 623
    assert Counter(r.category for r in lst) == {"Medium": 133, "High": 163, "Very High": 327}
    assert sorted(r.feeder_name for r in lst if r.atc_loss_pct is None) == [
        "KAGHZI BAZAAR (Ex-SARAFA BAZAAR)", "NEW SABZI MANDI",
    ]  # fmt: skip
    assert len({r.ibc for r in lst}) == 30


def test_ke_schedule(ke) -> None:
    _, sched, cycles = ke
    assert len(sched) == 618
    assert Counter(r.total_minutes for r in sched) == {360: 125, 720: 493}
    assert len(cycles) == 4 * 618
    assert Counter(c.feeder_name_norm for c in cycles).most_common(1)[0][1] == 4
    # 54 grids in the schedule; DEFENCE holds only ARMY HOUSE, which is not listed -> 53 among listed.
    assert len({r.grid for r in sched}) == 54
    assert [r.feeder_name for r in sched if r.grid == "DEFENCE"] == ["ARMY HOUSE"]


def test_ke_join(ke) -> None:
    lst, sched, _ = ke
    ls = {r.feeder_name_norm: r for r in lst}
    ss = {r.feeder_name_norm: r for r in sched}
    assert len(ls.keys() & ss.keys()) == 616  # + 1 truncated NAVY name, resolved downstream = 617
    assert sorted(ls[k].feeder_name for k in ls.keys() - ss.keys()) == [
        "ANDALEEB C.H.S",
        "BEHAVIORAL SCIENCES (Ex. INSTITUTE OF BEHAVIOR SCIENCE (IBS))",
        "CBR INCOME TAX BUILDING",
        "MISKEENABAD",
        "MUHAMMAD FAROOQ +",
        "NAVY HOUSING SCHEME (Ex. PAKISTAN NAVY HOUSING SCHEME)",
        "PNSC S/S",
    ]
    assert sorted(ss[k].feeder_name for k in ss.keys() - ls.keys()) == [
        "ARMY HOUSE", "NAVY HOUSING SCHEME (Ex. PAKISTAN NAVY HOUSING SCHEM",
    ]  # fmt: skip
    joined = ls.keys() & ss.keys()
    rel = Counter((ls[k].category, ss[k].total_minutes) for k in joined)
    assert rel == {("Very High", 720): 327, ("High", 720): 163, ("Medium", 360): 124,
                   ("Medium", 720): 2}  # fmt: skip
    assert sorted(ls[k].feeder_name for k in joined
                  if ls[k].category == "Medium" and ss[k].total_minutes == 720) == [
        "ABDUL GHANI +", "KHYABAN-E-HAFIZ",
    ]  # fmt: skip


@pytest.mark.parametrize(
    "ibc,n,share",
    [("IBC - Orangi - I", 41, 0.976), ("IBC - Korangi", 39, 0.615),
     ("IBC - Clifton", 11, 1.0), ("IBC - F.B. Area", 4, 0.0)],
)  # fmt: skip
def test_ke_ibc_oracles(ke, ibc, n, share) -> None:
    lst, sched, _ = ke
    ss = {r.feeder_name_norm: r for r in sched}
    rows = [r for r in lst if r.ibc == ibc]
    assert len(rows) == n
    hours = [ss[r.feeder_name_norm].total_minutes for r in rows if r.feeder_name_norm in ss]
    assert round(sum(h == 720 for h in hours) / len(hours), 3) == share


def test_ke_uthal_is_hub_chowki(ke) -> None:
    lst, sched, _ = ke
    uthal = {r.feeder_name_norm for r in lst if r.ibc == "IBC - Uthal"}
    hub = {r.feeder_name_norm for r in sched if r.grid == "HUB CHOWKI"}
    assert len(uthal) == 9 and uthal == hub


@pytest.fixture(scope="module")
def urban():
    from roshni.parsers.pbs_urban import parse_urban

    return {
        (t, p): parse_urban(D / f"table_{t}_{p}.{'pdf' if p == 'sindh_districts' else 'xlsx'}")
        for t in (33, 34)
        for p in ("islamabad", "punjab_districts", "sindh_districts")
    }


@pytest.mark.parametrize("prov,n", [("islamabad", 90), ("punjab_districts", 5534)])
def test_urban_join_complete(urban, prov, n) -> None:
    a, b = urban[(33, prov)], urban[(34, prov)]
    assert len(a.rows) == len(b.rows) == n and a.quarantine == b.quarantine == []
    assert {r.area_key for r in a.rows} == {r.area_key for r in b.rows}


def test_urban_islamabad_and_iesco_bodies(urban) -> None:
    isb = urban[(33, "islamabad")].rows
    assert Counter(r.level for r in isb)["charge"] == 12
    assert Counter(r.level for r in isb)["circle"] == 75
    pun = urban[(33, "punjab_districts")].rows
    iesco = {"ATTOCK DISTRICT", "RAWALPINDI DISTRICT", "JHELUM DISTRICT", "CHAKWAL DISTRICT"}
    assert sum(r.level == "body" and r.district in iesco for r in pun) == 39


def test_sindh_karachi_subdivisions(urban) -> None:
    rows = urban[(33, "sindh_districts")].rows
    karachi = {"KARACHI CENTRAL DISTRICT", "KARACHI EAST DISTRICT", "KARACHI SOUTH DISTRICT",
               "KARACHI WEST DISTRICT", "KEAMARI DISTRICT", "KORANGI DISTRICT", "MALIR DISTRICT"}  # fmt: skip
    subs = {r.name: r for r in rows if r.level == "tehsil" and r.district in karachi
            and r.name.endswith("SUB-DIVISION")}  # fmt: skip
    assert len(subs) == 28
    for name, pop, lit in [("ORANGI SUB-DIVISION", 596919, 60.8),
                           ("GULSHAN-E-IQBAL SUB-DIVISION", 973314, 89.2),
                           ("MAURIPUR SUB-DIVISION", 217930, 52.8)]:  # fmt: skip
        assert subs[name].pop_total == pop
        assert round(subs[name].literacy_pct_total, 1) == lit
    assert sum("overflow_cells" in r.flags for r in rows) == 7  # "#######" district totals


def test_sindh_join_at_district_and_subdivision(urban) -> None:
    a, b = urban[(33, "sindh_districts")].rows, urban[(34, "sindh_districts")].rows
    for level, n in (("district", 30), ("tehsil", 130)):
        ka = {r.area_key for r in a if r.level == level}
        kb = {r.area_key for r in b if r.level == level}
        assert ka == kb and len(ka) == n


@pytest.fixture(scope="module")
def rural():
    from roshni.parsers.pbs_rural import parse_rural

    out = {}
    for t in (31, 32):
        rows = []
        for p in ("islamabad", "punjab_districts"):
            rows += parse_rural(D / f"table_{t}_{p}.pdf").rows
        out[t] = [r for r in rows if r.level == "mauza" and r.district in IESCO_DISTRICTS]
    return out


def test_rural_localities(rural) -> None:
    # Audit: Attock 435, Chakwal 419, Islamabad 129, Jhelum 525, Rawalpindi 1,070 (= 2,578).
    # Parser finds 3 more genuine mauzas printed without a hadbast number (data-audit.md §8).
    assert Counter(r.district for r in rural[31]) == {
        "ATTOCK DISTRICT": 435, "CHAKWAL DISTRICT": 420, "ISLAMABAD DISTRICT": 129,
        "JHELUM DISTRICT": 525, "RAWALPINDI DISTRICT": 1072,
    }  # fmt: skip
    k31, k32 = {r.area_key for r in rural[31]}, {r.area_key for r in rural[32]}
    assert k31 == k32 and len(k31) == len(rural[31]) == 2581


def test_rural_indicators(rural) -> None:
    hou = {r.area_key: r for r in rural[32]}
    big = [(p, hou[p.area_key]) for p in rural[31] if hou[p.area_key].housing_units_total >= 20]
    assert len(big) == 2360  # audit 2,357; +3 from the extra localities above
    assert round(sum(p.pop_total for p, _ in big) / 1e6, 1) == 6.8
    lit = [p.literacy_pct_total for p, _ in big]
    assert (round(min(lit), 0), round(max(lit), 1)) == (17, 99.9)
    deg = [(p.edu_degree_above_male + p.edu_degree_above_female + p.edu_degree_above_transgender)
           / p.pop_total for p, _ in big]  # fmt: skip
    assert round(100 * max(deg), 1) == 39.8
    # With '-' stored as 0 (census convention), 27 localities are under 70% electricity; the audit
    # treated '-' as missing and reported 24 (3 localities print '-' for electricity).
    elec = [h.electricity / h.housing_units_total for _, h in big]
    assert sum(e < 0.70 for e in elec) == 27 and sum(e == 0 for e in elec) == 3
