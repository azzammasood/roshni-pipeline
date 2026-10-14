"""News headlines from trimmed feed snapshots: one row per link, earliest sighting wins."""

import json
from datetime import UTC, datetime
from pathlib import Path

from roshni.parsers.news import merge, parse_snapshot

T1 = datetime(2026, 10, 12, 1, 0, tzinfo=UTC)
T2 = datetime(2026, 10, 13, 1, 0, tzinfo=UTC)


def snap(tmp: Path, name: str, items: list[dict], fmt: str = "roshni-news-headlines/1") -> Path:
    p = tmp / name
    p.write_text(json.dumps({"format": fmt, "source": "news_dawn", "items": items}), "utf-8")
    return p


STORY = {
    "title": "Load shedding cut",
    "link": "https://dawn.com/1",
    "published": "2026-10-11T13:07:00Z",
}


def test_same_story_in_two_snapshots_is_one_row_first_seen_earliest(tmp_path: Path) -> None:
    a = parse_snapshot(snap(tmp_path, "a.json", [STORY]), "news_dawn", T2)
    b = parse_snapshot(snap(tmp_path, "b.json", [STORY]), "news_dawn", T1)
    (row,) = merge([a, b]).rows
    assert row.outlet == "Dawn" and row.first_seen_at == T1
    assert row.published_at == datetime(2026, 10, 11, 13, 7, tzinfo=UTC)


def test_bad_items_and_files_are_quarantined(tmp_path: Path) -> None:
    bad = {"title": "Power cuts", "link": "http://insecure.example/2", "published": "x"}
    res = parse_snapshot(
        snap(tmp_path, "c.json", [bad, {**STORY, "published": "soon"}]), "news_dawn", T1
    )
    assert [q.reason for q in res.quarantine] == ["missing title or non-https link"]
    assert res.rows[0].published_at is None  # unreadable date kept as unknown, never guessed
    other = parse_snapshot(snap(tmp_path, "d.json", [STORY], fmt="rss"), "news_dawn", T1)
    assert other.rows == [] and "unexpected format" in other.quarantine[0].reason


def test_category_and_topic_feeds_map_to_their_outlet() -> None:
    from roshni.parsers.news import outlet_of

    assert outlet_of("news_tribune_load_shedding") == "The Express Tribune"
    assert outlet_of("news_app_tag_loadshedding") == "Associated Press of Pakistan"
    assert outlet_of("news_dawn") == "Dawn"
    assert outlet_of("nepra_per_distribution") is None
