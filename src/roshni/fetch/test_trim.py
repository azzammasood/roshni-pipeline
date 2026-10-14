"""News feeds are trimmed to load-shedding headlines before storage (never article text)."""

import json
from pathlib import Path

import httpx
import pytest

from roshni.fetch.http import PoliteClient
from roshni.fetch.snapshot import run_snapshot
from roshni.fetch.store import SnapshotStore
from roshni.fetch.trim import TrimError, headlines, trim_news_feed
from roshni.sources.registry import Registry, SourceConfig

RSS = b"""<?xml version="1.0"?><rss version="2.0"><channel><title>Feed</title>
<item><title>Load-shedding cut to two hours, says minister</title>
  <link>https://example.pk/news/1</link><pubDate>Sun, 11 Oct 2026 18:07:00 +0500</pubDate>
  <description>Full article text that must never be stored.</description></item>
<item><title>Cricket: Pakistan win toss</title><link>https://example.pk/news/2</link></item>
<item><title>Internet outage hits Karachi</title><link>https://example.pk/news/3</link></item>
<item><title>Power outages in Quetta as shortfall widens</title>
  <link>https://example.pk/news/4</link><pubDate>not a date</pubDate></item>
<item><title>Loadshedding protest</title><link>javascript:alert(1)</link></item>
</channel></rss>"""

ATOM = b"""<feed xmlns="http://www.w3.org/2005/Atom"><title>F</title>
<entry><title>Electricity shortfall reaches 5,000 MW</title>
  <link href="https://example.pk/a"/><published>2026-10-12T04:00:00Z</published></entry>
</feed>"""


def test_rss_keeps_only_load_shedding_headlines() -> None:
    assert headlines(RSS) == [
        {
            "title": "Load-shedding cut to two hours, says minister",
            "link": "https://example.pk/news/1",
            "published": "2026-10-11T13:07:00Z",
        },
        {
            "title": "Power outages in Quetta as shortfall widens",
            "link": "https://example.pk/news/4",
            "published": "not a date",
        },
    ]


def test_atom_entries_are_read() -> None:
    (h,) = headlines(ATOM)
    assert h["link"] == "https://example.pk/a" and h["published"] == "2026-10-12T04:00:00Z"


def test_trimmed_json_never_contains_article_text() -> None:
    doc = json.loads(trim_news_feed(RSS, "news_x"))
    assert doc["format"] == "roshni-news-headlines/1" and doc["source"] == "news_x"
    assert b"Full article text" not in trim_news_feed(RSS, "news_x")


@pytest.mark.parametrize(
    "body,reason",
    [
        pytest.param(b"<html><body>Not a feed</body></html>", "no RSS channel", id="html"),
        pytest.param(b"{]", "not XML", id="not-xml"),
        pytest.param(None, "over", id="too-big"),
    ],
)
def test_unreadable_feed_raises(body: bytes | None, reason: str) -> None:
    with pytest.raises(TrimError, match=reason):
        headlines(body if body is not None else b"x" * 5_000_001)


FEED = "https://example.pk/feeds/home"
REG = Registry(
    user_agent="roshni-pipeline/0.1 (+test)",
    min_request_interval_seconds=0,
    sources={"news_x": SourceConfig(discovery="fixed_url", url=FEED, trim="news_headlines")},
)


def run(body: bytes, root: Path):
    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /\n")
        return httpx.Response(200, content=body)

    with PoliteClient(REG.user_agent, 0, transport=httpx.MockTransport(handler)) as c:
        return run_snapshot(c, SnapshotStore(root), REG)


def test_snapshot_stores_trimmed_json_and_dedupes(tmp_path: Path) -> None:
    assert run(RSS, tmp_path).count("new") == 1
    rec = SnapshotStore(tmp_path).last_good("news_x", "home")
    assert rec and rec.path.endswith(".json")
    assert len(json.loads((tmp_path / rec.path).read_text(encoding="utf-8"))["items"]) == 2
    # A feed whose other stories changed but whose load-shedding headlines did not: same content.
    busier = RSS.replace(b"Pakistan win toss", b"Pakistan lose toss")
    assert run(busier, tmp_path).count("unchanged") == 1


def test_unreadable_feed_is_logged_not_stored(tmp_path: Path) -> None:
    r = run(b"<html>maintenance</html>", tmp_path)
    assert r.count("error") == 1
    assert not (tmp_path / "files").exists()
    assert SnapshotStore(tmp_path).records[-1].note.startswith("not stored:")


@pytest.mark.parametrize(
    "title,keep",
    [
        ("No eight-hour gas loadshedding in Rawalpindi: SNGPL", False),
        ("SSGC announces load shedding for CNG stations", False),
        ("Governor urges PM to take notice of power, gas loadshedding", True),
        ("70% of K-Electric feeders loadshedding free", True),
        ("MEPCO issues load shedding schedule for city", True),
        ("Internet outage hits Karachi", False),
    ],
)
def test_headline_filter(title: str, keep: bool) -> None:
    from roshni.fetch.trim import is_load_shedding_headline

    assert is_load_shedding_headline(title) is keep


def test_known_broken_link_is_a_gap_not_an_error(tmp_path: Path) -> None:
    url = "https://example.pk/report-2023-24.pdf"
    reg = Registry(
        user_agent="roshni-pipeline/0.1 (+test)",
        min_request_interval_seconds=0,
        sources={"r": SourceConfig(discovery="fixed_url", url=url, known_broken=[url])},
    )

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /\n")
        return httpx.Response(404)

    with PoliteClient(reg.user_agent, 0, transport=httpx.MockTransport(handler)) as c:
        r = run_snapshot(c, SnapshotStore(tmp_path), reg)
    assert r.ok and r.count("gap") == 1 and r.count("error") == 0
