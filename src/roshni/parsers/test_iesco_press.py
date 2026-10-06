from collections import Counter
from datetime import UTC, datetime

from roshni.parsers.iesco_press import parse_press_release

DEV = """Temporary Power Shutdown Schedule on Limited Feeders
Intro text, with commas, that is not part of the schedule.
In this regard, on Saturday, October 03, 2026, from 08:00 AM to 02:00 PM, there
will be a temporary interruption in electricity supply in Islamabad Circle: Club-1,
Mehfooz Shaheed / Shahzad Town, CDA Pump Feeders, from 07:00 AM to 02:00 PM, Sudhran Feeder, GSO
Circle: from 06:00 AM to 09:00 AM, Line Park, Behkri Feeders. On Sunday, October 04, 2026, from
08:00 AM to 02:00 PM, Attock Circle: Lala Zar, Karnel Sher Khan Feeders. GSO Circle:
from 06:00 AM to 09:00 AM, Line Park Feeders. IESCO management apologizes to its consumers.
                                          Press Release No: 02: 10/2026
"""

MAINT = """   POWER SUSPENSION SCHEDULES FOR 14th September 2026.
According to the spokesman, work is in process, so feeders will be suspended.
On 14th September 2026, Islamabad Circle, from 7 am to 11 am, Highway, Zia
Masjid, Feeders, Rawalpindi Cantt. Circle, from 6 am to 10 am, Range Road, Feeders, GSO Circle,
from 09:00 am to 04:00 pm, 132kv AWC HMC Taxila, and surrounding areas will remain closed.
IESCO management apologizes to its esteemed customers.
                               Press Release No: 13: 09/2026
"""

TRAILING = """In this regard, on Friday, September 25, 2026, from 8:00 AM to 12:00 PM, there will be a
temporary interruption in electricity supply in Punjab House, Bari Imam, feeders and adjoining
areas in Islamabad Circle. IESCO management apologizes to its valued consumers."""


def groups(res):
    return Counter((str(r.outage_date), r.circle, r.start_local, r.end_local) for r in res.rows)


def test_development_format(fake_pdf) -> None:
    res = parse_press_release(fake_pdf("dev.pdf", DEV))
    assert res.quarantine == []
    assert groups(res) == {
        ("2026-10-03", "Islamabad", "08:00", "14:00"): 3,
        ("2026-10-03", "Islamabad", "07:00", "14:00"): 1,
        ("2026-10-03", "GSO", "06:00", "09:00"): 2,
        ("2026-10-04", "Attock", "08:00", "14:00"): 2,
        ("2026-10-04", "GSO", "06:00", "09:00"): 1,
    }
    names = [r.feeder_name for r in res.rows]
    assert "Mehfooz Shaheed / Shahzad Town" in names and "Karnel Sher Khan" in names
    first = res.rows[0]
    assert first.release_no == "02" and first.release_period == "10/2026"
    assert first.start_utc == datetime(2026, 10, 3, 3, 0, tzinfo=UTC)  # 08:00 PKT
    assert [r.seq for r in res.rows] == list(range(1, len(res.rows) + 1))


def test_maintenance_format(fake_pdf) -> None:
    res = parse_press_release(fake_pdf("maint.pdf", MAINT))
    assert groups(res) == {
        ("2026-09-14", "Islamabad", "07:00", "11:00"): 2,
        ("2026-09-14", "Rawalpindi Cantt", "06:00", "10:00"): 1,
        ("2026-09-14", "GSO", "09:00", "16:00"): 1,
    }
    asset = next(r for r in res.rows if r.circle == "GSO")
    assert asset.feeder_name == "132kv AWC HMC Taxila" and asset.flags == "transmission_asset"
    assert [q.reason for q in res.quarantine] == ["phrase is not a feeder name"]


def test_circle_after_list(fake_pdf) -> None:
    res = parse_press_release(fake_pdf("trail.pdf", TRAILING))
    assert [(r.feeder_name, r.circle, r.flags) for r in res.rows] == [
        ("Punjab House", "Islamabad", "circle_after_list"),
        ("Bari Imam", "Islamabad", "circle_after_list"),
    ]


def test_no_date_is_quarantined(fake_pdf) -> None:
    res = parse_press_release(fake_pdf("none.pdf", "A notice with no schedule at all."))
    assert res.rows == [] and res.quarantine[0].reason == "no outage date found"
