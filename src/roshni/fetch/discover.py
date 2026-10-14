"""Discover file URLs from listing pages. Each function returns Targets or raises DiscoveryError."""

import re
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from urllib.parse import unquote, urljoin, urlsplit

from bs4 import BeautifulSoup

from roshni.sources.registry import SourceConfig


class DiscoveryError(Exception):
    """The listing page did not look as expected. Never guess: fail and report."""


@dataclass(frozen=True)
class Target:
    source: str
    item_key: str  # stable id within the source (circle, release file stem, ...)
    url: str
    label: str = ""  # human context: listing-page date label, release title
    refetch: bool = True  # False: fetch once per URL, never re-check
    trim: str | None = None  # stored content is reduced by fetch.trim.TRIMMERS[trim]
    known_broken: bool = False  # a 404/410 is a recorded gap, not an error
    warnings: tuple[str, ...] = field(default=())


def _text(el) -> str:
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True)).strip()


def _file_stem(url: str) -> str:
    return PurePosixPath(urlsplit(url).path).stem


def iesco_xlsx_table(source: str, cfg: SourceConfig, html: str) -> list[Target]:
    """Rows of (circle label, date label, .xlsx link). Every configured circle appears once."""
    circles = cfg.circles or {}
    soup = BeautifulSoup(html, "html.parser")
    found: dict[str, Target] = {}
    for tr in soup.find_all("tr"):
        link = tr.find("a", href=re.compile(r"\.xlsx($|\?)", re.I))
        if not link:
            continue
        cells = [_text(td) for td in tr.find_all("td")]
        if not cells:
            continue
        label = cells[0]
        if label not in circles:
            raise DiscoveryError(f"unknown IESCO circle label {label!r}; update config/sources.yml")
        circle = circles[label]
        if circle in found:
            raise DiscoveryError(f"IESCO circle {circle!r} listed twice")
        date_label = cells[1] if len(cells) > 1 else ""
        found[circle] = Target(
            source, circle, urljoin(cfg.listing_url or "", link["href"]), date_label
        )
    missing = sorted(set(circles.values()) - set(found))
    if missing:
        raise DiscoveryError(f"IESCO XLSX links missing for circles: {missing}")
    return [found[c] for c in circles.values()]


def iesco_press_release_tab(source: str, cfg: SourceConfig, html: str) -> list[Target]:
    """Rows of (title, links labelled English/Urdu) inside the configured tab pane."""
    soup = BeautifulSoup(html, "html.parser")
    pane = soup.find(id=cfg.tab_id)
    if pane is None:
        raise DiscoveryError(f"press-release tab #{cfg.tab_id} not found")
    language = (cfg.language or "English").lower()
    targets: list[Target] = []
    for tr in pane.find_all("tr"):
        tds = tr.find_all("td")
        if not tds:
            continue
        link = next((a for a in tr.find_all("a", href=True) if _text(a).lower() == language), None)
        if link is None:
            continue
        url = urljoin(cfg.listing_url or "", link["href"])
        targets.append(Target(source, _file_stem(url), url, _text(tds[0]), refetch=cfg.refetch))
    if not targets:
        raise DiscoveryError(f"no {cfg.language} press-release links found in #{cfg.tab_id}")
    return targets


def _pdf_links(html: str, base: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    urls = [urljoin(base, a["href"]) for a in soup.find_all("a", href=re.compile(r"\.pdf", re.I))]
    return list(dict.fromkeys(urls))


def listing_pdf_pattern(source: str, cfg: SourceConfig, html: str) -> list[Target]:
    """Exactly one PDF link on the listing page whose file name matches the pattern."""
    inc = re.compile(cfg.link_pattern or ".")
    exc = re.compile(cfg.exclude_pattern) if cfg.exclude_pattern else None
    hits = [
        u
        for u in _pdf_links(html, cfg.listing_url or "")
        if inc.search(_file_stem(u)) and not (exc and exc.search(_file_stem(u)))
    ]
    if len(hits) != 1:
        raise DiscoveryError(f"expected 1 schedule PDF on {cfg.listing_url}, found {hits}")
    return [Target(source, "schedule", hits[0])]


def listing_pdfs(source: str, cfg: SourceConfig, html: str) -> list[Target]:
    """Every PDF link on the listing page whose (decoded) file name matches the pattern, e.g. a
    series of annual reports. Item key = file name with runs of other characters as "-"."""
    inc = re.compile(cfg.link_pattern or ".")
    exc = re.compile(cfg.exclude_pattern) if cfg.exclude_pattern else None
    targets = []
    for u in _pdf_links(html, cfg.listing_url or ""):
        stem = unquote(_file_stem(u))
        if inc.search(stem) and not (exc and exc.search(stem)):
            key = re.sub(r"[^A-Za-z0-9.]+", "-", stem).strip("-")
            targets.append(Target(source, key, u, label=stem, refetch=cfg.refetch))
    if not targets:
        raise DiscoveryError(f"no matching PDF on {cfg.listing_url}")
    return targets


def fixed_url(source: str, cfg: SourceConfig, html: str | None) -> list[Target]:
    """A configured URL. If a listing page is given, warn when it links a different candidate."""
    assert cfg.url
    warnings: list[str] = []
    if html is not None and cfg.listing_link_pattern:
        pat = re.compile(cfg.listing_link_pattern)
        listed = [u for u in _pdf_links(html, cfg.listing_url or "") if pat.search(_file_stem(u))]
        if cfg.url not in listed:
            warnings.append(f"listing page links {listed or 'no matching PDF'}, not {cfg.url}")
    return [Target(source, _file_stem(cfg.url), cfg.url, warnings=tuple(warnings))]


DISCOVERERS = {
    "iesco_xlsx_table": iesco_xlsx_table,
    "iesco_press_release_tab": iesco_press_release_tab,
    "listing_pdf_pattern": listing_pdf_pattern,
    "listing_pdfs": listing_pdfs,
    "fixed_url": fixed_url,
}
