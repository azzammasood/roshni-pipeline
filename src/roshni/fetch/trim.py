"""Trim fetched news feeds before they are stored (owner, 2026-10-13): keep only load-shedding
stories, and of those only headline, link and publication time. Article text, summaries and
images are never stored. The trimmed JSON is what gets hashed, so an unchanged set of matching
headlines is "same content" from one day to the next.

XML is parsed with the standard library (expat >= 2.4.1 guards against entity-expansion bombs and
never resolves external entities) after a size cap.
"""

import json
import re
import xml.etree.ElementTree as ET
from datetime import UTC
from email.utils import parsedate_to_datetime

MAX_FEED_BYTES = 5_000_000
FORMAT = "roshni-news-headlines/1"

# Matched against the headline only (what the site shows), case-insensitive. Electricity-specific
# phrases only: a bare "outage" or "blackout" also matches internet, gas and media stories.
KEYWORDS = re.compile(
    r"load[\s-]*shed|loadshed|(?:power|electricity)\s+(?:cuts?|outages?|shortfall|breakdown)",
    re.I,
)
# "Gas load shedding" (SNGPL, SSGC) is a different utility: excluded unless the headline also
# names electricity ("power, gas loadshedding" stays). Whole words via lookarounds.
GAS = re.compile(r"(?<![a-z])(?:gas|sngpl|ssgc)(?![a-z])", re.I)
ELECTRIC = re.compile(
    r"power|electric|feeder|wapda|(?<![a-z])(?:[a-z]{1,4}esco|discos?)(?![a-z])", re.I
)
ATOM = "{http://www.w3.org/2005/Atom}"


def is_load_shedding_headline(title: str) -> bool:
    """Electricity load shedding by the headline's own words (shared by trimming and parsing, so
    a rule change also applies to headlines stored earlier)."""
    return bool(KEYWORDS.search(title)) and not (GAS.search(title) and not ELECTRIC.search(title))


class TrimError(ValueError):
    """The feed could not be read; nothing is stored for this fetch."""


def _text(el: ET.Element | None) -> str:
    return re.sub(r"\s+", " ", "".join(el.itertext())).strip() if el is not None else ""


def _published(raw: str) -> str:
    """RFC 822 (RSS) or ISO 8601 (Atom) -> ISO UTC; the raw string if neither parses."""
    if not raw:
        return ""
    try:
        return parsedate_to_datetime(raw).astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    except (TypeError, ValueError):
        return raw


def headlines(content: bytes) -> list[dict[str, str]]:
    if len(content) > MAX_FEED_BYTES:
        raise TrimError(f"feed is {len(content)} bytes, over {MAX_FEED_BYTES}")
    try:
        root = ET.fromstring(content)
    except ET.ParseError as e:
        raise TrimError(f"not XML: {e}") from e
    items = []
    for it in root.iter("item"):  # RSS 2.0
        items.append((_text(it.find("title")), _text(it.find("link")), _text(it.find("pubDate"))))
    for it in root.iter(f"{ATOM}entry"):  # Atom
        link = it.find(f"{ATOM}link")
        href = link.get("href", "") if link is not None else ""
        when = _text(it.find(f"{ATOM}published")) or _text(it.find(f"{ATOM}updated"))
        items.append((_text(it.find(f"{ATOM}title")), href, when))
    if not items and root.find("channel") is None and root.tag != f"{ATOM}feed":
        raise TrimError(f"no RSS channel or Atom feed (root <{root.tag}>)")
    keep = {
        link: {"title": title, "link": link, "published": _published(when)}
        for title, link, when in items
        if title and link.startswith(("https://", "http://")) and is_load_shedding_headline(title)
    }
    return [keep[k] for k in sorted(keep)]


def trim_news_feed(content: bytes, source: str) -> bytes:
    doc = {"format": FORMAT, "source": source, "items": headlines(content)}
    return (json.dumps(doc, ensure_ascii=False, indent=1, sort_keys=True) + "\n").encode("utf-8")


TRIMMERS = {"news_headlines": trim_news_feed}
