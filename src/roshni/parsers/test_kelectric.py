from roshni.parsers.kelectric import (
    cycle_minutes,
    normalise_name,
    parse_feeder_list,
    parse_schedule,
)

LIST_TEXT = """                  List of Feeders under Load shed Category

S. No.               Feeder Name                                     IBC             ATC(OI)   Final Category
  1                       FAST RMU                              IBC - Bin Qasim       8.6%      Medium Loss
  2               RASHEEDIA MASJID RMU                               IBC - KIMZ       11.5%     Medium Loss
  3                 NEW SABZI MANDI                                 IBC - Gadap           -      Very High Loss
  4                   GARBLED LINE WITHOUT CATEGORY
"""

SCHED_TEXT = """   Load-shed Schedule for KE territory
   Feeder Name         Grids         1st Cycle     2nd Cycle     3rd Cycle     4th Cycle
BLOCK # 5 RMU                 AIRPORT       1035~1335     1435~1735     1835~2105     2235~0205
TANGA STAND                   AIRPORT       0935~1105     1335~1505     1705~1835     2005~2135
FOO                ELENDER RD       0705~1005     1105~1405     1505~1805     1905~2205IQBAL CENTER  ELENDER RD   0705~1005   1105~1405   1505~1805   1905~2205
SEVEN HOURS                   AIRPORT       0000~0100     0200~0300     0400~0500     0600~1000
"""


def test_normalise_name() -> None:
    assert normalise_name("Muhammad Farooq +") == "MUHAMMADFAROOQ"
    assert normalise_name("Andaleeb C.H.S") == normalise_name("ANDALEEB CHS")


def test_cycle_minutes_wraps_midnight() -> None:
    assert cycle_minutes("2235", "0205") == (210, True)
    assert cycle_minutes("1035", "1335") == (180, False)


def test_feeder_list(fake_pdf) -> None:
    res = parse_feeder_list(fake_pdf("kelectric-feeder-list.pdf", LIST_TEXT))
    assert [(r.serial, r.category, r.atc_loss_pct) for r in res.rows] == [
        (1, "Medium", 8.6),
        (2, "Medium", 11.5),
        (3, "Very High", None),
    ]
    assert res.rows[0].ibc == "IBC - Bin Qasim"
    assert len(res.quarantine) == 1


def test_schedule_glued_rows_and_validation(fake_pdf) -> None:
    feeders, cycles = parse_schedule(fake_pdf("kelectric-load-shed-schedule.pdf", SCHED_TEXT))
    got = {f.feeder_name: (f.grid, f.total_minutes, f.flags) for f in feeders.rows}
    assert got == {
        "BLOCK # 5 RMU": ("AIRPORT", 720, ""),
        "TANGA STAND": ("AIRPORT", 360, ""),
        "FOO": ("ELENDER RD", 720, "glued_line"),
        "IQBAL CENTER": ("ELENDER RD", 720, "glued_line"),
    }
    assert [q.reason for q in feeders.quarantine] == ["total 420 min is not 6 h or 12 h"]
    wraps = [c for c in cycles.rows if c.wraps_midnight]
    assert [(c.feeder_name_norm, c.cycle_no, c.minutes) for c in wraps] == [("BLOCK5RMU", 4, 210)]
