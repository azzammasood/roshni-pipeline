"""Discovery tests on small synthetic pages that mimic the real listing structure."""

import pytest

from roshni.fetch.discover import (
    DiscoveryError,
    fixed_url,
    iesco_press_release_tab,
    iesco_xlsx_table,
    listing_pdf_pattern,
)
from roshni.sources.registry import SourceConfig

XLSX_CFG = SourceConfig(
    discovery="iesco_xlsx_table",
    listing_url="https://iesco.com.pk/load-shedding",
    circles={"Islamabad": "islamabad", "Rawalpindi City & Cantt": "rawalpindi"},
)


def xlsx_page(rows: list[tuple[str, str]]) -> str:
    body = "".join(
        f"<tr><td>{c}</td><td>Sep-2026</td><td><a href='{h}'>Click to View</a></td></tr>"
        for c, h in rows
    )
    return f"<table><tr><th>Circle</th><th>Date</th><th>Detail</th></tr>{body}</table>"


def test_iesco_xlsx_maps_labels_to_circles() -> None:
    html = xlsx_page(
        [("Islamabad", "/storage/a/X1.xlsx"), ("Rawalpindi City &amp; Cantt", "B.xlsx")]
    )
    ts = iesco_xlsx_table("iesco_schedule_xlsx", XLSX_CFG, html)
    assert [(t.item_key, t.url, t.label) for t in ts] == [
        ("islamabad", "https://iesco.com.pk/storage/a/X1.xlsx", "Sep-2026"),
        ("rawalpindi", "https://iesco.com.pk/B.xlsx", "Sep-2026"),
    ]


def test_iesco_xlsx_unknown_label_fails() -> None:
    html = xlsx_page(
        [("Islamabad", "a.xlsx"), ("Rawalpindi City & Cantt", "b.xlsx"), ("Mars", "c.xlsx")]
    )
    with pytest.raises(DiscoveryError, match="unknown IESCO circle"):
        iesco_xlsx_table("s", XLSX_CFG, html)


def test_iesco_xlsx_missing_circle_fails() -> None:
    with pytest.raises(DiscoveryError, match="missing"):
        iesco_xlsx_table("s", XLSX_CFG, xlsx_page([("Islamabad", "a.xlsx")]))


PR_CFG = SourceConfig(
    discovery="iesco_press_release_tab",
    listing_url="https://iesco.com.pk/press-release",
    tab_id="power-desktop",
    language="English",
    refetch=False,
)

PR_PAGE = """
<div class="tab-pane" id="power-desktop"><table>
<tr><th>Description</th><th>Details</th></tr>
<tr><td>Temporary Power Shutdown on 6th October 2026</td>
    <td><a href="https://iesco.com.pk/storage/p/October2026/AAA.pdf">English</a>
        <a href="https://iesco.com.pk/storage/p/October2026/BBB.pdf">Urdu</a></td></tr>
<tr><td>Power Shut Down on 5th October 2026</td>
    <td><a href="/storage/p/October2026/CCC.pdf"> English </a></td></tr>
</table></div>
<div class="tab-pane" id="ceo-desktop"><table>
<tr><td>CEO visit</td><td><a href="/x/DDD.pdf">English</a></td></tr></table></div>
"""


def test_press_release_english_only_within_tab() -> None:
    ts = iesco_press_release_tab("iesco_press_release", PR_CFG, PR_PAGE)
    assert [(t.item_key, t.url) for t in ts] == [
        ("AAA", "https://iesco.com.pk/storage/p/October2026/AAA.pdf"),
        ("CCC", "https://iesco.com.pk/storage/p/October2026/CCC.pdf"),
    ]
    assert ts[0].label == "Temporary Power Shutdown on 6th October 2026"
    assert all(not t.refetch for t in ts)


def test_press_release_missing_tab_fails() -> None:
    with pytest.raises(DiscoveryError):
        iesco_press_release_tab("s", PR_CFG, "<div id='other'></div>")


KE_PAGE = """
<a href="https://ke.com.pk/wp-content/uploads/2026/07/Feeders-List.pdf">Download</a>
<a href="https://ke.com.pk/wp-content/uploads/2026/07/Non-Payers-List.pdf">Download</a>
<a href="https://ke.com.pk/wp-content/uploads/2026/08/LSMnew-PDF-Aug-5th.pdf">Download</a>
"""

KE_SCHED = SourceConfig(
    discovery="listing_pdf_pattern",
    listing_url="https://ke.com.pk/load-shed-schedule/",
    link_pattern="(?i)(lsm|load[-_ ]?shed|schedule)",
    exclude_pattern="(?i)(feeders?[-_ ]?list|non[-_ ]?payers)",
)


def test_ke_schedule_picked_by_filename() -> None:
    (t,) = listing_pdf_pattern("kelectric_schedule", KE_SCHED, KE_PAGE)
    assert t.url.endswith("/2026/08/LSMnew-PDF-Aug-5th.pdf")
    assert t.item_key == "schedule"


def test_ke_schedule_ambiguous_fails() -> None:
    page = KE_PAGE + '<a href="/wp-content/uploads/2026/10/Load-Shed-Schedule-Oct.pdf">x</a>'
    with pytest.raises(DiscoveryError, match="expected 1"):
        listing_pdf_pattern("s", KE_SCHED, page)


KE_LIST = SourceConfig(
    discovery="fixed_url",
    url="https://ke.com.pk/wp-content/uploads/2026/07/Feeders-List.pdf",
    listing_url="https://ke.com.pk/load-shed-schedule/",
    listing_link_pattern="(?i)feeders?[-_ ]?list",
)


def test_fixed_url_no_warning_when_listed() -> None:
    (t,) = fixed_url("kelectric_feeder_list", KE_LIST, KE_PAGE)
    assert t.warnings == ()
    assert t.item_key == "Feeders-List"


def test_fixed_url_warns_on_new_listing_link() -> None:
    page = KE_PAGE.replace("2026/07/Feeders-List", "2026/10/Feeders-List-Oct")
    (t,) = fixed_url("kelectric_feeder_list", KE_LIST, page)
    assert t.warnings and "Feeders-List-Oct" in t.warnings[0]
