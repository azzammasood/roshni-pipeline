"""News headlines about load shedding, from the trimmed feed snapshots (fetch/trim.py): one row
per story link, first seen in the earliest snapshot that listed it. Only headline, outlet, link
and publication time exist here; the statements in headlines are the outlet's, not Roshni's."""

import json
from datetime import datetime
from pathlib import Path

from roshni.fetch.trim import FORMAT, is_load_shedding_headline
from roshni.parsers.common import ParseResult, Provenance, provenance

OUTLETS = {
    "dawn": "Dawn",
    "brecorder": "Business Recorder",
    "tribune": "The Express Tribune",
    "app": "Associated Press of Pakistan",
}


def outlet_of(source: str) -> str | None:
    """news_<outlet>[_<feed>] -> outlet name (e.g. news_tribune_business -> The Express Tribune)."""
    parts = source.split("_")
    return OUTLETS.get(parts[1]) if len(parts) > 1 and parts[0] == "news" else None


class NewsHeadline(Provenance):
    outlet: str
    title: str
    link: str
    published_at: datetime | None  # UTC; None when the feed's date could not be read
    first_seen_at: datetime | None  # fetch time of the earliest snapshot listing the story


def _when(raw: str) -> datetime | None:
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")) if raw else None
    except ValueError:
        return None


def parse_snapshot(path: Path, source: str, fetched_at: datetime | None) -> ParseResult:
    res: ParseResult[NewsHeadline] = ParseResult("news_headline")
    prov = provenance(path, fetched_at)
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        res.reject(prov, "whole file", "", f"not JSON: {e}")
        return res
    outlet = outlet_of(source)
    if doc.get("format") != FORMAT or outlet is None:
        res.reject(
            prov, "whole file", str(doc.get("format")), f"unexpected format or source {source}"
        )
        return res
    for i, it in enumerate(doc.get("items", [])):
        link, title = it.get("link", ""), it.get("title", "")
        if not title or not link.startswith("https://"):
            res.reject(prov, f"item {i}", json.dumps(it)[:500], "missing title or non-https link")
            continue
        if not is_load_shedding_headline(title):
            res.reject(prov, f"item {i}", title, "not about electricity load shedding (filter)")
            continue
        res.rows.append(
            NewsHeadline(
                **prov.model_dump(),
                outlet=outlet,
                title=title,
                link=link,
                published_at=_when(it.get("published", "")),
                first_seen_at=fetched_at,
            )
        )
    return res


def merge(results: list[ParseResult]) -> ParseResult:
    """One row per link: the earliest sighting wins (later snapshots repeat the same story)."""
    out: ParseResult[NewsHeadline] = ParseResult("news_headline")
    seen: dict[str, NewsHeadline] = {}
    for res in results:
        out.quarantine.extend(res.quarantine)
        for row in res.rows:
            prev = seen.get(row.link)
            if prev is None or (
                row.first_seen_at
                and (prev.first_seen_at is None or row.first_seen_at < prev.first_seen_at)
            ):
                seen[row.link] = row
    out.rows = sorted(seen.values(), key=lambda r: r.link)
    return out
