"""NEPRA order on K-Electric (2026-08-31): golden values from a trimmed excerpt of its tables."""

from datetime import date

from roshni.parsers.common import Provenance
from roshni.parsers.nepra_ke_order import parse_text
from roshni.paths import REPO_ROOT

TEXT = (
    REPO_ROOT / "tests" / "fixtures" / "nepra_ke_order" / "order-2026-08-31-tables.txt"
).read_text(encoding="utf-8")
PROV = Provenance(source_file="order.pdf", source_sha256="0" * 64, fetched_at=None)


def test_categories_as_printed() -> None:
    cats, _ = parse_text(TEXT, PROV)
    assert cats.quarantine == []
    got = {c.category: (c.feeders, c.consumers, c.avg_atc_loss_pct, c.scheduled_minutes_per_day)
           for c in cats.rows}  # fmt: skip
    assert got == {
        "Very High Loss": (316, 1_177_900, 69, 600),
        "High Loss": (171, 707_365, 42, 600),
        "Medium Loss": (133, 484_637, 31, 360),
    }
    assert sum(c.feeders for c in cats.rows) == 620  # the order's grand total
    assert sum(c.consumers for c in cats.rows) == 2_369_902
    assert {c.order_date for c in cats.rows} == {date(2026, 8, 31)}


def test_bands_add_up_and_match_the_orders_shares() -> None:
    _, bands = parse_text(TEXT, PROV)
    assert len(bands.rows) == 10
    above = {}
    for b in bands.rows:
        sched = 360 if b.category == "Medium Loss" else 600
        if b.lower_minutes >= sched:
            above[b.category] = round(above.get(b.category, 0) + b.pct_feeders, 1)
    # The order's own text: 68.4% (medium), 81.9% (high), 91.1% (very high) above the schedule.
    assert above == {"Medium Loss": 68.4, "High Loss": 81.9, "Very High Loss": 91.1}
    top = next(b for b in bands.rows if b.band == "14:00-18:00+")
    assert (top.lower_minutes, top.upper_minutes, top.feeders) == (840, None, 51)


def test_bands_that_do_not_add_up_are_quarantined() -> None:
    broken = TEXT.replace(
        "  Upto 10:00            28         102,779", "  Upto 10:00            27         102,779"
    )
    cats, _ = parse_text(broken, PROV)
    assert [q.location for q in cats.quarantine] == ["Very High Loss"]
    assert "do not add up" in cats.quarantine[0].reason
